
import asyncio
import json
import uuid
from contextlib import aclosing
from datetime import datetime, timezone
from shopmate_agent.security_api import router as security_router
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from shopmate_agent.embedding_index import ROOT
from shopmate_agent.shopmate_graph import build_graph


LOG_FILE = ROOT / "data/logs/stream_events.jsonl"
WEB_FILE = ROOT / "web/day22.html"

app = FastAPI(title="ShopMate Day 22 SSE")
app.include_router(security_router)
app.state.graph = build_graph()


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=500)


def event_frame(name: str, data: dict) -> str:
    """将 JSON 包装为标准 SSE 数据帧。"""
    return (
        f"event: {name}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )


def audit(
    request_id: str,
    event: str,
    reason: str = "",
) -> None:
    """只记录请求 ID 和生命周期，不记录用户原始问题。"""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "event": event,
        "reason": reason,
    }

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(
            json.dumps(entry, ensure_ascii=False) + "\n"
        )


async def stream_events(
    request: Request,
    question: str,
    graph=None,
):
    graph = app.state.graph if graph is None else graph

    request_id = uuid.uuid4().hex[:12]
    answer = ""
    citations = []
    verified = False
    safe_end = False

    try:
        yield event_frame(
            "start", {"request_id": request_id}
        )

        # 只在服务端获取身份。
        # 目前没有认证中间件，所以匿名访问不能查询私人订单。
        async with aclosing(graph.astream(
            {"question": question, "user_id": None},
            stream_mode="updates",
        )) as updates:
            async for changes in updates:
                if await request.is_disconnected():
                    audit(
                        request_id,
                        "cancelled",
                        "client_disconnected",
                    )
                    return

                for node, data in changes.items():
                    if node == "policy_retrieve":
                        source_ids = [
                            item["doc_id"]
                            for item in data.get("evidence", [])
                            if item.get("doc_id")
                        ]

                        yield event_frame("retrieval", {
                            "node": node,
                            "source_ids": source_ids,
                        })

                    elif node in (
                        "product_tool",
                        "order_tool",
                    ):
                        yield event_frame("tool", {
                            "node": node,
                            "result_count": len(
                                data.get("evidence", [])
                            ),
                        })

                    elif node == "answer":
                        # 先缓存草稿，不直接推送给浏览器
                        answer = data.get("answer", "")
                        citations = data.get(
                            "citations", []
                        )

                    elif node == "verify":
                        verified = bool(
                            data.get("verified", False)
                        )

                    elif node in ("clarify", "safe_end", "human_handoff"):
                        answer = data.get("answer", "")
                        citations = data.get(
                            "citations", []
                        )
                        safe_end = node == "safe_end"
                        verified = node in ("clarify", "human_handoff")

        if not answer or not (verified or safe_end):
            raise RuntimeError(
                "No verified answer available"
            )

        # 校验完成后再发送答复增量
        for start in range(0, len(answer), 12):
            if await request.is_disconnected():
                audit(
                    request_id,
                    "cancelled",
                    "client_disconnected",
                )
                return

            yield event_frame("answer_delta", {
                "text": answer[start:start + 12],
            })

            # 为 Day 22 断连演示提供可观察的时间窗口
            await asyncio.sleep(0.04)

        if await request.is_disconnected():
            audit(
                request_id,
                "cancelled",
                "client_disconnected",
            )
            return

        audit(request_id, "completed")

        yield event_frame("complete", {
            "status": (
                "VERIFIED" if verified else "SAFE_END"
            ),
            "citations": citations,
            "request_id": request_id,
        })

    except asyncio.CancelledError:
        audit(
            request_id,
            "cancelled",
            "stream_cancelled",
        )
        raise

    except Exception as exc:
        audit(
            request_id,
            "error",
            type(exc).__name__,
        )

        if not await request.is_disconnected():
            yield event_frame("error", {
                "message": "本次请求处理失败，请重试。",
                "request_id": request_id,
            })


@app.get("/", response_class=HTMLResponse)
def homepage():
    return WEB_FILE.read_text(encoding="utf-8")


@app.post("/api/chat/stream")
async def chat_stream(
    payload: ChatInput,
    request: Request,
):
    question = payload.question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Question cannot be blank",
        )

    return StreamingResponse(
        stream_events(request, question),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
