"""
Document ingestion pipeline for RAG corpus.
Parses markdown files with frontmatter, chunks by section, and stores in ChromaDB.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
import yaml

from scdrc.retrieval.store import VectorStore


def parse_markdown_with_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Extract YAML frontmatter and body from markdown file."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
                return metadata, body
            except Exception:
                pass
    return {}, content.strip()


def chunk_document_by_section(
    doc_id: str,
    base_metadata: Dict[str, Any],
    body: str,
    max_words: int = 250,
) -> List[Dict[str, Any]]:
    """Split document into sections based on markdown headings."""
    chunks: List[Dict[str, Any]] = []
    sections = re.split(r"(?=^###?\s+)", body, flags=re.MULTILINE)

    chunk_idx = 0
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue

        lines = sec.splitlines()
        first_line = lines[0].strip("# ").strip() if lines else "General"

        meta = dict(base_metadata)
        meta["section"] = first_line
        meta["doc_id"] = doc_id

        # Normalize metadata values for ChromaDB (scalars only)
        clean_meta = {}
        for k, v in meta.items():
            if isinstance(v, (str, int, float, bool)):
                clean_meta[k] = v
            else:
                clean_meta[k] = str(v)

        chunk_id = f"{doc_id}-CHK-{chunk_idx:02d}"
        chunks.append({
            "id": chunk_id,
            "text": sec,
            "metadata": clean_meta,
        })
        chunk_idx += 1

    return chunks


def ingest_documents(
    docs_dir: str = "./data/documents",
    persist_dir: str = "./data/chroma_db",
) -> int:
    """Ingest all contracts, SOPs, and advisories into the vector store."""
    store = VectorStore(persist_dir=persist_dir)
    base_path = Path(docs_dir)

    all_ids: List[str] = []
    all_texts: List[str] = []
    all_metadatas: List[Dict[str, Any]] = []

    for file_path in base_path.rglob("*.md"):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        metadata, body = parse_markdown_with_frontmatter(content)
        doc_id = metadata.get("doc_id", file_path.stem)

        chunks = chunk_document_by_section(doc_id, metadata, body)
        for chk in chunks:
            all_ids.append(chk["id"])
            all_texts.append(chk["text"])
            all_metadatas.append(chk["metadata"])

    if all_ids:
        store.add_documents(ids=all_ids, documents=all_texts, metadatas=all_metadatas)

    count = store.count()
    print(f"Ingested {len(all_ids)} document chunks into ChromaDB. Total collection size: {count}")
    return count


if __name__ == "__main__":
    ingest_documents()
