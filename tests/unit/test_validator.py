"""
Unit tests for GroundingValidator.
Verifies citation grounding and hallucination prevention.
"""

import asyncio
from scdrc.core.blackboard import Blackboard, BlackboardView
from scdrc.core.schemas import (
    DisruptionReport,
    EntryType,
    AgentName,
    DecisionPayload,
    MitigationAction,
    CostEstimatesPayload,
    CostBreakdown,
)
from scdrc.decision.validator import GroundingValidator


def create_board_with_cost():
    report = DisruptionReport(report_id="R1", text="Supplier delay test")
    board = Blackboard(case_id="CASE-VAL-01", report=report)

    cost_breakdown = CostBreakdown(
        option_id="REORDER-SUP-004",
        action_type=MitigationAction.REORDER,
        target_entity="SUP-004",
        total_cost_inr=1842000.0,
        is_viable=True,
    )
    payload = CostEstimatesPayload(estimates=[cost_breakdown]).model_dump()

    async def _post():
        await board.post_entry(
            author=AgentName.COST,
            entry_type=EntryType.COST_ESTIMATES,
            payload=payload,
        )

    asyncio.run(_post())
    return board


def test_validator_valid_decision():
    board = create_board_with_cost()
    view = BlackboardView(board, AgentName.COORDINATOR)
    validator = GroundingValidator(view)

    decision = DecisionPayload(
        action=MitigationAction.REORDER,
        chosen_option_id="SUP-004",
        total_cost_inr=1842000.0,
        rationale="Selected SUP-004 based on cost estimates E-0001.",
        cited_entry_ids=["E-0001"],
        confidence=0.9,
    )

    result = validator.validate(decision)
    assert result.is_valid is True
    assert len(result.issues) == 0


def test_validator_detects_non_existent_citation():
    board = create_board_with_cost()
    view = BlackboardView(board, AgentName.COORDINATOR)
    validator = GroundingValidator(view)

    # Citing E-9999 which does NOT exist on the board
    decision = DecisionPayload(
        action=MitigationAction.REORDER,
        chosen_option_id="SUP-004",
        total_cost_inr=1842000.0,
        rationale="Selected option based on nonexistent entry E-9999.",
        cited_entry_ids=["E-9999"],
        confidence=0.9,
    )

    result = validator.validate(decision)
    assert result.is_valid is False
    assert any("does not exist" in issue for issue in result.issues)
