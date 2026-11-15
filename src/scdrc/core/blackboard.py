"""
Blackboard implementation for SCDRC.
Append-only, strictly typed, permission-controlled shared state.
"""

from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
import json
from pydantic import BaseModel

from scdrc.core.errors import (
    BlackboardPermissionError,
    BlackboardValidationError,
    BlackboardStateError,
)
from scdrc.core.schemas import (
    Entry,
    EntryType,
    AgentName,
    CaseStatus,
    AuditEvent,
    DisruptionReport,
    BlackboardSnapshot,
    DisruptionProfilePayload,
    AffectedItemsPayload,
    AffectedSitesPayload,
    InventoryStatusPayload,
    SupplierOptionsPayload,
    RouteOptionsPayload,
    CostEstimatesPayload,
    DecisionPayload,
    DegradedPayload,
    Evidence,
)

# Permission matrix: which agent can write which EntryType
AGENT_WRITE_PERMISSIONS: Dict[AgentName, Set[EntryType]] = {
    AgentName.MONITOR: {
        EntryType.DISRUPTION_PROFILE,
        EntryType.AFFECTED_ITEMS,
        EntryType.AFFECTED_SITES,
    },
    AgentName.INVENTORY: {
        EntryType.INVENTORY_STATUS,
    },
    AgentName.SUPPLIER: {
        EntryType.SUPPLIER_OPTIONS,
    },
    AgentName.ROUTE: {
        EntryType.ROUTE_OPTIONS,
    },
    AgentName.COST: {
        EntryType.COST_ESTIMATES,
    },
    AgentName.COORDINATOR: {
        EntryType.DECISION,
    },
    AgentName.ORCHESTRATOR: {
        EntryType.DEGRADED,
    },
}

# Payload schema mapping for runtime Pydantic validation
PAYLOAD_SCHEMAS: Dict[EntryType, Any] = {
    EntryType.DISRUPTION_PROFILE: DisruptionProfilePayload,
    EntryType.AFFECTED_ITEMS: AffectedItemsPayload,
    EntryType.AFFECTED_SITES: AffectedSitesPayload,
    EntryType.INVENTORY_STATUS: InventoryStatusPayload,
    EntryType.SUPPLIER_OPTIONS: SupplierOptionsPayload,
    EntryType.ROUTE_OPTIONS: RouteOptionsPayload,
    EntryType.COST_ESTIMATES: CostEstimatesPayload,
    EntryType.DECISION: DecisionPayload,
    EntryType.DEGRADED: DegradedPayload,
}


