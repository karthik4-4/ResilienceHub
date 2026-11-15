"""
Simulated Outbox for enterprise messaging (Email, Slack, SMS).
Persists notifications to outputs/<case_id>/outbox.json.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List
from scdrc.core.schemas import NotificationRecipient


class NotificationOutbox:
    """Manages dispatched notifications and exports outbox log."""

    def __init__(self, outputs_dir: str = "./outputs"):
        self.outputs_dir = Path(outputs_dir)

    def dispatch(self, case_id: str, notifications: List[NotificationRecipient]) -> Path:
        """Save dispatched notifications to disk."""
        case_dir = self.outputs_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        outbox_file = case_dir / "outbox.json"

        data = [n.model_dump(mode="json") for n in notifications]
        with open(outbox_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return outbox_file
