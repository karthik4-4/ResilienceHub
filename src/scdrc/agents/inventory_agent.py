"""
Inventory Agent: Pulls on-hand, in-transit, and safety stock, computes
days of cover deterministically, and posts INVENTORY_STATUS.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from scdrc.agents.base import BaseAgent
from scdrc.core.schemas import (
    AgentName,
    Entry,
    EntryType,
    InventoryStatusPayload,
    SiteInventoryItem,
    InventoryStatusType,
    Evidence,
)
from scdrc.core.blackboard import BlackboardView
from scdrc.data.repositories import InventoryRepository, SQLiteInventoryRepository
from scdrc.observability.tracing import Tracer


class InventoryAgent(BaseAgent):
    """Pulls stock, computes cover, and classifies stockout risk."""

    def __init__(
        self,
        inv_repo: Optional[InventoryRepository] = None,
        **kwargs,
    ):
        super().__init__(AgentName.INVENTORY, **kwargs)
        self.inv_repo = inv_repo or SQLiteInventoryRepository(
            self.settings.paths.database_url.replace("sqlite:///", "")
        )

    async def run(self, board: BlackboardView, tracer: Optional[Tracer] = None) -> List[Entry]:
        span = tracer.start_span(self.agent_name) if tracer else None

        items_entry = board.get_latest_entry_by_type(EntryType.AFFECTED_ITEMS)
        sites_entry = board.get_latest_entry_by_type(EntryType.AFFECTED_SITES)

        items = items_entry.payload.get("items", []) if items_entry else []
        sites = sites_entry.payload.get("sites", []) if sites_entry else []

        # If no specific sites found, scan all sites for the affected items
        site_ids = [s["site_id"] for s in sites if s.get("site_id")]
        sku_list = [i["sku"] for i in items if i.get("sku")]

        inventory_results: List[SiteInventoryItem] = []
        evidence_list: List[Evidence] = []
        tool_calls: List[str] = []

        ev_idx = 0
        for sku in sku_list:
            if site_ids:
                targets = site_ids
            else:
                # Find all sites that stock this SKU
                all_site_records = self.inv_repo.get_all_by_sku(sku)
                targets = [r["site_id"] for r in all_site_records]

            for s_id in targets:
                tool_calls.append(f"get_inventory({sku}, {s_id})")
                inv_data = self.inv_repo.get_inventory(sku, s_id)
                if not inv_data:
                    continue

                tool_calls.append(f"get_in_transit({sku}, {s_id})")
                in_transit_shipments = self.inv_repo.get_in_transit(sku, s_id)
                usable_in_transit = sum(
                    sh["qty"] for sh in in_transit_shipments if sh.get("status") in ["ON_SCHEDULE", "IN_TRANSIT"]
                )

                on_hand = int(inv_data["on_hand"])
                safety_stock = int(inv_data["safety_stock"])
                daily_demand = float(inv_data["daily_demand"])

                # Deterministic formula: cover = (on_hand + usable_in_transit) / daily_demand
                days_of_cover = (on_hand + usable_in_transit) / daily_demand if daily_demand > 0 else 999.0

                # Status classification
                if on_hand == 0:
                    status = InventoryStatusType.STOCKED_OUT
                elif days_of_cover < 7.0:
                    status = InventoryStatusType.STOCKOUT_RISK
                elif on_hand < safety_stock:
                    status = InventoryStatusType.BELOW_SAFETY
                else:
                    status = InventoryStatusType.OK

                ev_idx += 1
                evidence_list.append(
                    Evidence(
                        evidence_id=f"EV-INV-{ev_idx:03d}",
                        source_type="DATABASE",
                        citation=f"inventory table ({sku} @ {s_id})",
                        snippet=f"on_hand={on_hand}, safety_stock={safety_stock}, demand={daily_demand}/day, in_transit={usable_in_transit}",
                    )
                )

                inventory_results.append(
                    SiteInventoryItem(
                        sku=sku,
                        site_id=s_id,
                        on_hand=on_hand,
                        in_transit=usable_in_transit,
                        safety_stock=safety_stock,
                        daily_demand=daily_demand,
                        days_of_cover=round(days_of_cover, 1),
                        status=status,
                    )
                )

        summary_lines = [
            f"{r.sku} @ {r.site_id}: {r.days_of_cover:.1f} days cover (Status: {r.status.value})"
            for r in inventory_results
        ]
        summary = "; ".join(summary_lines) if summary_lines else "No inventory records located for affected items."

        payload = InventoryStatusPayload(
            inventory=inventory_results,
            summary=summary,
        )

        entry = await board.post_entry(
            EntryType.INVENTORY_STATUS,
            payload.model_dump(),
            confidence=0.98,
            evidence=evidence_list,
        )

        if span and tracer:
            tracer.end_span(
                span,
                status="SUCCESS",
                tool_calls=tool_calls,
            )

        return [entry]
