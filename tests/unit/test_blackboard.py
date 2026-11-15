"""
Unit tests for Blackboard rules, permissions, append-only constraints, and validation.
"""

import pytest
import asyncio
from scdrc.core.blackboard import Blackboard, BlackboardView
from scdrc.core.schemas import (
    DisruptionReport,
    EntryType,
    AgentName,
    CaseStatus,
    DisruptionProfilePayload,
    DisruptionType,
    InventoryStatusPayload,
)
from scdrc.core.errors import (
    BlackboardPermissionError,
    BlackboardValidationError,
    BlackboardStateError,
)


@pytest.fixture
def empty_board():
    report = DisruptionReport(
        report_id="REP-001",
        text="Sample supplier disruption report for SKU-1042",
    )
    return Blackboard(case_id="CASE-UNIT-01", report=report)


@pytest.mark.asyncio
async def test_blackboard_initialization(empty_board):
    assert empty_board.case_id == "CASE-UNIT-01"
    assert empty_board.status == CaseStatus.OPEN
    assert len(empty_board.get_all_entries()) == 0
    assert len(empty_board._audit_log) == 1
    assert empty_board._audit_log[0].event_type == "CASE_INITIALIZED"


@pytest.mark.asyncio
async def test_blackboard_write_permission_enforcement(empty_board):
    # Monitor Agent writing DISRUPTION_PROFILE is permitted
    payload = DisruptionProfilePayload(
        disruption_type=DisruptionType.SUPPLIER_DELAY,
        severity=4,
        expected_duration_days=5,
        source_text="Supplier delay",
    ).model_dump()

    entry = await empty_board.post_entry(
        author=AgentName.MONITOR,
        entry_type=EntryType.DISRUPTION_PROFILE,
        payload=payload,
    )
    assert entry.entry_id == "E-0001"
    assert entry.author == AgentName.MONITOR

    # Violation: Monitor trying to write DECISION must raise BlackboardPermissionError
    with pytest.raises(BlackboardPermissionError):
        await empty_board.post_entry(
            author=AgentName.MONITOR,
            entry_type=EntryType.DECISION,
            payload={"action": "REORDER"},
        )

    # Violation: Inventory trying to write ROUTE_OPTIONS must raise BlackboardPermissionError
    with pytest.raises(BlackboardPermissionError):
        await empty_board.post_entry(
            author=AgentName.INVENTORY,
            entry_type=EntryType.ROUTE_OPTIONS,
            payload={},
        )


@pytest.mark.asyncio
async def test_blackboard_schema_validation(empty_board):
    # Missing required field 'disruption_type' should raise BlackboardValidationError
    with pytest.raises(BlackboardValidationError):
        await empty_board.post_entry(
            author=AgentName.MONITOR,
            entry_type=EntryType.DISRUPTION_PROFILE,
            payload={"severity": 3},  # missing disruption_type and source_text
        )


@pytest.mark.asyncio
async def test_blackboard_append_only_and_versioning(empty_board):
    payload = DisruptionProfilePayload(
        disruption_type=DisruptionType.SUPPLIER_DELAY,
        severity=3,
        expected_duration_days=5,
        source_text="Initial report",
    ).model_dump()

    e1 = await empty_board.post_entry(
        author=AgentName.MONITOR,
        entry_type=EntryType.DISRUPTION_PROFILE,
        payload=payload,
    )
    assert e1.version == 1

    # Superseding entry creates version 2
    updated_payload = DisruptionProfilePayload(
        disruption_type=DisruptionType.SUPPLIER_DELAY,
        severity=4,
        expected_duration_days=8,
        source_text="Updated report",
    ).model_dump()

    e2 = await empty_board.post_entry(
        author=AgentName.MONITOR,
        entry_type=EntryType.DISRUPTION_PROFILE,
        payload=updated_payload,
        supersedes=e1.entry_id,
    )
    assert e2.version == 2
    assert e2.supersedes == "E-0001"
    assert len(empty_board.get_all_entries()) == 2


@pytest.mark.asyncio
async def test_blackboard_snapshot(empty_board):
    snapshot = empty_board.snapshot()
    assert snapshot.case_id == "CASE-UNIT-01"
    assert snapshot.status == CaseStatus.OPEN
    snap_dict = empty_board.snapshot_dict()
    assert "entries" in snap_dict
    assert "audit_log" in snap_dict
