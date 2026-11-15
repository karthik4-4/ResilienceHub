"""
Unit tests for Notification Router, Jinja2 template rendering, and outbox delivery.
"""

import pytest
from scdrc.core.blackboard import Blackboard, BlackboardView
from scdrc.core.schemas import (
    DisruptionReport,
    AgentName,
    DecisionPayload,
    MitigationAction,
    InventoryStatusPayload,
    SiteInventoryItem,
    InventoryStatusType,
    EntryType,
)
from scdrc.notify.router import NotificationRouter


@pytest.fixture
async def board_for_notify():
    report = DisruptionReport(report_id="R-NOTIF", text="Notification test")
    board = Blackboard(case_id="CASE-NOTIF-01", report=report)

    # Post stockout inventory status
    inv_item = SiteInventoryItem(
        sku="SKU-1042",
        site_id="SITE-CHN-01",
        on_hand=50,
        safety_stock=300,
        daily_demand=100.0,
        days_of_cover=0.5,
        status=InventoryStatusType.STOCKOUT_RISK,
    )
    await board.post_entry(
        author=AgentName.INVENTORY,
        entry_type=EntryType.INVENTORY_STATUS,
        payload=InventoryStatusPayload(inventory=[inv_item]).model_dump(),
    )
    return board


@pytest.mark.asyncio
async def test_notification_routing_reorder_with_stockout_risk(board_for_notify):
    view = BlackboardView(board_for_notify, AgentName.COORDINATOR)
    router = NotificationRouter()

    decision = DecisionPayload(
        action=MitigationAction.REORDER,
        chosen_option_id="SUP-004",
        total_cost_inr=1842000.0,  # Exceeds 1.5M -> should trigger Finance Controller
        rationale="Urgent reorder required to avert line stoppage.",
        cited_entry_ids=["E-0001"],
        confidence=0.9,
    )

    notifications = router.route_and_dispatch(view, decision)
    roles = [n.role for n in notifications]

    # Procurement Manager (always)
    assert "Procurement Manager" in roles
    # Supplier Account Rep (always)
    assert "Supplier Account Rep" in roles
    # Finance Controller (conditional: cost > 1.5M)
    assert "Finance Controller" in roles
    # Plant Manager (conditional: stockout risk)
    assert "Plant Manager" in roles

    for n in notifications:
        assert n.message is not None
        assert len(n.message) > 10
        assert "CASE-NOTIF-01" in n.message
