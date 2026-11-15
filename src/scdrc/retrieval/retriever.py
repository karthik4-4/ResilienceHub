"""
Document retriever for grounded knowledge queries.
Provides filtered top-k retrieval and constructs Evidence models for the Blackboard.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from scdrc.retrieval.store import VectorStore
from scdrc.core.schemas import Evidence


class GroundedRetriever:
    """Retrieves grounded document excerpts and builds citations."""

    def __init__(self, persist_dir: str = "./data/chroma_db"):
        self.store = VectorStore(persist_dir=persist_dir)
        self._evidence_counter = 0

    def query(
        self,
        query: str,
        n_results: int = 3,
        doc_type: Optional[str] = None,
        supplier_id: Optional[str] = None,
        lane_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query ChromaDB with optional metadata filters."""
        where_filter: Optional[Dict[str, Any]] = None
        conditions: List[Dict[str, Any]] = []

        if doc_type:
            conditions.append({"doc_type": doc_type})
        if supplier_id:
            conditions.append({"supplier_id": supplier_id})
        if lane_id:
            conditions.append({"lane_id": lane_id})

        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        return self.store.query(query_text=query, n_results=n_results, where=where_filter)

    def retrieve_with_evidence(
        self,
        query: str,
        n_results: int = 3,
        doc_type: Optional[str] = None,
        supplier_id: Optional[str] = None,
        lane_id: Optional[str] = None,
    ) -> List[Evidence]:
        """Query documents and return structured Evidence objects with citations."""
        results = self.query(
            query=query,
            n_results=n_results,
            doc_type=doc_type,
            supplier_id=supplier_id,
            lane_id=lane_id,
        )

        evidence_list: List[Evidence] = []
        for r in results:
            self._evidence_counter += 1
            meta = r.get("metadata", {})
            doc_id = meta.get("doc_id", "DOC-UNKNOWN")
            section = meta.get("section", "General")
            citation = f"{doc_id} § {section}"
            snippet = r.get("content", "")[:280].strip()

            evidence = Evidence(
                evidence_id=f"EV-{self._evidence_counter:04d}",
                source_type="RAG",
                citation=citation,
                snippet=snippet,
            )
            evidence_list.append(evidence)

        return evidence_list
