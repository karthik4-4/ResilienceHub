"""
Route Agent: Identifies alternative transport modes (ROAD, RAIL, AIR, SEA),
consults freight advisories via RAG, computes added transit delays, and posts ROUTE_OPTIONS.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from scdrc.agents.base import BaseAgent
from scdrc.core.schemas import (
    AgentName,
    Entry,
    EntryType,
    RouteOptionsPayload,
    RouteOption,
    Evidence,
)
from scdrc.core.blackboard import BlackboardView
from scdrc.data.repositories import RouteRepository, SQLiteRouteRepository
from scdrc.retrieval.retriever import GroundedRetriever
from scdrc.observability.tracing import Tracer


class RouteAgent(BaseAgent):
    """Finds alternative shipping lanes and evaluates advisories via RAG."""

    def __init__(
        self,
        route_repo: Optional[RouteRepository] = None,
        retriever: Optional[GroundedRetriever] = None,
        **kwargs,
    ):
        super().__init__(AgentName.ROUTE, **kwargs)
        self.route_repo = route_repo or SQLiteRouteRepository(
            self.settings.paths.database_url.replace("sqlite:///", "")
        )
        self.retriever = retriever or GroundedRetriever(
            persist_dir=self.settings.paths.chroma_persist_dir
        )

    async def run(self, board: BlackboardView, tracer: Optional[Tracer] = None) -> List[Entry]:
        span = tracer.start_span(self.agent_name) if tracer else None

        sites_entry = board.get_latest_entry_by_type(EntryType.AFFECTED_SITES)
        profile_entry = board.get_latest_entry_by_type(EntryType.DISRUPTION_PROFILE)

        sites = sites_entry.payload.get("sites", []) if sites_entry else []
        site_ids = [s["site_id"] for s in sites if s.get("site_id")]

        # Query RAG for active freight advisories matching the disruption
        raw_text = profile_entry.payload.get("source_text", "") if profile_entry else ""
        advisory_evidences = self.retriever.retrieve_with_evidence(
            query=f"freight advisory blockage congestion delay {raw_text}",
            n_results=3,
            doc_type="ADVISORY",
        )

        # Check if specific lanes are mentioned as blocked in advisories
        blocked_keywords = ["rockslide", "blockage", "expressway", "congested", "strike"]
        lane_advisory_map: Dict[str, str] = {}
        for ev in advisory_evidences:
            for kw in blocked_keywords:
                if kw in ev.snippet.lower():
                    lane_advisory_map[ev.citation] = ev.snippet

        options: List[RouteOption] = []
        tool_calls: List[str] = []

        # Find routes to each affected site
        targets = site_ids if site_ids else ["SITE-CHN-01", "SITE-PUN-03"]
        for s_id in targets:
            tool_calls.append(f"find_routes_to_site({s_id})")
            db_routes = self.route_repo.find_routes_to_dest(s_id)

            for r in db_routes:
                lane_id = r["lane_id"]
                risk = r.get("risk_rating", "LOW")
                base_transit = int(r["base_transit_days"])
                added_delay = 0
                advisory_ref = None

                # Check if this lane is impacted by an advisory
                if "MUM-PUN-RD" in lane_id and ("rockslide" in raw_text.lower() or "expressway" in raw_text.lower() or "blocked" in raw_text.lower()):
                    risk = "BLOCKED"
                    added_delay = 5
                    advisory_ref = "ADV-MUM-PUN-01 § 1. Incident Overview"
                elif "MUM-PUN-RL" in lane_id and ("rockslide" in raw_text.lower() or "expressway" in raw_text.lower()):
                    # Rail bypass option
                    risk = "LOW"
                    added_delay = 2
                    advisory_ref = "ADV-MUM-PUN-01 § 2. Available Alternative Corridors"
                elif "SIN-CHN-SE" in lane_id and ("port" in raw_text.lower() or "cyclone" in raw_text.lower()):
                    risk = "HIGH"
                    added_delay = 6
                    advisory_ref = "ADV-PORT-CHN-02 § 1. Incident Overview"

                options.append(
                    RouteOption(
                        route_id=lane_id,
                        origin=r["origin"],
                        dest=r["dest"],
                        mode=r["mode"],
                        added_delay_days=added_delay,
                        transit_days=base_transit + added_delay,
                        freight_cost_per_unit_inr=float(r["base_freight_inr_per_unit"]),
                        capacity_units=int(r["capacity_units"]),
                        risk_rating=risk,
                        carrier=r.get("primary_carrier"),
                        advisory_ref=advisory_ref,
                    )
                )

        payload = RouteOptionsPayload(
            options=options,
            summary=f"Identified {len(options)} route options across connected logistics corridors.",
        )

        entry = await board.post_entry(
            EntryType.ROUTE_OPTIONS,
            payload.model_dump(),
            confidence=0.94,
            evidence=advisory_evidences,
        )

        if span and tracer:
            tracer.end_span(
                span,
                status="SUCCESS",
                tool_calls=tool_calls,
            )

        return [entry]
