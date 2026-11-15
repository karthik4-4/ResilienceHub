"""
Monitor Agent: Parses disruption reports, classifies disruption type,
normalizes items/sites against master data, and posts signals to the Blackboard.
"""

from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Optional

from scdrc.agents.base import BaseAgent
from scdrc.core.schemas import (
    AgentName,
    Entry,
    EntryType,
    DisruptionProfilePayload,
    AffectedItemsPayload,
    AffectedSitesPayload,
    AffectedItem,
    AffectedSite,
    DisruptionType,
    Evidence,
)
from scdrc.core.blackboard import BlackboardView
from scdrc.data.repositories import (
    ItemRepository,
    SiteRepository,
    SQLiteItemRepository,
    SQLiteSiteRepository,
)
from scdrc.observability.tracing import Tracer


class MonitorAgent(BaseAgent):
    """Parses incoming disruption reports and posts profile, affected items, and sites."""

    def __init__(
        self,
        item_repo: Optional[ItemRepository] = None,
        site_repo: Optional[SiteRepository] = None,
        **kwargs,
    ):
        super().__init__(AgentName.MONITOR, **kwargs)
        self.item_repo = item_repo or SQLiteItemRepository(self.settings.paths.database_url.replace("sqlite:///", ""))
        self.site_repo = site_repo or SQLiteSiteRepository(self.settings.paths.database_url.replace("sqlite:///", ""))

    async def run(self, board: BlackboardView, tracer: Optional[Tracer] = None) -> List[Entry]:
        span = tracer.start_span(self.agent_name) if tracer else None
        report_text = board.report.text

        messages = [
            {"role": "system", "content": self.prompt_template},
            {
                "role": "user",
                "content": f"Parse the following disruption report and extract entities in JSON format:\n\n{report_text}",
            },
        ]

        llm_resp = await self.call_llm(messages, response_format={"type": "json_object"})
        raw_content = llm_resp.get("content", "{}")

        try:
            parsed = json.loads(raw_content)
        except Exception:
            # Rule-based fallback
            parsed = self._rule_based_fallback(report_text)

        # Entity normalization against master data
        normalized_items, unresolved_items = self._normalize_items(parsed.get("items", []), report_text)
        normalized_sites, unresolved_sites = self._normalize_sites(parsed.get("sites", []), report_text)

        # Determine overall confidence
        confidence = 0.95
        if unresolved_items or unresolved_sites:
            confidence = 0.65
        if not normalized_items and not normalized_sites:
            confidence = 0.40

        # Construct payloads
        disruption_type_str = parsed.get("disruption_type", "UNKNOWN")
        try:
            disruption_type = DisruptionType(disruption_type_str)
        except ValueError:
            disruption_type = DisruptionType.UNKNOWN

        profile_payload = DisruptionProfilePayload(
            disruption_type=disruption_type,
            severity=int(parsed.get("severity", 3)),
            start_date=parsed.get("start_date"),
            expected_duration_days=int(parsed.get("expected_duration_days", 5)),
            source_text=report_text,
            root_cause=parsed.get("root_cause", "Disruption reported via monitoring channel"),
        )

        items_payload = AffectedItemsPayload(
            items=normalized_items,
            unresolved_tokens=unresolved_items + parsed.get("unresolved_tokens", []),
        )

        sites_payload = AffectedSitesPayload(
            sites=normalized_sites,
            unresolved_tokens=unresolved_sites + parsed.get("unresolved_tokens", []),
        )

        evidence = [
            Evidence(
                evidence_id="EV-MON-001",
                source_type="MANUAL",
                citation="Disruption Report Raw Ingestion",
                snippet=report_text[:200],
            )
        ]

        # Post the three typed entries
        e1 = await board.post_entry(
            EntryType.DISRUPTION_PROFILE,
            profile_payload.model_dump(),
            confidence=confidence,
            evidence=evidence,
        )

        e2 = await board.post_entry(
            EntryType.AFFECTED_ITEMS,
            items_payload.model_dump(),
            confidence=confidence,
            evidence=evidence,
        )

        e3 = await board.post_entry(
            EntryType.AFFECTED_SITES,
            sites_payload.model_dump(),
            confidence=confidence,
            evidence=evidence,
        )

        if span and tracer:
            tracer.end_span(
                span,
                status="SUCCESS",
                tokens=llm_resp.get("tokens"),
                tool_calls=["lookup_item", "lookup_site"],
            )

        return [e1, e2, e3]

    def _normalize_items(self, items: List[Dict[str, Any]], text: str) -> tuple[List[AffectedItem], List[str]]:
        normalized: List[AffectedItem] = []
        unresolved: List[str] = []

        # If LLM didn't find items, search text for known SKUs
        if not items:
            for item in self.item_repo.list_all():
                if item["sku"].lower() in text.lower():
                    items.append({"sku": item["sku"], "qty_at_risk": 1000})

        for it in items:
            sku = it.get("sku", "")
            db_item = self.item_repo.get_by_sku(sku)
            if db_item:
                normalized.append(
                    AffectedItem(
                        sku=db_item["sku"],
                        name=db_item["name"],
                        qty_at_risk=it.get("qty_at_risk", 1000),
                        criticality=db_item["criticality"],
                    )
                )
            else:
                matches = self.item_repo.search_by_name(sku)
                if matches:
                    db_item = matches[0]
                    normalized.append(
                        AffectedItem(
                            sku=db_item["sku"],
                            name=db_item["name"],
                            qty_at_risk=it.get("qty_at_risk", 1000),
                            criticality=db_item["criticality"],
                        )
                    )
                else:
                    unresolved.append(sku or "unidentified_item")

        return normalized, unresolved

    def _normalize_sites(self, sites: List[Dict[str, Any]], text: str) -> tuple[List[AffectedSite], List[str]]:
        normalized: List[AffectedSite] = []
        unresolved: List[str] = []

        # If LLM didn't find sites, search text for known site IDs or city names
        if not sites:
            for site in self.site_repo.list_all():
                if site["site_id"].lower() in text.lower() or site["city"].lower() in text.lower():
                    sites.append({"site_id": site["site_id"]})

        for st in sites:
            site_id = st.get("site_id", "")
            db_site = self.site_repo.get_by_id(site_id)
            if db_site:
                normalized.append(
                    AffectedSite(
                        site_id=db_site["site_id"],
                        name=db_site["name"],
                        role=db_site["role"],
                        region=db_site["state"],
                    )
                )
            else:
                matches = self.site_repo.search_by_name(site_id)
                if matches:
                    db_site = matches[0]
                    normalized.append(
                        AffectedSite(
                            site_id=db_site["site_id"],
                            name=db_site["name"],
                            role=db_site["role"],
                            region=db_site["state"],
                        )
                    )
                else:
                    unresolved.append(site_id or "unidentified_site")

        return normalized, unresolved

    def _rule_based_fallback(self, text: str) -> Dict[str, Any]:
        """Regex and keyword entity extraction if LLM fails."""
        skus = re.findall(r"SKU-\d{4}", text, re.IGNORECASE)
        sites = re.findall(r"SITE-[A-Z]{3}-\d{2}", text, re.IGNORECASE)

        dtype = "UNKNOWN"
        if "delay" in text.lower() or "supplier" in text.lower():
            dtype = "SUPPLIER_DELAY"
        elif "stockout" in text.lower() or "depleted" in text.lower():
            dtype = "STOCKOUT"
        elif "route" in text.lower() or "expressway" in text.lower() or "block" in text.lower():
            dtype = "ROUTE_BLOCK"

        return {
            "disruption_type": dtype,
            "severity": 4,
            "expected_duration_days": 7,
            "root_cause": "Extracted via rule-based pattern matcher",
            "items": [{"sku": s.upper(), "qty_at_risk": 1000} for s in skus],
            "sites": [{"site_id": st.upper()} for st in sites],
            "unresolved_tokens": [],
        }
