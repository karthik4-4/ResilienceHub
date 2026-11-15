"""
Unit tests for deterministic cost equations, viability filtering, and option ranking.
"""

import pytest
from scdrc.core.schemas import CostBreakdown, MitigationAction
from scdrc.decision.viability import evaluate_viability
from scdrc.decision.scoring import compute_option_cost, rank_mitigation_options


def test_viability_filter_arrival_after_stockout():
    # If option arrives in 14 days, but stock runs out in 4 days, option is NOT viable
    cand = CostBreakdown(
        option_id="REORDER-SUP-009",
        action_type=MitigationAction.REORDER,
        target_entity="SUP-009",
        arrival_days=14,
        is_viable=True,
    )
    evaluated = evaluate_viability(
        candidate=cand,
        days_of_cover=4.0,
        needed_qty=1000,
        supplier_info={"lead_time_days": 14, "qualified": True, "capacity": 5000},
    )
    assert evaluated.is_viable is False
    assert "after projected stockout" in evaluated.non_viability_reason


def test_viability_filter_unqualified_supplier():
    # Probationary / uncertified supplier must fail viability
    cand = CostBreakdown(
        option_id="REORDER-SUP-009",
        action_type=MitigationAction.REORDER,
        target_entity="SUP-009",
        arrival_days=5,
        is_viable=True,
    )
    evaluated = evaluate_viability(
        candidate=cand,
        days_of_cover=10.0,
        needed_qty=1000,
        supplier_info={
            "lead_time_days": 5,
            "qualified": False,
            "disqualification_reason": "Excluded per exclusivity clause 4.2",
        },
    )
    assert evaluated.is_viable is False
    assert "clause 4.2" in evaluated.non_viability_reason


def test_compute_option_cost_reorder():
    cand = CostBreakdown(
        option_id="REORDER-SUP-004",
        action_type=MitigationAction.REORDER,
        target_entity="SUP-004",
        arrival_days=5,
        is_viable=True,
    )
    costed = compute_option_cost(
        option=cand,
        needed_qty=1000,
        item_unit_cost=1450.0,
        days_of_cover=10.0,
        supplier_info={"unit_price_inr": 1520.0, "lead_time_days": 5, "moq": 300},
        rates={"daily_holding_factor": 0.00055},
    )
    assert costed.purchase_cost_inr == 1520000.0  # 1000 * 1520
    assert costed.freight_cost_inr == 35000.0     # 1000 * 35
    assert costed.total_cost_inr > 1555000.0


def test_cheapest_viable_ranking():
    # Option A: cheaper but non-viable (arrives too late)
    opt_a = CostBreakdown(
        option_id="REORDER-SUP-009",
        action_type=MitigationAction.REORDER,
        target_entity="SUP-009",
        total_cost_inr=1200000.0,
        is_viable=False,
        non_viability_reason="Arrives after stockout",
    )
    # Option B: viable, moderate cost
    opt_b = CostBreakdown(
        option_id="REORDER-SUP-004",
        action_type=MitigationAction.REORDER,
        target_entity="SUP-004",
        total_cost_inr=1842000.0,
        is_viable=True,
    )
    # Option C: viable, high cost
    opt_c = CostBreakdown(
        option_id="REORDER-SUP-012",
        action_type=MitigationAction.REORDER,
        target_entity="SUP-012",
        total_cost_inr=2100000.0,
        is_viable=True,
    )

    best, viable_ranked, rejected = rank_mitigation_options([opt_a, opt_b, opt_c])

    # Best must be Option B (cheapest VIABLE, ignoring non-viable opt_a)
    assert best.option_id == "REORDER-SUP-004"
    assert len(viable_ranked) == 2
    assert len(rejected) == 1
    assert rejected[0].option_id == "REORDER-SUP-009"
