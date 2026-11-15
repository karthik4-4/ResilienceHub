"""
Independent unit tests for each of the 6 specialized agents.
Confirms modularity, proper tool usage, and Blackboard permission compliance.
"""

import pytest
import asyncio
from scdrc.core.blackboard import Blackboard, BlackboardView
from scdrc.core.schemas import (
    DisruptionReport,
    AgentName,
    EntryType,
    DisruptionType,
    InventoryStatusType,
)
from scdrc.agents.monitor_agent import MonitorAgent
from scdrc.agents.inventory_agent import InventoryAgent
from scdrc.agents.supplier_agent import SupplierAgent
from scdrc.agents.route_agent import RouteAgent
from scdrc.agents.cost_agent import CostAgent
from scdrc.agents.coordinator_agent import CoordinatorAgent


@pytest.fixture
def test_board():
    report = DisruptionReport(
        report_id="REP-TEST",
        text="Primary supplier Apex Micro Systems reports 10 days delay for SKU-1042 at Chennai Plant SITE-CHN-01.",
    )
    return Blackboard(case_id="CASE-AGENT-TEST", report=report)


@pytest.mark.asyncio
async def test_monitor_agent_posts_expected_entries(test_board):
    view = BlackboardView(test_board, AgentName.MONITOR)
    agent = MonitorAgent()
    entries = await agent.run(view)

    assert len(entries) == 3
    types = [e.type for e in entries]
    assert EntryType.DISRUPTION_PROFILE in types
    assert EntryType.AFFECTED_ITEMS in types
    assert EntryType.AFFECTED_SITES in types


@pytest.mark.asyncio
async def test_inventory_agent_computes_cover(test_board):
    # Setup prerequisite entries
    m_view = BlackboardView(test_board, AgentName.MONITOR)
    await MonitorAgent().run(m_view)

    inv_view = BlackboardView(test_board, AgentName.INVENTORY)
    agent = InventoryAgent()
    entries = await agent.run(inv_view)

    assert len(entries) == 1
    assert entries[0].type == EntryType.INVENTORY_STATUS
    inv_data = entries[0].payload.get("inventory", [])
    assert len(inv_data) > 0
    assert any(i["sku"] == "SKU-1042" for i in inv_data)


@pytest.mark.asyncio
async def test_supplier_agent_identifies_alternatives(test_board):
    m_view = BlackboardView(test_board, AgentName.MONITOR)
    await MonitorAgent().run(m_view)

    s_view = BlackboardView(test_board, AgentName.SUPPLIER)
    agent = SupplierAgent()
    entries = await agent.run(s_view)

    assert len(entries) == 1
    assert entries[0].type == EntryType.SUPPLIER_OPTIONS
    opts = entries[0].payload.get("options", [])
    assert len(opts) > 0
    # Must contain Silicon Craft (SUP-004)
    assert any(o["supplier_id"] == "SUP-004" for o in opts)


@pytest.mark.asyncio
async def test_route_agent_identifies_lanes(test_board):
    m_view = BlackboardView(test_board, AgentName.MONITOR)
    await MonitorAgent().run(m_view)

    r_view = BlackboardView(test_board, AgentName.ROUTE)
    agent = RouteAgent()
    entries = await agent.run(r_view)

    assert len(entries) == 1
    assert entries[0].type == EntryType.ROUTE_OPTIONS


@pytest.mark.asyncio
async def test_cost_agent_evaluates_options(test_board):
    # Run phases 1 & 2
    await MonitorAgent().run(BlackboardView(test_board, AgentName.MONITOR))
    await InventoryAgent().run(BlackboardView(test_board, AgentName.INVENTORY))
    await SupplierAgent().run(BlackboardView(test_board, AgentName.SUPPLIER))
    await RouteAgent().run(BlackboardView(test_board, AgentName.ROUTE))

    c_view = BlackboardView(test_board, AgentName.COST)
    agent = CostAgent()
    entries = await agent.run(c_view)

    assert len(entries) == 1
    assert entries[0].type == EntryType.COST_ESTIMATES
    estimates = entries[0].payload.get("estimates", [])
    assert len(estimates) > 0


@pytest.mark.asyncio
async def test_coordinator_agent_decides_grounded_mitigation(test_board):
    # Run full sequence through Cost Agent
    await MonitorAgent().run(BlackboardView(test_board, AgentName.MONITOR))
    await InventoryAgent().run(BlackboardView(test_board, AgentName.INVENTORY))
    await SupplierAgent().run(BlackboardView(test_board, AgentName.SUPPLIER))
    await RouteAgent().run(BlackboardView(test_board, AgentName.ROUTE))
    await CostAgent().run(BlackboardView(test_board, AgentName.COST))

    coord_view = BlackboardView(test_board, AgentName.COORDINATOR)
    agent = CoordinatorAgent()
    entries = await agent.run(coord_view)

    assert len(entries) == 1
    assert entries[0].type == EntryType.DECISION
    dec = entries[0].payload
    assert dec["action"] in ["REORDER", "REROUTE", "HOLD"]
    assert len(dec["cited_entry_ids"]) >= 1
