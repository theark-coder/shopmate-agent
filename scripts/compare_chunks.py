
from pathlib import Path

from shopmate_agent.chunking import chunk_directory


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "data" / "knowledge"

for size, overlap in [(100, 20), (300, 40)]:
    chunks = chunk_directory(
        KNOWLEDGE,
        max_chars=size,
        overlap=overlap,
    )

    print(f"\nChunk size={size}, overlap={overlap}")
    print("Total chunks:", len(chunks))

    for chunk in chunks[:3]:
        print({
            "doc_id": chunk.doc_id,
            "heading": chunk.heading,
            "length": len(chunk.text),
            "range": (
                chunk.start_char,
                chunk.end_char,
            ),
        })
