
"""Day 21: SQLite 会话持久化 + 结构化摘要 + 最近消息窗口。"""

import json
import re
import sqlite3
from pathlib import Path

from shopmate_agent.embedding_index import ROOT


DB_FILE = ROOT / "data" / "sessions.db"

PRODUCT_RE = re.compile(
    r"(?<![A-Za-z0-9])P\d{3}(?![A-Za-z0-9])",
    re.I,
)

CONSTRAINT_RE = re.compile(
    r"预算\s*\d+\s*元(?:以内|以下)?"
    r"|不要推荐[^\s，。；;？！,!?]{1,24}"
)


def estimate_tokens(text: str) -> int:
    """以 UTF-8 字节数做保守预算代理，不是模型精确 Token 数。"""
    return len(text.encode("utf-8"))


class SessionMemory:
    def __init__(self, db_path: Path = DB_FILE):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    facts_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL
                        CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    FOREIGN KEY(session_id)
                        REFERENCES sessions(session_id)
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON conversation_messages(session_id, id);
            """)

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def _load_session(conn, session_id, owner_id):
        row = conn.execute(
            "SELECT owner_id, facts_json "
            "FROM sessions WHERE session_id=?",
            (session_id,),
        ).fetchone()

        if row is None:
            raise KeyError("Session not found")

        if row[0] != owner_id:
            raise PermissionError("Session owner mismatch")

        return json.loads(row[1])

    def append_turn(
        self,
        session_id: str,
        owner_id: str,
        question: str,
        answer: str,
        source_ids: list[str] | None = None,
    ) -> None:
        if not all((
            session_id,
            owner_id,
            question.strip(),
            answer.strip(),
        )):
            raise ValueError("Missing session information")

        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()

            if not exists:
                facts = {
                    "constraints": [],
                    "source_ids": [],
                    "last_product_id": None,
                    "topics": [],
                }
                conn.execute(
                    "INSERT INTO sessions VALUES (?, ?, ?)",
                    (
                        session_id,
                        owner_id,
                        json.dumps(facts, ensure_ascii=False),
                    ),
                )

            # 先验证归属，再读写历史
            facts = self._load_session(
                conn, session_id, owner_id
            )

            for match in CONSTRAINT_RE.finditer(question):
                constraint = match.group().strip()

                if constraint not in facts["constraints"]:
                    facts["constraints"].append(constraint)

            products = PRODUCT_RE.findall(question)
            if products:
                facts["last_product_id"] = products[-1].upper()

            # 来源只能从已执行工具或已验证答案传入
            for sid in source_ids or []:
                if sid not in facts["source_ids"]:
                    facts["source_ids"].append(sid)

            if "订单" in question:
                topic = "订单"
            elif any(w in question for w in (
                "退货", "保修", "政策",
            )):
                topic = "政策"
            elif any(w in question for w in (
                "商品", "推荐", "预算", "价格",
            )):
                topic = "商品"
            else:
                topic = "其他"

            if topic not in facts["topics"]:
                facts["topics"].append(topic)

            conn.executemany(
                """
                INSERT INTO conversation_messages
                    (session_id, role, content)
                VALUES (?, ?, ?)
                """,
                [
                    (session_id, "user", question),
                    (session_id, "assistant", answer),
                ],
            )

            conn.execute(
                "UPDATE sessions SET facts_json=? "
                "WHERE session_id=?",
                (
                    json.dumps(facts, ensure_ascii=False),
                    session_id,
                ),
            )

    def context(
        self,
        session_id: str,
        owner_id: str,
        token_budget: int = 1200,
        recent_limit: int = 6,
    ) -> dict:
        if token_budget < 1 or recent_limit < 0:
            raise ValueError("Invalid context limits")

        with self._connect() as conn:
            facts = self._load_session(
                conn, session_id, owner_id
            )

            rows = conn.execute(
                "SELECT role, content "
                "FROM conversation_messages "
                "WHERE session_id=? "
                "ORDER BY id DESC LIMIT ?",
                (session_id, recent_limit),
            ).fetchall()

        summary = (
            "历史会话摘要（不等于已验证的实时事实）：\n"
            "讨论主题："
            + "、".join(facts["topics"]) + "\n"
            "明确商品ID："
            + str(facts["last_product_id"] or "无") + "\n"
            "用户约束："
            + "；".join(facts["constraints"]) + "\n"
            "已引用来源ID："
            + "；".join(facts["source_ids"]) + "\n"
            "订单查询必须重新验证身份与所有权；"
            "不能根据摘要捏造事实。"
        )

        recent = [
            {"role": role, "content": content}
            for role, content in reversed(rows)
        ]

        messages = [
            {"role": "system", "content": summary}
        ] + recent

        def used():
            return sum(
                estimate_tokens(m["content"])
                for m in messages
            )

        # 不允许为了压缩而悄悄丢弃关键事实
        if estimate_tokens(summary) > token_budget:
            raise ValueError(
                "Critical facts exceed budget; "
                "do not truncate constraints/sources"
            )

        # 普通历史消息从最旧一条开始移除
        while used() > token_budget and len(messages) > 1:
            messages.pop(1)

        return {
            "messages": messages,
            "summary": summary,
            "constraints": facts["constraints"],
            "source_ids": facts["source_ids"],
            "last_product_id": facts["last_product_id"],
            "estimated_tokens": used(),
            "token_budget": token_budget,
        }
