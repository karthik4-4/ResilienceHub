"""
Semantic Kernel Plugin: Cost calculations for candidate mitigation options.
"""

from __future__ import annotations
import json
from semantic_kernel.functions import kernel_function
from scdrc.data.repositories import CostRepository


class CostPlugin:
    """Tools for computing landed cost components for reorder, reroute, and hold."""

    def __init__(self, repo: CostRepository):
        self.repo = repo

    @kernel_function(description="Calculate total landed cost for a REORDER option including purchase, freight, expedite, and holding.")
    def calculate_reorder_cost(
        self,
        qty: int,
        unit_price: float,
        freight_per_unit: float = 25.0,
        expedite_fee: float = 0.0,
        lead_time_days: int = 5,
        holding_rate_annual: float = 0.18,
    ) -> str:
        purchase = qty * unit_price
        freight = qty * freight_per_unit
        holding = purchase * (holding_rate_annual / 365.0) * lead_time_days
        total = purchase + freight + expedite_fee + holding
        return json.dumps({
            "purchase_cost": round(purchase, 2),
            "freight_cost": round(freight, 2),
            "expedite_fee": round(expedite_fee, 2),
            "holding_cost": round(holding, 2),
            "total_cost": round(total, 2),
        })

    @kernel_function(description="Calculate differential cost for REROUTE option including extra freight and transit delay holding.")
    def calculate_reroute_cost(
        self,
        qty: int,
        unit_value: float,
        extra_freight_per_unit: float,
        added_transit_days: int,
        holding_rate_annual: float = 0.18,
    ) -> str:
        freight = qty * extra_freight_per_unit
        holding = (qty * unit_value) * (holding_rate_annual / 365.0) * added_transit_days
        total = freight + holding
        return json.dumps({
            "extra_freight_cost": round(freight, 2),
            "delay_holding_cost": round(holding, 2),
            "total_cost": round(total, 2),
        })
