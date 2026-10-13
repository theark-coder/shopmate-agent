
import asyncio

from fastapi.testclient import TestClient

from shopmate_agent import stream_api


class FakeRequest:
    def __init__(self, disconnected=False):
        self.disconnected = disconnected

    async def is_disconnected(self):
        return self.disconnected


class FakeGraph:
    def __init__(self, updates, fail=False):
        self.updates = updates
        self.fail = fail

    async def astream(self, inputs, stream_mode=None):
        assert inputs["user_id"] is None
        assert stream_mode == "updates"

        for update in self.updates:
            yield update

        if self.fail:
            raise RuntimeError("hidden detail")


def collect(request, graph):
    async def go():
        return [
            chunk
            async for chunk in stream_api.stream_events(
                request, "测试问题", graph
            )
        ]

    return asyncio.run(go())


def names(chunks):
    return [
        chunk.split("\n", 1)[0].removeprefix("event: ")
        for chunk in chunks
    ]


POLICY = [
    {
        "policy_retrieve": {
            "evidence": [
                {"doc_id": "policy-returns"}
            ]
        }
    },
    {
        "answer": {
            "answer": "可以咨询七天退货政策",
            "citations": ["policy-returns"],
        }
    },
    {"verify": {"verified": True}},
]


def test_wire_frame():
    frame = stream_api.event_frame(
        "tool", {"text": "中文"}
    )

    assert frame.startswith("event: tool\ndata: ")
    assert frame.endswith("\n\n")
    assert "中文" in frame


def test_policy_retrieval_and_verified_answer(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        stream_api,
        "LOG_FILE",
        tmp_path / "events.jsonl",
    )

    chunks = collect(
        FakeRequest(),
        FakeGraph(POLICY),
    )

    assert "retrieval" in names(chunks)
    assert "answer_delta" in names(chunks)
    assert names(chunks)[-1] == "complete"
    assert "policy-returns" in chunks[-1]

    retrieval_position = next(
        i for i, c in enumerate(chunks)
        if "event: retrieval" in c
    )
    answer_position = next(
        i for i, c in enumerate(chunks)
        if "event: answer_delta" in c
    )

    assert retrieval_position < answer_position


def test_tool_progress_and_citations():
    chunks = collect(
        FakeRequest(),
        FakeGraph([
            {
                "product_tool": {
                    "evidence": [
                        {"product_id": "P001"}
                    ]
                }
            },
            {
                "answer": {
                    "answer": "商品P001价格已查询",
                    "citations": [
                        "db:products:P001"
                    ],
                }
            },
            {"verify": {"verified": True}},
        ]),
    )

    assert "tool" in names(chunks)
    assert "db:products:P001" in chunks[-1]


def test_error_event_and_log(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        stream_api,
        "LOG_FILE",
        tmp_path / "events.jsonl",
    )

    chunks = collect(
        FakeRequest(),
        FakeGraph([], fail=True),
    )

    assert names(chunks)[-1] == "error"
    assert "hidden detail" not in chunks[-1]

    log = stream_api.LOG_FILE.read_text(
        encoding="utf-8"
    )

    assert '"event": "error"' in log


def test_disconnect_logs_cancel(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        stream_api,
        "LOG_FILE",
        tmp_path / "events.jsonl",
    )

    chunks = collect(
        FakeRequest(disconnected=True),
        FakeGraph(POLICY),
    )

    assert names(chunks) == ["start"]

    log = stream_api.LOG_FILE.read_text(
        encoding="utf-8"
    )

    assert '"event": "cancelled"' in log


def test_http_ui_and_post(monkeypatch):
    monkeypatch.setattr(
        stream_api.app.state,
        "graph",
        FakeGraph(POLICY),
    )

    client = TestClient(stream_api.app)

    assert client.get("/").status_code == 200

    response = client.post(
        "/api/chat/stream",
        json={"question": "七天退货政策"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/event-stream"
    )
    assert "event: complete" in response.text


def test_api_rejects_spoofed_identity_and_blank():
    client = TestClient(stream_api.app)

    spoofed = client.post(
        "/api/chat/stream",
        json={
            "question": "订单ORD001",
            "user_id": "demo_user_001",
        },
    )
    assert spoofed.status_code == 422

    blank = client.post(
        "/api/chat/stream",
        json={"question": "   "},
    )
    assert blank.status_code == 422
