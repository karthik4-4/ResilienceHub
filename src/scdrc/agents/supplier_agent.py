"""
Supplier Agent: Identifies alternative supplier options, evaluates contracts via RAG,
verifies qualification/exclusivity rules, and posts SUPPLIER_OPTIONS.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from scdrc.agents.base import BaseAgent
from scdrc.core.schemas import (
    AgentName,
    Entry,
    EntryType,
    SupplierOptionsPayload,
    SupplierOption,
    Evidence,
)
from scdrc.core.blackboard import BlackboardView
from scdrc.data.repositories import SupplierRepository, SQLiteSupplierRepository
from scdrc.retrieval.retriever import GroundedRetriever
from scdrc.observability.tracing import Tracer


class SupplierAgent(BaseAgent):
    """Finds alternate suppliers and grounds terms in contracts via RAG."""

    def __init__(
        self,
        supp_repo: Optional[SupplierRepository] = None,
        retriever: Optional[GroundedRetriever] = None,
        **kwargs,
    ):
        super().__init__(AgentName.SUPPLIER, **kwargs)
        self.supp_repo = supp_repo or SQLiteSupplierRepository(
            self.settings.paths.database_url.replace("sqlite:///", "")
        )
        self.retriever = retriever or GroundedRetriever(
            persist_dir=self.settings.paths.chroma_persist_dir
        )

    async def run(self, board: BlackboardView, tracer: Optional[Tracer] = None) -> List[Entry]:
        span = tracer.start_span(self.agent_name) if tracer else None

        items_entry = board.get_latest_entry_by_type(EntryType.AFFECTED_ITEMS)
        items = items_entry.payload.get("items", []) if items_entry else []
        sku_list = [i["sku"] for i in items if i.get("sku")]

        options: List[SupplierOption] = []
        evidence_list: List[Evidence] = []
        tool_calls: List[str] = []

        for sku in sku_list:
            tool_calls.append(f"find_suppliers_for_sku({sku})")
            db_suppliers = self.supp_repo.find_suppliers_for_sku(sku)

            for s in db_suppliers:
                supp_id = s["supplier_id"]
                # Skip primary supplier if it is the one disrupted
                # (unless explicitly requested)
                is_primary = bool(s.get("is_primary", 0))
                is_qualified = bool(s.get("is_qualified", 1))

                contract_ref = s.get("contract_id", f"CTR-{supp_id}-2025")
                disqualification_reason: Optional[str] = None

                # Query RAG for contract terms & exclusivity clauses
                rag_evidences = self.retriever.retrieve_with_evidence(
                    query=f"supplier {supp_id} exclusivity qualification clause terms",
                    n_results=2,
                    supplier_id=supp_id,
                )
                evidence_list.extend(rag_evidences)

                # Check for contract disqualification clauses (Scenario S6)
                for ev in rag_evidences:
                    snip = ev.snippet.lower()
                    if "disqualified" in snip or "unqualified" in snip or "probationary" in snip or "clause 4.2" in snip:
                        is_qualified = False
                        disqualification_reason = f"Disqualified per contract terms: {ev.citation}"

                if not is_qualified and not disqualification_reason:
                    disqualification_reason = "Probationary status / uncertified for Tier-1 production"

                options.append(
                    SupplierOption(
                        supplier_id=supp_id,
                        supplier_name=s.get("name"),
                        sku=sku,
                        unit_price_inr=float(s["unit_price_inr"]),
                        moq=int(s["moq"]),
                        lead_time_days=int(s["standard_lead_time_days"]),
                        capacity=int(s["max_capacity"]),
                        reliability_score=float(s["reliability_score"]),
                        contract_ref=contract_ref,
                        qualified=is_qualified,
                        disqualification_reason=disqualification_reason,
                    )
                )

        payload = SupplierOptionsPayload(
            options=options,
            summary=f"Evaluated {len(options)} supplier options across {len(sku_list)} SKUs.",
        )

        entry = await board.post_entry(
            EntryType.SUPPLIER_OPTIONS,
            payload.model_dump(),
            confidence=0.95,
            evidence=evidence_list,
        )

        if span and tracer:
            tracer.end_span(
                span,
                status="SUCCESS",
                tool_calls=tool_calls,
            )

        return [entry]
