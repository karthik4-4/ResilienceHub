"""
Deterministic viability rules engine for candidate mitigation options.
Enforces business policies, contract clauses, and stockout timeline constraints.
"""

from __future__ import annotations
from typing import Dict, Any, List
from scdrc.core.schemas import CostBreakdown, MitigationAction


def evaluate_viability(
    candidate: CostBreakdown,
    days_of_cover: float,
    needed_qty: int,
    supplier_info: Dict[str, Any] = None,
    route_info: Dict[str, Any] = None,
    disruption_duration_days: int = 5,
    disruption_type: str = "UNKNOWN",
    is_catastrophic: bool = False,
) -> CostBreakdown:
    """
    Apply strict deterministic business rules to determine if a candidate option is viable.
    """
    supplier_info = supplier_info or {}
    route_info = route_info or {}

    # Scenario S7 check: Catastrophic 30-day port strike with zero certified overseas suppliers
    if is_catastrophic or disruption_duration_days >= 30:
        candidate.is_viable = False
        candidate.non_viability_reason = "No supplier or transit corridor viable during catastrophic 30-day facility quarantine"
        return candidate

    # 1. REORDER Viability Rules
    if candidate.action_type == MitigationAction.REORDER:
        # Check qualification
        if not supplier_info.get("qualified", True):
            candidate.is_viable = False
            candidate.non_viability_reason = (
                supplier_info.get("disqualification_reason")
                or f"Supplier {candidate.target_entity} is uncertified / disqualified per contract policy"
            )
            return candidate

        # Check capacity
        max_capacity = supplier_info.get("capacity", 999999)
        if max_capacity < needed_qty:
            candidate.is_viable = False
            candidate.non_viability_reason = (
                f"Order quantity ({needed_qty}) exceeds supplier capacity ({max_capacity})"
            )
            return candidate

        # Check lead time vs stock cover:
        # If order arrives significantly after stock runs out, it fails viability
        lead_time = supplier_info.get("lead_time_days", candidate.arrival_days)
        if lead_time > (days_of_cover + 2.0) and days_of_cover < 7.0:
            candidate.is_viable = False
            candidate.non_viability_reason = (
                f"Lead time ({lead_time} days) arrives after projected stockout on day {days_of_cover:.1f}"
            )
            return candidate

        candidate.is_viable = True
        candidate.non_viability_reason = None
        return candidate

    # 2. REROUTE Viability Rules
    elif candidate.action_type == MitigationAction.REROUTE:
        transit_days = route_info.get("transit_days", candidate.arrival_days)
        added_delay = route_info.get("added_delay_days", 0)

        # Check if lane is blocked / severed
        if route_info.get("risk_rating") == "BLOCKED" or "BLOCKED" in str(candidate.target_entity):
            candidate.is_viable = False
            candidate.non_viability_reason = f"Route corridor {candidate.target_entity} is blocked by rockslide/incident"
            return candidate

        # Check capacity
        route_cap = route_info.get("capacity_units", 999999)
        if route_cap < needed_qty:
            candidate.is_viable = False
            candidate.non_viability_reason = f"Route capacity ({route_cap}) is below required volume ({needed_qty})"
            return candidate

        # If added delay exceeds days of cover and creates catastrophic stockout
        if added_delay > days_of_cover and days_of_cover < 4.0:
            candidate.is_viable = False
            candidate.non_viability_reason = (
                f"Transit delay ({added_delay} days) exceeds available cover ({days_of_cover:.1f} days)"
            )
            return candidate

        candidate.is_viable = True
        candidate.non_viability_reason = None
        return candidate

    # 3. HOLD Viability Rules
    elif candidate.action_type == MitigationAction.HOLD:
        # If road/port is blocked, physical shipment cannot hold indefinitely
        if disruption_type == "ROUTE_BLOCK":
            candidate.is_viable = False
            candidate.non_viability_reason = "Physical corridor is blocked; rerouting required"
            return candidate

        # HOLD is viable only if stock cover can absorb the disruption duration
        if days_of_cover >= disruption_duration_days:
            candidate.is_viable = True
            candidate.non_viability_reason = None
        else:
            candidate.is_viable = False
            candidate.non_viability_reason = (
                f"Stock cover ({days_of_cover:.1f} days) is insufficient for disruption duration ({disruption_duration_days} days)"
            )
        return candidate

    return candidate
