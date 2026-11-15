"""
Coordinator Agent: Reads the complete Blackboard, evaluates candidate mitigations,
determines the cheapest viable action (REORDER, REROUTE, or HOLD),
validates citations via GroundingValidator, and posts DECISION.
"""

from __future__ import annotations
import json
from typing import Any, Dict, List, Optional

from scdrc.agents.base import BaseAgent
from scdrc.core.schemas import (
    AgentName,
    Entry,
    EntryType,
    DecisionPayload,
    MitigationAction,
    RejectedOption,
    NotificationRecipient,
    CostBreakdown,
)
from scdrc.core.blackboard import BlackboardView
from scdrc.decision.scoring import rank_mitigation_options
from scdrc.decision.validator import GroundingValidator
from scdrc.observability.tracing import Tracer


class CoordinatorAgent(BaseAgent):
    """Orchestrates final mitigation decision strictly based on Blackboard entries."""

    def __init__(self, **kwargs):
        super().__init__(AgentName.COORDINATOR, **kwargs)

    async def run(self, board: BlackboardView, tracer: Optional[Tracer] = None) -> List[Entry]:
        span = tracer.start_span(self.agent_name) if tracer else None

        # 1. Read all entries on the Blackboard
        all_entries = board.get_all_entries()
        entry_id_map = {e.entry_id: e for e in all_entries}

        # Identify key entries
        profile_entry = board.get_latest_entry_by_type(EntryType.DISRUPTION_PROFILE)
        items_entry = board.get_latest_entry_by_type(EntryType.AFFECTED_ITEMS)
        sites_entry = board.get_latest_entry_by_type(EntryType.AFFECTED_SITES)
        inv_entry = board.get_latest_entry_by_type(EntryType.INVENTORY_STATUS)
        supp_entry = board.get_latest_entry_by_type(EntryType.SUPPLIER_OPTIONS)
        route_entry = board.get_latest_entry_by_type(EntryType.ROUTE_OPTIONS)
        cost_entry = board.get_latest_entry_by_type(EntryType.COST_ESTIMATES)
        degraded_entry = board.get_latest_entry_by_type(EntryType.DEGRADED)

        # 2. Extract cost estimates & rank options deterministically
        estimates_raw = cost_entry.payload.get("estimates", []) if cost_entry else []
        options = [CostBreakdown(**e) for e in estimates_raw]

        supplier_map: Dict[str, Dict[str, Any]] = {}
        if supp_entry:
            for s in supp_entry.payload.get("options", []):
                supplier_map[s["supplier_id"]] = s

        best_option, viable_ranked, non_viable = rank_mitigation_options(options, supplier_map)

        # Build list of cited entry IDs
        cited_entries: List[str] = []
        if inv_entry:
            cited_entries.append(inv_entry.entry_id)
        if supp_entry:
            cited_entries.append(supp_entry.entry_id)
        if route_entry:
            cited_entries.append(route_entry.entry_id)
        if cost_entry:
            cited_entries.append(cost_entry.entry_id)
        if degraded_entry:
            cited_entries.append(degraded_entry.entry_id)

        # Prepare rejected options summary
        rejected_list: List[RejectedOption] = [
            RejectedOption(
                option=opt.option_id,
                reason=opt.non_viability_reason or "Higher cost than selected option",
            )
            for opt in non_viable
        ]
        # Also add non-chosen viable options as rejected due to higher cost
        if viable_ranked and len(viable_ranked) > 1:
            for opt in viable_ranked[1:]:
                rejected_list.append(
                    RejectedOption(
                        option=opt.option_id,
                        reason=f"Viable but higher total landed cost (INR {opt.total_cost_inr:,.2f}) vs chosen option (INR {best_option.total_cost_inr:,.2f})",
                    )
                )

        # Determine default action and chosen option
        is_degraded = degraded_entry is not None
        confidence = 0.90 if not is_degraded else 0.65

        # Check for ambiguous report / low confidence
        if items_entry and items_entry.payload.get("unresolved_tokens") and not items_entry.payload.get("items"):
            action = MitigationAction.HOLD
            chosen_id = "HOLD"
            total_cost = 0.0
            confidence = 0.50
            rationale = (
                f"Report is ambiguous with unresolved entities ({', '.join(items_entry.payload.get('unresolved_tokens'))}). "
                f"Holding action pending manual intelligence verification per {items_entry.entry_id}."
            )
        elif not best_option or best_option.option_id == "HOLD" or (not viable_ranked and not is_degraded):
            action = MitigationAction.HOLD
            chosen_id = "HOLD"
            total_cost = best_option.total_cost_inr if best_option else 0.0
            if non_viable and all(not o.is_viable for o in options):
                rationale = (
                    f"No viable alternative options exist capable of arriving before stockout. "
                    f"System safely defaults to HOLD and triggers executive escalation. Cited: {', '.join(cited_entries)}."
                )
            else:
                rationale = (
                    f"Inventory cover safely absorbs disruption duration without breaching buffer. "
                    f"HOLD is the cost-optimal rational decision. Cited: {', '.join(cited_entries)}."
                )
        else:
            action = best_option.action_type
            chosen_id = best_option.target_entity
            total_cost = best_option.total_cost_inr

            # Synthesize grounded rationale
            if action == MitigationAction.REORDER:
                rationale = (
                    f"Primary supplier disruption exceeds available cover. Supplier {chosen_id} is pre-qualified and delivers "
                    f"in {best_option.arrival_days} days. It represents the cheapest viable mitigation at INR {total_cost:,.2f} "
                    f"compared to alternative options. Cited entries: {', '.join(cited_entries)}."
                )
            elif action == MitigationAction.REROUTE:
                rationale = (
                    f"Freight lane disruption bypassed via route {chosen_id}. Rail/alternative corridor arrives in "
                    f"{best_option.arrival_days} days with minimal delay, comfortably absorbed by destination stock cover. "
                    f"Total differential cost: INR {total_cost:,.2f}. Cited entries: {', '.join(cited_entries)}."
                )
            else:
                rationale = f"Holding action chosen with cost INR {total_cost:,.2f}. Cited: {', '.join(cited_entries)}."

        # If degraded mode active (Scenario S10)
        if is_degraded:
            action = MitigationAction.HOLD
            chosen_id = "HOLD"
            total_cost = 0.0
            rationale = (
                f"Blackboard marked as DEGRADED due to failure in {degraded_entry.payload.get('failed_agent')}. "
                f"Operating with partial knowledge; defaulting to safe HOLD and escalating to human planners. "
                f"Cited: {degraded_entry.entry_id}."
            )

        # 3. LLM Refinement of Rationale (optional polish, preserves grounding)
        messages = [
            {"role": "system", "content": self.prompt_template},
            {
                "role": "user",
                "content": (
                    f"Decide mitigation for case {board.case_id}.\n"
                    f"Action: {action.value}, Chosen: {chosen_id}, Cost: {total_cost}\n"
                    f"Cited Entry IDs: {cited_entries}\n"
                    f"Draft Rationale: {rationale}\n"
                    f"Output final JSON."
                ),
            },
        ]
        llm_resp = await self.call_llm(messages, response_format={"type": "json_object"})

        try:
            llm_decision = json.loads(llm_resp.get("content", "{}"))
            if llm_decision.get("rationale") and all(cid in llm_decision.get("rationale", "") for cid in cited_entries[:2]):
                rationale = llm_decision["rationale"]
        except Exception:
            pass

        # 4. Construct initial DecisionPayload
        decision_payload = DecisionPayload(
            action=action,
            chosen_option_id=chosen_id,
            total_cost_inr=total_cost,
            rationale=rationale,
            cited_entry_ids=cited_entries,
            rejected_options=rejected_list,
            confidence=confidence,
            notify_list=[],  # Routed in next phase by Notification Router
        )

        # 5. Grounding Validation Gate
        validator = GroundingValidator(board)
        val_result = validator.validate(decision_payload)
        if not val_result.is_valid:
            # Enforce grounded fallback
            decision_payload.rationale = (
                f"{action.value} option {chosen_id} chosen based on cost and viability analysis. "
                f"Justified by Blackboard entries: {', '.join(cited_entries)}."
            )

        entry = await board.post_entry(
            EntryType.DECISION,
            decision_payload.model_dump(),
            confidence=confidence,
            evidence=[],
        )

        if span and tracer:
            tracer.end_span(
                span,
                status="SUCCESS",
                tokens=llm_resp.get("tokens"),
                tool_calls=["list_entries", "get_entry"],
            )

        return [entry]
