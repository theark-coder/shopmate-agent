"""Day26 tests: quota, max-inflight, stream deadline, metrics and retry jitter."""
import asyncio
import json
import random

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import StreamingResponse

from shopmate_agent.perf_guard import AdmissionGuard, AdmissionMiddleware
from scripts.load_test_day26 import backoff_seconds, percentile, summarize


def test_guard_returns_503_and_release_reopens():
    guard = AdmissionGuard(max_inflight=1, requests_per_minute=10)
    assert guard.try_enter() is None
    assert guard.try_enter() == (503, 1)
    guard.leave()
    assert guard.try_enter() is None
    guard.leave()


def test_429_after_quota_and_reset_after_a_minute():
    clock = [0.0]
    guard = AdmissionGuard(max_inflight=2, requests_per_minute=1, clock=lambda: clock[0])
    assert guard.try_enter() is None
    guard.leave()
    assert guard.try_enter() == (429, 60)
    clock[0] = 60.1
    assert guard.try_enter() is None
    guard.leave()


def make_app(guard: AdmissionGuard, timeout=1.0, delay=0):
    app = FastAPI()

    @app.get("/health/live")
    def health():
        return {"status": "alive"}

    @app.post("/api/chat/stream")
    def stream():
        async def body():
            yield "event: start\\ndata: {}\\n\\n".replace("\\n", "\n")
            if delay:
                await asyncio.sleep(delay)
            yield 'event: answer_delta\ndata: {"text":"你好"}\n\n'
            yield 'event: complete\ndata: {"status":"VERIFIED"}\n\n'
        return StreamingResponse(body(), media_type="text/event-stream")

    app.add_middleware(AdmissionMiddleware, guard=guard, timeout_seconds=timeout)
    return app


def test_middleware_429_with_retry_after_and_health_bypass():
    app = make_app(AdmissionGuard(max_inflight=4, requests_per_minute=1))
    with TestClient(app) as client:
        assert client.post("/api/chat/stream").status_code == 200
        resp = client.post("/api/chat/stream")
        assert resp.status_code == 429
        assert int(resp.headers["retry-after"]) >= 1
        assert client.get("/health/live").status_code == 200


def test_middleware_503_when_full():
    guard = AdmissionGuard(max_inflight=1, requests_per_minute=10)
    guard.try_enter()
    app = make_app(guard)
    with TestClient(app) as client:
        response = client.post("/api/chat/stream")
        assert response.status_code == 503
        assert response.headers["retry-after"] == "1"
    guard.leave()


def test_sse_timeout_emits_error_not_fake_success():
    app = make_app(AdmissionGuard(), timeout=0.02, delay=0.1)
    with TestClient(app) as client:
        resp = client.post("/api/chat/stream")
    assert resp.status_code == 200  # SSE headers already sent
    assert "event: error" in resp.text
    assert '"code": "timeout"' in resp.text
    assert "event: complete" not in resp.text


def test_backoff_honors_retry_after_and_p95():
    class FixedRng:
        def uniform(self, lo, hi):
            return hi
    assert backoff_seconds(0, "2", FixedRng()) == 2.0
    assert backoff_seconds(1, None, FixedRng()) == 1.0
    assert percentile([1, 2, 3, 4, 5]) == 5
    assert percentile([]) is None


def test_report_marks_tokens_unavailable():
    from types import SimpleNamespace
    args = SimpleNamespace(url="http://localhost:8000/api/chat/stream", requests=1,
        concurrency=20, retries=0, seed=26, timeout=75, hardware="test")
    result = summarize([{"success": True, "status": "complete", "ttft_ms": 50,
                         "latency_ms": 80, "attempts": 1, "answer_characters": 20}], 0.1, args)
    assert result["metrics"]["actual_model_tokens"] is None
    assert result["metrics"]["ttft_p95_ms_success_only"] == 50
    assert result["metrics"]["failure_rate"] == 0


def test_load_tester_counts_first_answer_delta_not_start():
    from scripts.load_test_day26 import one_request
    app = make_app(AdmissionGuard())

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await one_request(
                client, "http://test/api/chat/stream", "测试", 0, random.Random(26)
            )

    result = asyncio.run(run())
    assert result["success"] is True
    assert result["status"] == "complete"
    assert result["ttft_ms"] is not None
    assert result["answer_characters"] == 2
