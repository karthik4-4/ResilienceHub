"""
Semantic Kernel Plugin: Inventory queries and deterministic calculations.
"""

from __future__ import annotations
import json
from semantic_kernel.functions import kernel_function
from scdrc.data.repositories import InventoryRepository


class InventoryPlugin:
    """Tools for querying stock, in-transit shipments, and computing days of cover."""

    def __init__(self, repo: InventoryRepository):
        self.repo = repo

    @kernel_function(description="Get on-hand stock, safety stock, and daily demand for a SKU at a specific site.")
    def get_stock(self, sku: str, site_id: str) -> str:
        inv = self.repo.get_inventory(sku, site_id)
        if not inv:
            return json.dumps({"error": f"No inventory record for {sku} at {site_id}"})
        return json.dumps(inv, indent=2)

    @kernel_function(description="Get active in-transit shipments destined for a specific SKU and site.")
    def get_in_transit(self, sku: str, site_id: str) -> str:
        shipments = self.repo.get_in_transit(sku, site_id)
        return json.dumps(shipments, indent=2)

    @kernel_function(description="Compute days of cover deterministically given stock and demand rate.")
    def calculate_days_of_cover(self, on_hand: int, in_transit: int, daily_demand: float) -> str:
        if daily_demand <= 0:
            return json.dumps({"days_of_cover": 999.0, "status": "UNKNOWN"})
        cover = (on_hand + in_transit) / daily_demand
        status = "OK" if cover >= 14 else ("BELOW_SAFETY" if cover >= 7 else "STOCKOUT_RISK")
        if on_hand == 0:
            status = "STOCKED_OUT"
        return json.dumps({"days_of_cover": round(cover, 1), "status": status})
