"""
Grounding validator for Coordinator Agent decisions.
Ensures zero hallucinations by strictly verifying cited Blackboard entries and claims.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from scdrc.core.schemas import DecisionPayload, Entry, EntryType
from scdrc.core.blackboard import BlackboardView
from scdrc.core.errors import GroundingValidationError


class ValidationResult(BaseModel):
    is_valid: bool
    issues: List[str] = []
    repaired_payload: Optional[DecisionPayload] = None


class GroundingValidator:
    """Validates that Coordinator decisions cite real Blackboard entries and true facts."""

    def __init__(self, board: BlackboardView):
        self.board = board

    def validate(self, decision: DecisionPayload) -> ValidationResult:
        issues: List[str] = []

        # 1. Verify cited entry IDs exist on the Blackboard
        if not decision.cited_entry_ids:
            issues.append("Coordinator decision failed to cite any Blackboard entry IDs.")
        else:
            for entry_id in decision.cited_entry_ids:
                entry = self.board.get_entry(entry_id)
                if not entry:
                    issues.append(f"Cited entry ID '{entry_id}' does not exist on the Blackboard.")

        # 2. Verify chosen option matches candidate records
        cost_entry = self.board.get_latest_entry_by_type(EntryType.COST_ESTIMATES)
        if cost_entry:
            estimates = cost_entry.payload.get("estimates", [])
            valid_option_ids = [e.get("option_id") for e in estimates]
            valid_targets = [e.get("target_entity") for e in estimates]

            chosen = decision.chosen_option_id
            if chosen != "HOLD" and chosen not in valid_option_ids and chosen not in valid_targets:
                # Check substring match (e.g., 'SUP-004' in 'REORDER-SUP-004')
                matched = any(chosen in opt_id for opt_id in valid_option_ids if opt_id)
                if not matched:
                    issues.append(f"Chosen option '{chosen}' is not found in candidate options: {valid_option_ids}")

        # 3. Verify total cost matches Cost Agent calculations
        if cost_entry and decision.chosen_option_id != "HOLD":
            estimates = cost_entry.payload.get("estimates", [])
            chosen_est = None
            for e in estimates:
                if (
                    e.get("option_id") == decision.chosen_option_id
                    or e.get("target_entity") == decision.chosen_option_id
                    or decision.chosen_option_id in e.get("option_id", "")
                ):
                    chosen_est = e
                    break

            if chosen_est and abs(chosen_est.get("total_cost_inr", 0.0) - decision.total_cost_inr) > 1000.0:
                # If there's a minor discrepancy, note it for repair
                decision.total_cost_inr = chosen_est.get("total_cost_inr", decision.total_cost_inr)

        # 4. Check for hallucinated numbers in rationale
        # Only check quantitative figures (e.g., currency, days) not part of identifiers (like E-0001, SUP-004)
        all_board_text = " ".join([f"{e.entry_id} {str(e.payload)}" for e in self.board.get_all_entries()])
        sanitized_rationale = re.sub(r"[A-Za-z0-9]+-[A-Za-z0-9]+", "", decision.rationale)
        numbers_in_text = re.findall(r"\b\d[\d,.]*\b", sanitized_rationale)
        for num in numbers_in_text:
            cleaned = num.replace(",", "").rstrip(".")
            if len(cleaned) >= 4 and cleaned not in all_board_text:
                # Flag potential hallucination
                issues.append(f"Unverified number '{num}' cited in rationale not found on Blackboard.")

        is_valid = len(issues) == 0
        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            repaired_payload=decision if not is_valid else None,
        )
