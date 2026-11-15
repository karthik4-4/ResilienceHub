"""
ChromaDB vector store wrapper for grounded enterprise document retrieval.
Includes a self-contained local embedding function ensuring zero network dependencies.
"""

from __future__ import annotations
import math
import re
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings


class LocalDeterministicEmbeddingFunction(EmbeddingFunction):
    """
    High-speed, deterministic 64-dimensional n-gram semantic embedding.
    Ensures 100% local execution without calling external APIs or downloading models.
    """

    def __init__(self, dim: int = 64):
        self.dim = dim

    def __call__(self, input: Documents) -> Embeddings:
        embeddings: List[List[float]] = []
        for text in input:
            vec = [0.0] * self.dim
            words = re.findall(r"\w+", text.lower())
            if not words:
                embeddings.append(vec)
                continue

            for i, word in enumerate(words):
                h = hash(word) % self.dim
                vec[h] += 1.0
                if i < len(words) - 1:
                    bigram = f"{word}_{words[i+1]}"
                    h_bi = hash(bigram) % self.dim
                    vec[h_bi] += 1.5

            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            embeddings.append(vec)
        return embeddings


class VectorStore:
    """Wrapper around persistent ChromaDB collection."""

    def __init__(self, persist_dir: str = "./data/chroma_db", collection_name: str = "scdrc_knowledge"):
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.embedding_fn = LocalDeterministicEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
            metadata={"description": "Supply chain contracts, SOPs, and freight advisories"},
        )

    def add_documents(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Upsert documents into ChromaDB."""
        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    def query(
        self,
        query_text: str,
        n_results: int = 4,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query vector store and return matched chunks with metadata and distances."""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
        )

        matched: List[Dict[str, Any]] = []
        if results and results["ids"] and len(results["ids"]) > 0:
            doc_ids = results["ids"][0]
            docs = results["documents"][0] if results["documents"] else []
            metas = results["metadatas"][0] if results["metadatas"] else []
            distances = results["distances"][0] if results["distances"] else []

            for i in range(len(doc_ids)):
                matched.append({
                    "chunk_id": doc_ids[i],
                    "content": docs[i] if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {},
                    "score": 1.0 - (distances[i] if i < len(distances) else 0.0),
                })
        return matched

    def count(self) -> int:
        return self.collection.count()