class Blackboard:
    """
    Central Blackboard shared state object.
    Enforces append-only semantics, agent write permissions, schema validation,
    and async thread-safety.
    """

    def __init__(self, case_id: str, report: DisruptionReport):
        self.case_id = case_id
        self.report = report
        self.status = CaseStatus.OPEN
        self._entries: List[Entry] = []
        self._audit_log: List[AuditEvent] = []
        self._lock: Optional[asyncio.Lock] = None
        self._entry_counter = 0

        self._record_audit(
            AgentName.ORCHESTRATOR,
            "CASE_INITIALIZED",
            f"Case {case_id} initialized with report: {report.text[:80]}...",
        )

    def _record_audit(self, agent: AgentName, event_type: str, details: str) -> None:
        event = AuditEvent(
            event_id=f"AUD-{len(self._audit_log) + 1:04d}",
            event_type=event_type,
            agent=agent,
            details=details,
            timestamp=datetime.utcnow(),
        )
        self._audit_log.append(event)

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def post_entry(
        self,
        author: AgentName,
        entry_type: EntryType,
        payload: Dict[str, Any],
        confidence: float = 1.0,
        evidence: Optional[List[Evidence]] = None,
        supersedes: Optional[str] = None,
    ) -> Entry:
        """
        Post a new entry to the blackboard.
        Enforces write permissions, payload validation, and append-only rules.
        """
        async with self._get_lock():
            # 1. Enforce write permissions
            allowed_types = AGENT_WRITE_PERMISSIONS.get(author, set())
            if entry_type not in allowed_types:
                raise BlackboardPermissionError(
                    f"Agent '{author.value}' is not permitted to write entry type '{entry_type.value}'. "
                    f"Allowed types: {[t.value for t in allowed_types]}"
                )

            # 2. Validate payload against Pydantic schema
            schema_cls = PAYLOAD_SCHEMAS.get(entry_type)
            if schema_cls:
                try:
                    if isinstance(payload, BaseModel):
                        validated_payload = payload.model_dump()
                    else:
                        validated_payload = schema_cls(**payload).model_dump()
                except Exception as e:
                    raise BlackboardValidationError(
                        f"Validation failed for entry type '{entry_type.value}': {str(e)}"
                    ) from e
            else:
                validated_payload = payload

            # 3. Determine version and superseding
            version = 1
            if supersedes:
                target_entry = self._get_entry_by_id_locked(supersedes)
                if not target_entry:
                    raise BlackboardStateError(f"Entry to supersede '{supersedes}' not found.")
                version = target_entry.version + 1

            # 4. Generate sequential entry ID (E-0001, E-0002, ...)
            self._entry_counter += 1
            entry_id = f"E-{self._entry_counter:04d}"

            entry = Entry(
                entry_id=entry_id,
                type=entry_type,
                author=author,
                payload=validated_payload,
                confidence=confidence,
                evidence=evidence or [],
                created_at=datetime.utcnow(),
                version=version,
                supersedes=supersedes,
            )

            self._entries.append(entry)

            self._record_audit(
                author,
                "ENTRY_POSTED",
                f"Posted {entry_id} ({entry_type.value}) with confidence {confidence:.2f}",
            )

            return entry

    def _get_entry_by_id_locked(self, entry_id: str) -> Optional[Entry]:
        for e in self._entries:
            if e.entry_id == entry_id:
                return e
        return None

    def get_entry(self, entry_id: str) -> Optional[Entry]:
        """Retrieve entry by its unique ID."""
        for e in self._entries:
            if e.entry_id == entry_id:
                return e
        return None

    def get_entries_by_type(self, entry_type: EntryType) -> List[Entry]:
        """Retrieve all entries matching a given type."""
        return [e for e in self._entries if e.type == entry_type]

    def get_latest_entry_by_type(self, entry_type: EntryType) -> Optional[Entry]:
        """Retrieve the latest entry for a given type."""
        matching = [e for e in self._entries if e.type == entry_type]
        return matching[-1] if matching else None

    def get_all_entries(self) -> List[Entry]:
        """Retrieve all blackboard entries in order."""
        return list(self._entries)

    def set_status(self, new_status: CaseStatus, agent: AgentName = AgentName.ORCHESTRATOR, reason: str = "") -> None:
        """Update case lifecycle status."""
        old = self.status
        self.status = new_status
        self._record_audit(agent, "STATUS_CHANGED", f"Status changed from {old.value} to {new_status.value}. {reason}")

    def snapshot(self) -> BlackboardSnapshot:
        """Export an immutable snapshot of the entire blackboard state."""
        return BlackboardSnapshot(
            case_id=self.case_id,
            report=self.report,
            entries=list(self._entries),
            status=self.status,
            audit_log=list(self._audit_log),
            created_at=datetime.utcnow(),
        )

    def snapshot_dict(self) -> Dict[str, Any]:
        """Export snapshot as a JSON-serializable dictionary."""
        return self.snapshot().model_dump(mode="json")


class BlackboardView:
    """
    Scoped view given to individual agents.
    Provides read access and enforces the agent's identity for writes.
    """

    def __init__(self, blackboard: Blackboard, agent_name: AgentName):
        self._board = blackboard
        self.agent_name = agent_name

    @property
    def case_id(self) -> str:
        return self._board.case_id

    @property
    def report(self) -> DisruptionReport:
        return self._board.report

    @property
    def status(self) -> CaseStatus:
        return self._board.status

    def get_entry(self, entry_id: str) -> Optional[Entry]:
        return self._board.get_entry(entry_id)

    def get_entries_by_type(self, entry_type: EntryType) -> List[Entry]:
        return self._board.get_entries_by_type(entry_type)

    def get_latest_entry_by_type(self, entry_type: EntryType) -> Optional[Entry]:
        return self._board.get_latest_entry_by_type(entry_type)

    def get_all_entries(self) -> List[Entry]:
        return self._board.get_all_entries()

    async def post_entry(
        self,
        entry_type: EntryType,
        payload: Dict[str, Any],
        confidence: float = 1.0,
        evidence: Optional[List[Evidence]] = None,
        supersedes: Optional[str] = None,
    ) -> Entry:
        """Post an entry under this agent's identity."""
        return await self._board.post_entry(
            author=self.agent_name,
            entry_type=entry_type,
            payload=payload,
            confidence=confidence,
            evidence=evidence,
            supersedes=supersedes,
        )

    def snapshot(self) -> BlackboardSnapshot:
        return self._board.snapshot()
