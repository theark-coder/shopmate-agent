
import pytest

from shopmate_agent.conversation_memory import SessionMemory


@pytest.fixture
def memory(tmp_path):
    return SessionMemory(tmp_path / "sessions.db")


def test_session_survives_restart(memory):
    memory.append_turn(
        "s1", "alice",
        "商品P001多少钱？",
        "399元",
        ["db:products:P001"],
    )

    reopened = SessionMemory(memory.db_path)
    ctx = reopened.context("s1", "alice")

    assert ctx["last_product_id"] == "P001"
    assert ctx["source_ids"] == ["db:products:P001"]
    assert any(
        m["content"] == "399元"
        for m in ctx["messages"]
    )


def test_constraints_survive_compression(memory):
    memory.append_turn(
        "s1", "alice",
        "预算300元以内，不要推荐耳机",
        "已收到要求",
    )

    for n in range(20):
        memory.append_turn(
            "s1", "alice",
            f"第{n}轮推荐商品",
            "重复回答" * 100,
            ["policy-returns"],
        )

    ctx = memory.context(
        "s1", "alice", token_budget=1200
    )

    assert "预算300元以内" in ctx["constraints"]
    assert "不要推荐耳机" in ctx["constraints"]
    assert "预算300元以内" in ctx["summary"]
    assert "policy-returns" in ctx["summary"]
    assert ctx["estimated_tokens"] <= 1200


def test_sources_stored_without_duplicate(memory):
    for _ in range(2):
        memory.append_turn(
            "s1", "alice",
            "七天退货政策",
            "查看来源",
            ["policy-returns"],
        )

    ctx = memory.context("s1", "alice")

    assert ctx["source_ids"] == ["policy-returns"]


def test_recent_window_keeps_order(memory):
    for i in range(5):
        memory.append_turn(
            "s1", "alice",
            f"问题{i}",
            f"答案{i}",
        )

    ctx = memory.context(
        "s1", "alice", recent_limit=4
    )

    assert [
        m["content"] for m in ctx["messages"][1:]
    ] == [
        "问题3", "答案3", "问题4", "答案4"
    ]


def test_read_rejects_other_owner(memory):
    memory.append_turn("s1", "alice", "问题", "回答")

    with pytest.raises(PermissionError):
        memory.context("s1", "bob")


def test_write_rejects_other_owner(memory):
    memory.append_turn("s1", "alice", "问题", "回答")

    with pytest.raises(PermissionError):
        memory.append_turn(
            "s1", "bob", "窃取", "非法回答"
        )

    assert not any(
        m["content"] == "窃取"
        for m in memory.context("s1", "alice")["messages"]
    )


def test_never_silently_truncates_critical_facts(memory):
    memory.append_turn(
        "s1", "alice",
        "预算300元以内，不要推荐耳机",
        "收到",
        ["policy-returns"],
    )

    with pytest.raises(
        ValueError,
        match="Critical facts",
    ):
        memory.context(
            "s1", "alice", token_budget=10
        )
