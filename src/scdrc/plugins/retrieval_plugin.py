"""
Semantic Kernel Plugin: Grounded RAG document queries.
"""

from __future__ import annotations
import json
from semantic_kernel.functions import kernel_function
from scdrc.retrieval.retriever import GroundedRetriever


class RetrievalPlugin:
    """Tools for retrieving contract clauses, SOP policies, and freight advisories."""

    def __init__(self, retriever: GroundedRetriever):
        self.retriever = retriever

    @kernel_function(description="Retrieve specific supplier contract clauses (exclusivity, force majeure, penalties, lead times).")
    def retrieve_contract_clause(self, query: str, supplier_id: str = "") -> str:
        results = self.retriever.query(
            query=query,
            n_results=3,
            doc_type="CONTRACT",
            supplier_id=supplier_id if supplier_id else None,
        )
        return json.dumps(results, indent=2)

    @kernel_function(description="Retrieve freight advisories, port congestion notes, and weather warnings.")
    def retrieve_advisory(self, query: str, lane_id: str = "") -> str:
        results = self.retriever.query(
            query=query,
            n_results=3,
            doc_type="ADVISORY",
            lane_id=lane_id if lane_id else None,
        )
        return json.dumps(results, indent=2)

    @kernel_function(description="Retrieve standard operating procedures (SOPs) on stockout response and escalation rules.")
    def retrieve_sop(self, query: str) -> str:
        results = self.retriever.query(
            query=query,
            n_results=3,
            doc_type="SOP",
        )
        return json.dumps(results, indent=2)
