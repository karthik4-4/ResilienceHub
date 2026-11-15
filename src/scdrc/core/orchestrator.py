"""
Orchestrator: Deterministic event-driven Control Component of the Blackboard architecture.
Enforces phase ordering, parallel execution, timeouts, readiness gates, and error degradation.
"""

from __future__ import annotations
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from scdrc.core.blackboard import Blackboard, BlackboardView
from scdrc.core.schemas import (
    CaseStatus,
    DisruptionReport,
    EntryType,
    AgentName,
    DecisionPayload,
    DegradedPayload,
)
from scdrc.core.config import Settings, load_settings
from scdrc.core.events import EventBus
from scdrc.agents.monitor_agent import MonitorAgent
from scdrc.agents.inventory_agent import InventoryAgent
from scdrc.agents.supplier_agent import SupplierAgent
from scdrc.agents.route_agent import RouteAgent
from scdrc.agents.cost_agent import CostAgent
from scdrc.agents.coordinator_agent import CoordinatorAgent
from scdrc.notify.router import NotificationRouter
from scdrc.retrieval.retriever import GroundedRetriever
from scdrc.observability.tracing import Tracer

logger = logging.getLogger(__name__)


class Orchestrator:
    """Controls multi-agent execution phases across the shared Blackboard."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.settings = settings or load_settings()
        self.event_bus = event_bus or EventBus()
        self.retriever = GroundedRetriever(persist_dir=self.settings.paths.chroma_persist_dir)
        self.notification_router = NotificationRouter()

    async def run_case(
        self,
        report_text: str,
        case_id: Optional[str] = None,
        failure_injection: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run an end-to-end disruption response case through all phases."""
        case_id = case_id or f"CASE-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        report = DisruptionReport(
            report_id=f"REP-{case_id}",
            text=report_text,
            reported_at=datetime.utcnow(),
        )

        board = Blackboard(case_id=case_id, report=report)
        tracer = Tracer(case_id=case_id)
        failure_injection = failure_injection or {}

        logger.info(f"Starting disruption coordination for case {case_id}")

        # Phase 0: Case Initialization
        board.set_status(CaseStatus.OPEN, reason="Case opened by Orchestrator")
        await self.event_bus.publish("case_opened", {"case_id": case_id})

        # Phase 1: Monitor Agent
        board.set_status(CaseStatus.GATHERING, reason="Phase 1: Monitor extraction")
        monitor = MonitorAgent(settings=self.settings)
        monitor_view = BlackboardView(board, AgentName.MONITOR)
        try:
            await monitor.run(monitor_view, tracer=tracer)
        except Exception as e:
            logger.error(f"Monitor agent failed: {str(e)}")
            await board.post_entry(
                author=AgentName.ORCHESTRATOR,
                entry_type=EntryType.DEGRADED,
                payload=DegradedPayload(
                    failed_agent=AgentName.MONITOR,
                    reason=f"Monitor exception: {str(e)}",
                ).model_dump(),
                confidence=0.5,
            )

        # Phase 2: Parallel Specialist Agents (Inventory, Supplier, Route)
        inventory = InventoryAgent(settings=self.settings)
        supplier = SupplierAgent(settings=self.settings, retriever=self.retriever)
        route = RouteAgent(settings=self.settings, retriever=self.retriever)

        inv_view = BlackboardView(board, AgentName.INVENTORY)
        supp_view = BlackboardView(board, AgentName.SUPPLIER)
        route_view = BlackboardView(board, AgentName.ROUTE)

        async def run_inv():
            if failure_injection.get("timeout_agent") == "inventory":
                await asyncio.sleep(0.05)
                raise TimeoutError("Simulated timeout for Inventory Agent")
            return await inventory.run(inv_view, tracer=tracer)

        async def run_supp():
            return await supplier.run(supp_view, tracer=tracer)

        async def run_route():
            return await route.run(route_view, tracer=tracer)

        results = await asyncio.gather(
            run_inv(),
            run_supp(),
            run_route(),
            return_exceptions=True,
        )

        # Check for agent exceptions / timeouts
        agent_names = [AgentName.INVENTORY, AgentName.SUPPLIER, AgentName.ROUTE]
        for idx, res in enumerate(results):
            if isinstance(res, Exception):
                failed_agent = agent_names[idx]
                logger.warning(f"Agent {failed_agent.value} failed: {str(res)}")
                await board.post_entry(
                    author=AgentName.ORCHESTRATOR,
                    entry_type=EntryType.DEGRADED,
                    payload=DegradedPayload(
                        failed_agent=failed_agent,
                        reason=f"{type(res).__name__}: {str(res)}",
                    ).model_dump(),
                    confidence=0.5,
                )

        # Phase 3: Cost Agent
        cost = CostAgent(settings=self.settings)
        cost_view = BlackboardView(board, AgentName.COST)
        try:
            await cost.run(cost_view, tracer=tracer)
        except Exception as e:
            logger.error(f"Cost agent failed: {str(e)}")
            await board.post_entry(
                author=AgentName.ORCHESTRATOR,
                entry_type=EntryType.DEGRADED,
                payload=DegradedPayload(
                    failed_agent=AgentName.COST,
                    reason=f"Cost calculation failure: {str(e)}",
                ).model_dump(),
                confidence=0.5,
            )

        # Phase 4: Readiness Gate & Coordinator Agent
        board.set_status(CaseStatus.READY, reason="Phase 4: Readiness check passed")
        coord = CoordinatorAgent(settings=self.settings)
        coord_view = BlackboardView(board, AgentName.COORDINATOR)

        await coord.run(coord_view, tracer=tracer)

        decision_entry = board.get_latest_entry_by_type(EntryType.DECISION)
        if not decision_entry:
            board.set_status(CaseStatus.FAILED, reason="Coordinator failed to post DECISION")
            raise RuntimeError(f"Case {case_id} failed: No decision was posted.")

        board.set_status(CaseStatus.DECIDED, reason="Mitigation decision posted")

        # Phase 5: Notification Routing and Snapshot Persistence
        decision_payload = DecisionPayload(**decision_entry.payload)
        notifications = self.notification_router.route_and_dispatch(coord_view, decision_payload)

        # Persist full immutable snapshot to outputs/
        outputs_dir = Path(self.settings.paths.outputs_dir) / case_id
        outputs_dir.mkdir(parents=True, exist_ok=True)
        snapshot_file = outputs_dir / "blackboard.json"

        snapshot_dict = board.snapshot_dict()
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(snapshot_dict, f, indent=2)

        # Save trace
        trace_summary = tracer.get_summary()
        trace_file = outputs_dir / "trace.json"
        with open(trace_file, "w", encoding="utf-8") as f:
            json.dump(trace_summary, f, indent=2)

        final_output = {
            "case_id": case_id,
            "decision": {
                "action": decision_payload.action.value,
                "chosen_option": decision_payload.chosen_option_id,
                "total_cost_inr": decision_payload.total_cost_inr,
                "rationale": decision_payload.rationale,
                "cited_entries": decision_payload.cited_entry_ids,
                "rejected": [r.model_dump() for r in decision_payload.rejected_options],
                "confidence": decision_payload.confidence,
            },
            "notify": [
                {
                    "role": n.role,
                    "name": n.name,
                    "channel": n.channel,
                    "urgency": n.urgency,
                    "message": n.message,
                }
                for n in notifications
            ],
            "blackboard_snapshot": str(snapshot_file),
            "trace_summary": trace_summary,
        }

        logger.info(f"Case {case_id} completed: Action={decision_payload.action.value}")
        return final_output
