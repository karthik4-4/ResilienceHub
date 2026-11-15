"""
Event bus for asynchronous decoupled notifications across Blackboard phases.
"""

from __future__ import annotations
import asyncio
from typing import Callable, Coroutine, Dict, List, Any
from scdrc.core.schemas import Entry, CaseStatus, AgentName


EventHandler = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    """Simple in-memory async event bus."""

    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        handlers = self._subscribers.get(event_type, [])
        if handlers:
            tasks = [asyncio.create_task(h(data)) for h in handlers]
            await asyncio.gather(*tasks, return_exceptions=True)
