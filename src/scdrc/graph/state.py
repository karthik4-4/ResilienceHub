"""
LangGraph State Schema for SCDRC Blackboard Architecture.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class BlackboardGraphState(TypedDict, total=False):
    """Shared state object routed across nodes in the LangGraph graph."""
    case_id: str
    report_text: str
    status: str
    board: Any  # Blackboard instance
    failure_injection: Dict[str, Any]
    trace_summary: Dict[str, Any]
    decision: Optional[Dict[str, Any]]
    notifications: List[Dict[str, Any]]
    is_degraded: bool
