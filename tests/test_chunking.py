
from pathlib import Path

from shopmate_agent.chunking import (
    parse_markdown,
    split_markdown,
    chunk_directory,
)


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "data" / "knowledge"


def test_ten_documents_have_metadata_and_source():
    paths = sorted(KNOWLEDGE.rglob("*.md"))
    assert len(paths) == 30

    for path in paths[:10]:
        metadata, body = parse_markdown(path)
        chunks = split_markdown(path)

        assert chunks

        for chunk in chunks:
            assert chunk.doc_id == metadata["doc_id"]
            assert chunk.version == metadata["version"]
            assert chunk.source == metadata["source"]
            assert chunk.source_path == path.as_posix()

            # 必须能够定位到原文
            assert (
                body[chunk.start_char:chunk.end_char]
                == chunk.text
            )


def test_policy_conditions_are_preserved():
    path = KNOWLEDGE / "policies" / "returns.md"

    _, body = parse_markdown(path)
    chunks = split_markdown(path, max_chars=300)

    assert any(
        "签收后7天内" in chunk.text
        and "商品应保持完好" in chunk.text
        and "定制商品" in chunk.text
        for chunk in chunks
    )

    assert all(
        chunk.version == "1.0"
        and chunk.source == "shopmate-demo"
        for chunk in chunks
    )


def test_long_document_and_overlap(tmp_path):
    path = tmp_path / "long.md"

    text = (
        "---\n"
        "doc_id: long-test\n"
        "version: 1.0\n"
        "source: shopmate-demo\n"
        "---\n\n"
        "# 长商品说明\n\n"
        + "商品功能描述。" * 100
    )

    path.write_text(text, encoding="utf-8")

    chunks = split_markdown(
        path,
        max_chars=100,
        overlap=20,
    )

    assert len(chunks) > 1

    _, body = parse_markdown(path)

    for chunk in chunks:
        assert len(chunk.text) <= 100
        assert body[chunk.start_char:chunk.end_char] == chunk.text

    for previous, current in zip(chunks, chunks[1:]):
        assert current.start_char <= previous.end_char


def test_all_documents_can_be_chunked():
    chunks = chunk_directory(KNOWLEDGE)

    assert chunks
    assert len({chunk.doc_id for chunk in chunks}) == 30
