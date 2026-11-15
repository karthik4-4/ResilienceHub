"""
Builds candidate mitigation options (REORDER, REROUTE, HOLD) from Blackboard entries.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from scdrc.core.schemas import (
    MitigationAction,
    CostBreakdown,
    EntryType,
    DisruptionType,
)
from scdrc.core.blackboard import BlackboardView


def build_candidate_options(board: BlackboardView) -> List[CostBreakdown]:
    """
    Extracts affected items, inventory cover, supplier options, and route options
    from the Blackboard and generates candidate mitigation options.
    """
    candidates: List[CostBreakdown] = []

    profile_entry = board.get_latest_entry_by_type(EntryType.DISRUPTION_PROFILE)
    disruption_type = profile_entry.payload.get("disruption_type", "UNKNOWN") if profile_entry else "UNKNOWN"
    disruption_duration = profile_entry.payload.get("expected_duration_days", 5) if profile_entry else 5

    items_entry = board.get_latest_entry_by_type(EntryType.AFFECTED_ITEMS)
    items_list = items_entry.payload.get("items", []) if items_entry else []
    target_sku = items_list[0].get("sku", "SKU-1042") if items_list else "SKU-1042"
    target_qty = items_list[0].get("qty_at_risk", 1000) if items_list else 1000

    inv_entry = board.get_latest_entry_by_type(EntryType.INVENTORY_STATUS)
    inv_list = inv_entry.payload.get("inventory", []) if inv_entry else []

    # Calculate minimum days of cover across all affected items/sites
    min_days_of_cover = 999.0
    for inv in inv_list:
        cover = float(inv.get("days_of_cover", 10.0))
        if cover < min_days_of_cover:
            min_days_of_cover = cover

    if min_days_of_cover == 999.0:
        min_days_of_cover = 10.0

    # A. Candidate REORDER Options (from SUPPLIER_OPTIONS)
    supp_entry = board.get_latest_entry_by_type(EntryType.SUPPLIER_OPTIONS)
    if supp_entry:
        supplier_options = supp_entry.payload.get("options", [])
        for opt in supplier_options:
            cand = CostBreakdown(
                option_id=f"REORDER-{opt['supplier_id']}",
                action_type=MitigationAction.REORDER,
                target_entity=opt["supplier_id"],
                arrival_days=int(opt.get("lead_time_days", 7)),
                is_viable=bool(opt.get("qualified", True)),
                non_viability_reason=opt.get("disqualification_reason"),
            )
            candidates.append(cand)

    # B. Candidate REROUTE Options (from ROUTE_OPTIONS)
    # REROUTE is active when disruption involves route blocks or freight transit
    route_entry = board.get_latest_entry_by_type(EntryType.ROUTE_OPTIONS)
    if route_entry and disruption_type in ["ROUTE_BLOCK"]:
        route_options = route_entry.payload.get("options", [])
        for r_opt in route_options:
            risk = r_opt.get("risk_rating", "LOW")
            is_viable = (risk != "BLOCKED")
            reason = "Lane is blocked by disruption" if not is_viable else None

            cand = CostBreakdown(
                option_id=f"REROUTE-{r_opt['route_id']}",
                action_type=MitigationAction.REROUTE,
                target_entity=r_opt["route_id"],
                arrival_days=int(r_opt.get("transit_days", 3)),
                is_viable=is_viable,
                non_viability_reason=reason,
            )
            candidates.append(cand)

    # C. Candidate HOLD Option
    # HOLD is NOT viable if shipment is stranded by active route block, or if cover < duration
    if disruption_type == "ROUTE_BLOCK":
        hold_is_viable = False
        hold_reason = "Physical corridor is blocked; active transit cannot hold indefinitely without rerouting"
    elif min_days_of_cover < disruption_duration:
        hold_is_viable = False
        hold_reason = f"Minimum inventory cover ({min_days_of_cover:.1f} days) is insufficient for {disruption_duration}-day delay"
    else:
        hold_is_viable = True
        hold_reason = None

    hold_cand = CostBreakdown(
        option_id="HOLD",
        action_type=MitigationAction.HOLD,
        target_entity="HOLD",
        arrival_days=disruption_duration,
        is_viable=hold_is_viable,
        non_viability_reason=hold_reason,
    )
    candidates.append(hold_cand)

    return candidates
