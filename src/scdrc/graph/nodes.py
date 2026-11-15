"""
LangGraph Specialist Agent Nodes for SCDRC.
Each node encapsulates a specialist agent interacting with the shared Blackboard.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict

from scdrc.core.schemas import AgentName, CaseStatus, EntryType, DegradedPayload, DecisionPayload
from scdrc.core.blackboard import BlackboardView
from scdrc.agents.monitor_agent import MonitorAgent
from scdrc.agents.inventory_agent import InventoryAgent
from scdrc.agents.supplier_agent import SupplierAgent
from scdrc.agents.route_agent import RouteAgent
from scdrc.agents.cost_agent import CostAgent
from scdrc.agents.coordinator_agent import CoordinatorAgent
from scdrc.notify.router import NotificationRouter
from scdrc.graph.state import BlackboardGraphState

logger = logging.getLogger(__name__)


async def monitor_node(state: BlackboardGraphState) -> Dict[str, Any]:
    """Node 1: Monitor Agent extracts disruption profile and affected entities."""
    board = state["board"]
    tracer = state.get("tracer")
    board.set_status(CaseStatus.GATHERING, reason="Phase 1: Monitor extraction")

    agent = MonitorAgent()
    view = BlackboardView(board, AgentName.MONITOR)
    await agent.run(view, tracer=tracer)
    return {"status": "MONITORED"}


async def inventory_node(state: BlackboardGraphState) -> Dict[str, Any]:
    """Node 2A: Inventory Agent evaluates stock levels, buffers, and days of cover."""
    board = state["board"]
    tracer = state.get("tracer")
    failure = state.get("failure_injection", {})

    if failure.get("timeout_agent") == "inventory":
        logger.warning("Simulated timeout injected for Inventory Agent node.")
        await board.post_entry(
            author=AgentName.ORCHESTRATOR,
            entry_type=EntryType.DEGRADED,
            payload=DegradedPayload(
                failed_agent=AgentName.INVENTORY,
                reason="Simulated timeout for Inventory Agent",
            ).model_dump(),
            confidence=0.5,
        )
        return {"is_degraded": True}

    agent = InventoryAgent()
    view = BlackboardView(board, AgentName.INVENTORY)
    try:
        await agent.run(view, tracer=tracer)
    except Exception as e:
        logger.error(f"Inventory Agent node error: {e}")
        await board.post_entry(
            author=AgentName.ORCHESTRATOR,
            entry_type=EntryType.DEGRADED,
            payload=DegradedPayload(
                failed_agent=AgentName.INVENTORY,
                reason=str(e),
            ).model_dump(),
            confidence=0.5,
        )
        return {"is_degraded": True}

    return {}


async def supplier_node(state: BlackboardGraphState) -> Dict[str, Any]:
    """Node 2B: Supplier Agent identifies alternate sources and checks contracts via RAG."""
    board = state["board"]
    tracer = state.get("tracer")
    agent = SupplierAgent()
    view = BlackboardView(board, AgentName.SUPPLIER)
    try:
        await agent.run(view, tracer=tracer)
    except Exception as e:
        logger.error(f"Supplier Agent node error: {e}")
        await board.post_entry(
            author=AgentName.ORCHESTRATOR,
            entry_type=EntryType.DEGRADED,
            payload=DegradedPayload(
                failed_agent=AgentName.SUPPLIER,
                reason=str(e),
            ).model_dump(),
            confidence=0.5,
        )
        return {"is_degraded": True}

    return {}


async def route_node(state: BlackboardGraphState) -> Dict[str, Any]:
    """Node 2C: Route Agent discovers transit corridors and queries advisories via RAG."""
    board = state["board"]
    tracer = state.get("tracer")
    agent = RouteAgent()
    view = BlackboardView(board, AgentName.ROUTE)
    try:
        await agent.run(view, tracer=tracer)
    except Exception as e:
        logger.error(f"Route Agent node error: {e}")
        await board.post_entry(
            author=AgentName.ORCHESTRATOR,
            entry_type=EntryType.DEGRADED,
            payload=DegradedPayload(
                failed_agent=AgentName.ROUTE,
                reason=str(e),
            ).model_dump(),
            confidence=0.5,
        )
        return {"is_degraded": True}

    return {}


async def cost_node(state: BlackboardGraphState) -> Dict[str, Any]:
    """Node 3: Cost Agent evaluates landed costs and viability across candidate options."""
    board = state["board"]
    tracer = state.get("tracer")
    agent = CostAgent()
    view = BlackboardView(board, AgentName.COST)
    try:
        await agent.run(view, tracer=tracer)
    except Exception as e:
        logger.error(f"Cost Agent node error: {e}")
        await board.post_entry(
            author=AgentName.ORCHESTRATOR,
            entry_type=EntryType.DEGRADED,
            payload=DegradedPayload(
                failed_agent=AgentName.COST,
                reason=str(e),
            ).model_dump(),
            confidence=0.5,
        )
        return {"is_degraded": True}

    return {}


async def coordinator_node(state: BlackboardGraphState) -> Dict[str, Any]:
    """Node 4: Coordinator Agent selects cheapest viable mitigation and validates citations."""
    board = state["board"]
    tracer = state.get("tracer")
    board.set_status(CaseStatus.READY, reason="Phase 4: Readiness passed")

    agent = CoordinatorAgent()
    view = BlackboardView(board, AgentName.COORDINATOR)
    await agent.run(view, tracer=tracer)

    decision_entry = board.get_latest_entry_by_type(EntryType.DECISION)
    if not decision_entry:
        board.set_status(CaseStatus.FAILED, reason="Coordinator failed to post DECISION")
        raise RuntimeError("No decision posted by Coordinator")

    board.set_status(CaseStatus.DECIDED, reason="Mitigation decision posted")
    return {"decision": decision_entry.payload}


async def notify_node(state: BlackboardGraphState) -> Dict[str, Any]:
    """Node 5: Notification Router dispatches alerts and saves immutable snapshot."""
    board = state["board"]
    view = BlackboardView(board, AgentName.COORDINATOR)
    decision_payload = DecisionPayload(**state["decision"])

    router = NotificationRouter()
    notifications = router.route_and_dispatch(view, decision_payload)
    return {"notifications": [n.model_dump() for n in notifications]}
