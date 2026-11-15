"""
Cost calculation models and multi-criteria ranking engine for mitigation options.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from scdrc.core.schemas import CostBreakdown, MitigationAction


def compute_option_cost(
    option: CostBreakdown,
    needed_qty: int,
    item_unit_cost: float,
    days_of_cover: float,
    supplier_info: Optional[Dict[str, Any]] = None,
    route_info: Optional[Dict[str, Any]] = None,
    rates: Optional[Dict[str, Any]] = None,
) -> CostBreakdown:
    """Compute all cost components deterministically for a mitigation option."""
    rates = rates or {}
    daily_holding_factor = float(rates.get("daily_holding_factor", 0.00055))
    stockout_penalty_per_unit_day = float(rates.get("stockout_penalty_per_unit_day", 250.0))
    expedite_base_fee = float(rates.get("expedite_base_fee_inr", 25000.0))

    supplier_info = supplier_info or {}
    route_info = route_info or {}

    assumptions: List[str] = []

    # 1. REORDER Option Cost
    if option.action_type == MitigationAction.REORDER:
        unit_price = float(supplier_info.get("unit_price_inr", item_unit_cost))
        lead_time = int(supplier_info.get("lead_time_days", option.arrival_days))
        moq = int(supplier_info.get("moq", 500))
        order_qty = max(needed_qty, moq)

        purchase = order_qty * unit_price
        freight = order_qty * 35.0  # standard base road/rail freight per unit
        expedite = expedite_base_fee if lead_time <= 3 else 0.0
        holding = purchase * daily_holding_factor * lead_time

        # Stockout penalty if arrival exceeds cover
        shortfall_days = max(0.0, lead_time - days_of_cover)
        penalty = shortfall_days * order_qty * (stockout_penalty_per_unit_day * 0.2)

        total = purchase + freight + expedite + holding + penalty

        option.purchase_cost_inr = round(purchase, 2)
        option.freight_cost_inr = round(freight, 2)
        option.expedite_fee_inr = round(expedite, 2)
        option.holding_cost_inr = round(holding, 2)
        option.stockout_penalty_inr = round(penalty, 2)
        option.total_cost_inr = round(total, 2)
        option.arrival_days = lead_time

        assumptions.append(f"Order quantity: {order_qty} (MOQ: {moq}) at INR {unit_price:.2f}/unit")
        assumptions.append(f"Holding cost for {lead_time} days lead time: INR {holding:.2f}")
        if penalty > 0:
            assumptions.append(f"Stockout risk penalty for {shortfall_days:.1f} days shortfall: INR {penalty:.2f}")

    # 2. REROUTE Option Cost
    elif option.action_type == MitigationAction.REROUTE:
        freight_per_unit = float(route_info.get("freight_cost_per_unit_inr", 25.0))
        transit_days = int(route_info.get("transit_days", option.arrival_days))
        added_delay = int(route_info.get("added_delay_days", 2))

        freight = needed_qty * freight_per_unit
        holding = (needed_qty * item_unit_cost) * daily_holding_factor * added_delay

        shortfall_days = max(0.0, added_delay - days_of_cover)
        penalty = shortfall_days * needed_qty * (stockout_penalty_per_unit_day * 0.5)

        total = freight + holding + penalty

        option.purchase_cost_inr = 0.0
        option.freight_cost_inr = round(freight, 2)
        option.expedite_fee_inr = 0.0
        option.holding_cost_inr = round(holding, 2)
        option.stockout_penalty_inr = round(penalty, 2)
        option.total_cost_inr = round(total, 2)
        option.arrival_days = transit_days

        assumptions.append(f"Freight cost on alternative route {option.target_entity}: INR {freight:.2f}")
        assumptions.append(f"Delay holding cost for {added_delay} days: INR {holding:.2f}")

    # 3. HOLD Option Cost
    elif option.action_type == MitigationAction.HOLD:
        wait_days = option.arrival_days
        holding = (needed_qty * item_unit_cost) * daily_holding_factor * wait_days

        shortfall_days = max(0.0, wait_days - days_of_cover)
        penalty = shortfall_days * needed_qty * stockout_penalty_per_unit_day

        total = holding + penalty

        option.purchase_cost_inr = 0.0
        option.freight_cost_inr = 0.0
        option.expedite_fee_inr = 0.0
        option.holding_cost_inr = round(holding, 2)
        option.stockout_penalty_inr = round(penalty, 2)
        option.total_cost_inr = round(total, 2)

        assumptions.append(f"Buffer holding cost while waiting {wait_days} days: INR {holding:.2f}")
        if penalty > 0:
            assumptions.append(f"Imminent stockout penalty for unmitigated delay: INR {penalty:.2f}")

    option.assumptions = assumptions
    return option


def rank_mitigation_options(
    options: List[CostBreakdown],
    supplier_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[Optional[CostBreakdown], List[CostBreakdown], List[CostBreakdown]]:
    """
    Ranks options:
    1. Splits into viable and non-viable.
    2. Sorts viable options by total_cost_inr ASC.
    3. Returns (best_viable_option, viable_options_ranked, rejected_options).
    """
    supplier_map = supplier_map or {}

    viable = [o for o in options if o.is_viable]
    rejected = [o for o in options if not o.is_viable]

    def sort_key(opt: CostBreakdown):
        rel = 0.90
        if opt.target_entity in supplier_map:
            rel = float(supplier_map[opt.target_entity].get("reliability_score", 0.90))
        # Primary: total_cost ASC, Secondary: reliability DESC, Tertiary: arrival days ASC
        return (opt.total_cost_inr, -rel, opt.arrival_days)

    viable_ranked = sorted(viable, key=sort_key)
    best_option = viable_ranked[0] if viable_ranked else None

    return best_option, viable_ranked, rejected
