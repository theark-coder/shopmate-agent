"""Reproducible 20-concurrent SSE benchmark for the local demo.

Measures TTFT at the first `answer_delta`, not SSE `start`.
`actual_model_tokens` stays null because ShopMate's present graph does not
call a provider model or return token usage. `answer_characters` is NOT tokens.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import platform
import random
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

SAMPLES = [
    "七天退货有什么条件？",
    "商品P001多少钱？",
    "付款后什么时候发货？",
    "订单ORD001现在什么状态？",
    "如何申请商品保修？",
]
RETRYABLE_HTTP = {429, 500, 502, 503, 504}


def percentile(values: list[float], ratio: float = 0.95) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * ratio) - 1)], 2)


def backoff_seconds(attempt: int, retry_after: str | None, rng) -> float:
    """Full jitter, honoring Retry-After; do not retry an established SSE stream."""
    try:
        required = max(0.0, float(retry_after or 0))
    except ValueError:
        required = 0.0
    return max(required, rng.uniform(0, min(8.0, 0.5 * 2**attempt)))


def summarize(results: list[dict], wall_seconds: float, args) -> dict:
    successes = [r for r in results if r["success"]]
    statuses = Counter(str(r["status"]) for r in results)
    ttfts = [r["ttft_ms"] for r in successes if r["ttft_ms"] is not None]
    return {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_url": args.url,
        "run_configuration": {
            "requests": args.requests,
            "concurrency": args.concurrency,
            "max_retries": args.retries,
            "seed": args.seed,
            "timeout_s": args.timeout,
            "scenario": "fixed-demo-5-questions",
        },
        "environment": {
            "os": platform.platform(),
            "cpu": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "hardware_notes": args.hardware,
            "service": "ShopMate FastAPI / LangGraph rules demo",
            "model": "No hosted LLM in current graph",
            "token_accounting": "unavailable: no model usage returned",
        },
        "metrics": {
            "completed_requests": len(successes),
            "total_requests": len(results),
            "failure_rate": round(1 - len(successes) / len(results), 4) if results else None,
            "status_counts": dict(statuses),
            "ttft_p50_ms_success_only": percentile(ttfts, 0.50),
            "ttft_p95_ms_success_only": percentile(ttfts),
            "latency_p95_ms_success_only": percentile([r["latency_ms"] for r in successes]),
            "wall_seconds": round(wall_seconds, 3),
            "success_throughput_rps": round(len(successes) / wall_seconds, 3) if wall_seconds else 0,
            "request_attempts": sum(r["attempts"] for r in results),
            "answer_characters_total": sum(r["answer_characters"] for r in successes),
            "actual_model_tokens": None,
        },
        "limitations": [
            "Only on local demo hardware; no external LLM API/token usage.",
            "TTFT is first verified answer_delta, not initial SSE start.",
            "Success requires SSE complete; HTTP 200 with SSE error is failure.",
            "429/503 load shedding counts as failed requests unless retry succeeds.",
            "In-process limiter is per worker, not cluster-wide.",
        ],
    }


async def one_request(client: httpx.AsyncClient, url: str, question: str,
                      max_retries: int, rng) -> dict:
    start = time.perf_counter()
    status: str | int = "network_error"
    attempts = 0
    answer_characters = 0
    ttft_ms = None
    success = False

    for attempt in range(max_retries + 1):
        attempts += 1
        event_name = ""
        event_data = []
        try:
            async with client.stream("POST", url, json={"question": question}) as resp:
                status = resp.status_code
                if status in RETRYABLE_HTTP and attempt < max_retries:
                    await resp.aread()
                    delay = backoff_seconds(attempt, resp.headers.get("retry-after"), rng)
                elif status != 200:
                    await resp.aread()
                    break
                else:
                    error_event = False
                    completed = False
                    async for line in resp.aiter_lines():
                        if line.startswith("event:"):
                            event_name = line[6:].strip()
                        elif line.startswith("data:"):
                            event_data.append(line[5:].strip())
                        elif line == "":
                            if event_name == "answer_delta":
                                if ttft_ms is None:
                                    ttft_ms = round((time.perf_counter() - start) * 1000, 2)
                                try:
                                    answer_characters += len(json.loads("".join(event_data)).get("text", ""))
                                except json.JSONDecodeError:
                                    error_event = True
                            elif event_name == "complete":
                                completed = True
                            elif event_name == "error":
                                error_event = True
                            event_name, event_data = "", []
                    success = completed and not error_event
                    status = "complete" if success else "sse_error_or_incomplete"
                    break
            if status in RETRYABLE_HTTP and attempt < max_retries:
                await asyncio.sleep(delay)
                continue
        except (httpx.RequestError, httpx.TimeoutException) as e:
            status = type(e).__name__
            # Never retry an interrupted 200/SSE response: it may have streamed data.
            break

    return {
        "success": success,
        "status": status,
        "attempts": attempts,
        "ttft_ms": ttft_ms,
        "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        "answer_characters": answer_characters,
    }


async def benchmark(args) -> dict:
    rng = random.Random(args.seed)
    questions = [SAMPLES[i % len(SAMPLES)] for i in range(args.requests)]
    rng.shuffle(questions)
    semaphore = asyncio.Semaphore(args.concurrency)
    timeout = httpx.Timeout(args.timeout)
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout, limits=limits, trust_env=False) as client:
        async def run(question):
            async with semaphore:
                return await one_request(client, args.url, question, args.retries, rng)
        results = await asyncio.gather(*(run(q) for q in questions))
    return summarize(results, time.perf_counter() - start, args)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="ShopMate Day26 SSE performance run")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/chat/stream")
    parser.add_argument("--requests", type=int, default=40)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--retries", type=int, choices=(0, 1, 2), default=0)
    parser.add_argument("--seed", type=int, default=26)
    parser.add_argument("--timeout", type=float, default=75)
    parser.add_argument("--hardware", default="Fill in actual machine CPU / RAM / GPU")
    parser.add_argument("--output", default="reports/day26/performance.json")
    args = parser.parse_args(argv)
    if args.requests < 1 or args.concurrency < 1 or args.timeout <= 0:
        parser.error("requests/concurrency/timeout must be positive")
    return args


def main():
    args = parse_args()
    data = asyncio.run(benchmark(args))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data["metrics"], ensure_ascii=False, indent=2))
    print("Report:", output)


if __name__ == "__main__":
    main()
