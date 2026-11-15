"""
Semantic Kernel Plugin: Scoped Blackboard access.
"""

from __future__ import annotations
import json
from typing import Optional
from semantic_kernel.functions import kernel_function

from scdrc.core.blackboard import BlackboardView
from scdrc.core.schemas import EntryType


class BlackboardPlugin:
    """Plugin providing scoped access to the shared Blackboard."""

    def __init__(self, view: BlackboardView):
        self.view = view

    @kernel_function(description="List all entry IDs, authors, and types currently on the blackboard.")
    def list_entries(self) -> str:
        entries = self.view.get_all_entries()
        summary = [{"entry_id": e.entry_id, "type": e.type.value, "author": e.author.value, "version": e.version} for e in entries]
        return json.dumps(summary, indent=2)

    @kernel_function(description="Retrieve full details and payload of a specific blackboard entry by ID.")
    def get_entry(self, entry_id: str) -> str:
        entry = self.view.get_entry(entry_id)
        if not entry:
            return json.dumps({"error": f"Entry '{entry_id}' not found."})
        return json.dumps(entry.model_dump(mode="json"), indent=2)

    @kernel_function(description="Retrieve all blackboard entries of a specific type.")
    def get_entries_by_type(self, entry_type: str) -> str:
        try:
            etype = EntryType(entry_type)
        except ValueError:
            return json.dumps({"error": f"Invalid entry type: {entry_type}"})
        entries = self.view.get_entries_by_type(etype)
        return json.dumps([e.model_dump(mode="json") for e in entries], indent=2)
