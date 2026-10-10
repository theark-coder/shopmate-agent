
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    version: str
    source: str
    source_path: str
    heading: str
    start_char: int
    end_char: int
    text: str


def parse_markdown(path: Path):
    raw = path.read_text(encoding="utf-8")

    if not raw.startswith("---\n"):
        raise ValueError(f"Missing frontmatter: {path}")

    parts = raw.split("---", 2)
    if len(parts) != 3:
        raise ValueError(f"Invalid frontmatter: {path}")

    metadata = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()

    for key in ("doc_id", "version", "source"):
        if not metadata.get(key):
            raise ValueError(f"Missing {key}: {path}")

    # 保留正文原始字符位置，不随意 strip
    body = parts[2]
    return metadata, body


def split_markdown(
    path: Path,
    max_chars: int = 300,
    overlap: int = 40,
) -> list[Chunk]:
    if max_chars < 1 or overlap < 0 or overlap >= max_chars:
        raise ValueError("Invalid chunk settings")

    metadata, body = parse_markdown(path)

    # 找 Markdown 标题，以标题作为优先分块边界
    headings = list(
        re.finditer(r"^#{1,6}\s+.+$", body, re.MULTILINE)
    )

    starts = [0]
    starts.extend(
        match.start()
        for match in headings
        if match.start() != 0
    )
    starts = sorted(set(starts))
    starts.append(len(body))

    chunks = []

    for section_index in range(len(starts) - 1):
        section_start = starts[section_index]
        section_end = starts[section_index + 1]

        section = body[section_start:section_end]
        if not section.strip():
            continue

        heading_match = re.search(
            r"^#{1,6}\s+(.+)$",
            section,
            re.MULTILINE,
        )
        heading = (
            heading_match.group(1)
            if heading_match
            else ""
        )

        start = section_start

        while start < section_end:
            end = min(start + max_chars, section_end)

            # 优先在段落空行处分块
            if end < section_end:
                candidate = body.rfind(
                    "\n\n",
                    start + 1,
                    end,
                )

                if candidate > start + max_chars // 2:
                    end = candidate + 2

            text = body[start:end]

            if text.strip():
                chunks.append(
                    Chunk(
                        chunk_id=(
                            f"{metadata['doc_id']}:"
                            f"{len(chunks):03d}"
                        ),
                        doc_id=metadata["doc_id"],
                        version=metadata["version"],
                        source=metadata["source"],
                        source_path=path.as_posix(),
                        heading=heading,
                        start_char=start,
                        end_char=end,
                        text=text,
                    )
                )

            if end == section_end:
                break

            # 下一块与上一块保持重叠
            start = end - overlap

    return chunks


def chunk_directory(root: Path, **kwargs) -> list[Chunk]:
    chunks = []

    for path in sorted(root.rglob("*.md")):
        chunks.extend(split_markdown(path, **kwargs))

    return chunks
