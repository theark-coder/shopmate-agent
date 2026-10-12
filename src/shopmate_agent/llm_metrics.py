
import json
import logging
import time

logger = logging.getLogger("shopmate.llm")


def create_with_metrics(client, **kwargs):
    """调用非流式 Chat Completions，并记录用量与耗时。"""
    started = time.perf_counter()

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:
        duration_ms = round(
            (time.perf_counter() - started) * 1000, 2
        )

        logger.warning(json.dumps({
            "event": "llm_error",
            "model": kwargs.get("model"),
            "duration_ms": duration_ms,
            "error_type": type(exc).__name__,
        }, ensure_ascii=False))

        raise

    duration_ms = round(
        (time.perf_counter() - started) * 1000, 2
    )

    usage = getattr(response, "usage", None)

    metrics = {
        "event": "llm_usage",
        "request_id": getattr(response, "id", None),
        "model": getattr(
            response, "model", kwargs.get("model")
        ),
        "prompt_tokens": getattr(
            usage, "prompt_tokens", None
        ),
        "completion_tokens": getattr(
            usage, "completion_tokens", None
        ),
        "total_tokens": getattr(
            usage, "total_tokens", None
        ),
        "duration_ms": duration_ms,
    }

    logger.info(
        json.dumps(metrics, ensure_ascii=False)
    )

    return response, metrics
