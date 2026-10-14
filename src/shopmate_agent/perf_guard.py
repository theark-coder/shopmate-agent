"""Day 26: per-process SSE admission control, 429/503 and request deadline.

The guard applies only to POST /api/chat/stream. It does not alter public
health checks or Day 23 ownership checks. For one Uvicorn worker, counters
are process-wide; multiple workers/replicas require a shared rate limiter.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable

from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class AdmissionGuard:
    def __init__(
        self,
        max_inflight: int = 4,
        requests_per_minute: int = 120,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_inflight < 1 or requests_per_minute < 1:
            raise ValueError("limits must be positive")
        self.max_inflight = max_inflight
        self.requests_per_minute = requests_per_minute
        self.clock = clock
        self.active = 0
        self.timestamps: deque[float] = deque()
        self.lock = threading.Lock()

    def try_enter(self) -> tuple[int, int] | None:
        """Return (status_code, Retry-After seconds), or None if admitted."""
        with self.lock:
            now = self.clock()
            while self.timestamps and now - self.timestamps[0] >= 60:
                self.timestamps.popleft()

            # Do not spend rate quota on concurrency rejections.
            if self.active >= self.max_inflight:
                return (503, 1)
            if len(self.timestamps) >= self.requests_per_minute:
                wait = math.ceil(60 - (now - self.timestamps[0]))
                return (429, max(1, wait))

            self.active += 1
            self.timestamps.append(now)
            return None

    def leave(self) -> None:
        with self.lock:
            if self.active <= 0:
                raise RuntimeError("admission guard over-released")
            self.active -= 1


class AdmissionMiddleware:
    """Pure ASGI: hold a slot until the SSE body is finished or cancelled."""

    def __init__(
        self,
        app,
        *,
        guard: AdmissionGuard | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.app = app
        self.guard = guard or AdmissionGuard()
        self.timeout_seconds = timeout_seconds

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or not (
            scope.get("path") == "/api/chat/stream"
            and scope.get("method") == "POST"
        ):
            await self.app(scope, receive, send)
            return

        rejected = self.guard.try_enter()
        if rejected is not None:
            status, retry_after = rejected
            detail = (
                "请求过于频繁，请稍后重试。"
                if status == 429 else "服务繁忙，请稍后重试。"
            )
            response = JSONResponse(
                {"detail": detail},
                status_code=status,
                headers={"Retry-After": str(retry_after), "Cache-Control": "no-store"},
            )
            await response(scope, receive, send)
            return

        response_started = False
        response_completed = False

        async def tracked_send(message):
            nonlocal response_started, response_completed
            if message["type"] == "http.response.start":
                response_started = True
            elif message["type"] == "http.response.body" and not message.get("more_body", False):
                response_completed = True
            await send(message)

        try:
            await asyncio.wait_for(
                self.app(scope, receive, tracked_send),
                timeout=self.timeout_seconds,
            )
        except TimeoutError:
            logger.warning("Day26 SSE deadline exceeded; request payload omitted")
            if not response_started:
                response = JSONResponse(
                    {"detail": "处理超时，请稍后重试。"},
                    status_code=504,
                    headers={"Cache-Control": "no-store"},
                )
                await response(scope, receive, send)
            elif not response_completed:
                # HTTP headers are already 200; stream an explicit SSE error.
                frame = (
                    'event: error\ndata: '
                    + json.dumps({"message": "处理超时，请稍后重试。", "code": "timeout"}, ensure_ascii=False)
                    + '\n\n'
                ).encode("utf-8")
                await send({"type": "http.response.body", "body": frame, "more_body": True})
                await send({"type": "http.response.body", "body": b"", "more_body": False})
        finally:
            self.guard.leave()


def configured_guard() -> AdmissionGuard:
    return AdmissionGuard(
        max_inflight=int(os.getenv("SHOPMATE_MAX_INFLIGHT", "4")),
        requests_per_minute=int(os.getenv("SHOPMATE_RPM", "120")),
    )
