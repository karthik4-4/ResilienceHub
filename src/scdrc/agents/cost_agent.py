"""
Cost Agent: Computes total landed cost estimates for every candidate mitigation option
(REORDER, REROUTE, HOLD), evaluates viability, and posts COST_ESTIMATES.
"""

from __future__ import annotations
import json
from typing import Any, Dict, List, Optional

from scdrc.agents.base import BaseAgent
from scdrc.core.schemas import (
    AgentName,
    Entry,
    EntryType,
    CostEstimatesPayload,
    CostBreakdown,
    MitigationAction,
    Evidence,
)
from scdrc.core.blackboard import BlackboardView
from scdrc.data.repositories import CostRepository, SQLiteCostRepository
from scdrc.decision.options import build_candidate_options
from scdrc.decision.viability import evaluate_viability
from scdrc.decision.scoring import compute_option_cost
from scdrc.observability.tracing import Tracer


class CostAgent(BaseAgent):
    """Computes landed costs, evaluates option viability, and formats cost breakdown."""

    def __init__(
        self,
        cost_repo: Optional[CostRepository] = None,
        **kwargs,
    ):
        super().__init__(AgentName.COST, **kwargs)
        self.cost_repo = cost_repo or SQLiteCostRepository(
            self.settings.paths.database_url.replace("sqlite:///", "")
        )

    async def run(self, board: BlackboardView, tracer: Optional[Tracer] = None) -> List[Entry]:
        span = tracer.start_span(self.agent_name) if tracer else None

        # 1. Gather prerequisites from Blackboard
        items_entry = board.get_latest_entry_by_type(EntryType.AFFECTED_ITEMS)
        inv_entry = board.get_latest_entry_by_type(EntryType.INVENTORY_STATUS)
        supp_entry = board.get_latest_entry_by_type(EntryType.SUPPLIER_OPTIONS)
        route_entry = board.get_latest_entry_by_type(EntryType.ROUTE_OPTIONS)
        profile_entry = board.get_latest_entry_by_type(EntryType.DISRUPTION_PROFILE)

        items_list = items_entry.payload.get("items", []) if items_entry else []
        target_sku = items_list[0].get("sku", "SKU-1042") if items_list else "SKU-1042"
        target_qty = items_list[0].get("qty_at_risk", 1000) if items_list else 1000

        # Minimum days of cover across all affected items & sites
        inv_list = inv_entry.payload.get("inventory", []) if inv_entry else []
        min_cover = min((float(i.get("days_of_cover", 10.0)) for i in inv_list), default=10.0)

        disruption_duration = profile_entry.payload.get("expected_duration_days", 5) if profile_entry else 5
        disruption_type = profile_entry.payload.get("disruption_type", "UNKNOWN") if profile_entry else "UNKNOWN"
        is_catastrophic = "strike" in profile_entry.payload.get("source_text", "").lower() and disruption_duration >= 20

        # Item standard unit cost & rates
        item_cost = self.cost_repo.get_item_unit_cost(target_sku)
        rates = self.cost_repo.get_rates_for_category("Electronics") or {}

        # Build supplier and route lookup maps
        supplier_map: Dict[str, Dict[str, Any]] = {}
        if supp_entry:
            for s in supp_entry.payload.get("options", []):
                supplier_map[s["supplier_id"]] = s

        route_map: Dict[str, Dict[str, Any]] = {}
        if route_entry:
            for r in route_entry.payload.get("options", []):
                route_map[r["route_id"]] = r

        # 2. Build candidate options
        candidate_options = build_candidate_options(board)

        # 3. Evaluate viability and compute cost for each option
        costed_options: List[CostBreakdown] = []
        for cand in candidate_options:
            supp_info = supplier_map.get(cand.target_entity, {})
            r_info = route_map.get(cand.target_entity, {})

            # Apply viability checks
            cand = evaluate_viability(
                candidate=cand,
                days_of_cover=min_cover,
                needed_qty=target_qty,
                supplier_info=supp_info,
                route_info=r_info,
                disruption_duration_days=disruption_duration,
                disruption_type=disruption_type,
                is_catastrophic=is_catastrophic,
            )

            # Compute cost breakdown
            costed = compute_option_cost(
                option=cand,
                needed_qty=target_qty,
                item_unit_cost=item_cost,
                days_of_cover=min_cover,
                supplier_info=supp_info,
                route_info=r_info,
                rates=rates,
            )
            costed_options.append(costed)

        # 4. LLM Narrative for Cost Methodology and Assumptions
        messages = [
            {"role": "system", "content": self.prompt_template},
            {
                "role": "user",
                "content": f"Summarize the cost modeling methodology and key financial assumptions for SKU {target_sku} (qty: {target_qty}, cover: {min_cover} days).",
            },
        ]
        llm_resp = await self.call_llm(messages, response_format={"type": "json_object"})

        try:
            llm_data = json.loads(llm_resp.get("content", "{}"))
            methodology = llm_data.get("methodology", "Deterministic multi-tier landed cost evaluation")
        except Exception:
            methodology = "Deterministic multi-tier landed cost evaluation"

        payload = CostEstimatesPayload(
            estimates=costed_options,
            methodology=methodology,
        )

        evidence = [
            Evidence(
                evidence_id="EV-COST-001",
                source_type="RULE",
                citation="SCDRC Enterprise Cost Model",
                snippet=f"Evaluated {len(costed_options)} options for SKU {target_sku} at unit base INR {item_cost:.2f}",
            )
        ]

        entry = await board.post_entry(
            EntryType.COST_ESTIMATES,
            payload.model_dump(),
            confidence=0.96,
            evidence=evidence,
        )

        if span and tracer:
            tracer.end_span(
                span,
                status="SUCCESS",
                tokens=llm_resp.get("tokens"),
                tool_calls=["calculate_reorder_cost", "calculate_reroute_cost"],
            )

        return [entry]
