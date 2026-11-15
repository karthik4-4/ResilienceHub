"""
Data models and schemas for SCDRC Multi-Agent Blackboard System.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class EntryType(str, Enum):
    DISRUPTION_PROFILE = "DISRUPTION_PROFILE"
    AFFECTED_ITEMS = "AFFECTED_ITEMS"
    AFFECTED_SITES = "AFFECTED_SITES"
    INVENTORY_STATUS = "INVENTORY_STATUS"
    SUPPLIER_OPTIONS = "SUPPLIER_OPTIONS"
    ROUTE_OPTIONS = "ROUTE_OPTIONS"
    COST_ESTIMATES = "COST_ESTIMATES"
    DECISION = "DECISION"
    DEGRADED = "DEGRADED"


class AgentName(str, Enum):
    MONITOR = "monitor"
    INVENTORY = "inventory"
    SUPPLIER = "supplier"
    ROUTE = "route"
    COST = "cost"
    COORDINATOR = "coordinator"
    ORCHESTRATOR = "orchestrator"


class CaseStatus(str, Enum):
    OPEN = "OPEN"
    GATHERING = "GATHERING"
    READY = "READY"
    DECIDED = "DECIDED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


class MitigationAction(str, Enum):
    REORDER = "REORDER"
    REROUTE = "REROUTE"
    HOLD = "HOLD"


class DisruptionType(str, Enum):
    SUPPLIER_DELAY = "SUPPLIER_DELAY"
    STOCKOUT = "STOCKOUT"
    ROUTE_BLOCK = "ROUTE_BLOCK"
    QUALITY_HOLD = "QUALITY_HOLD"
    UNKNOWN = "UNKNOWN"


class InventoryStatusType(str, Enum):
    OK = "OK"
    BELOW_SAFETY = "BELOW_SAFETY"
    STOCKOUT_RISK = "STOCKOUT_RISK"
    STOCKED_OUT = "STOCKED_OUT"


class Evidence(BaseModel):
    evidence_id: str
    source_type: str = Field(..., description="DATABASE | RAG | RULE | MANUAL")
    citation: str = Field(..., description="Document ID, table name, or clause reference")
    snippet: Optional[str] = None


class DisruptionReport(BaseModel):
    report_id: str
    text: str
    reported_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = "MANUAL"


# --- Specific Entry Payloads ---

class DisruptionProfilePayload(BaseModel):
    disruption_type: DisruptionType
    severity: int = Field(..., ge=1, le=5, description="Severity rating 1 to 5")
    start_date: Optional[str] = None
    expected_duration_days: int = Field(default=0, ge=0)
    source_text: str
    root_cause: Optional[str] = None


class AffectedItem(BaseModel):
    sku: str
    name: Optional[str] = None
    qty_at_risk: int = Field(default=0, ge=0)
    criticality: str = Field(default="MEDIUM", description="CRITICAL | HIGH | MEDIUM | LOW")


class AffectedItemsPayload(BaseModel):
    items: List[AffectedItem] = Field(default_factory=list)
    unresolved_tokens: List[str] = Field(default_factory=list)


class AffectedSite(BaseModel):
    site_id: str
    name: Optional[str] = None
    role: str = Field(default="PLANT", description="PLANT | DC | HUB")
    region: Optional[str] = None


class AffectedSitesPayload(BaseModel):
    sites: List[AffectedSite] = Field(default_factory=list)
    unresolved_tokens: List[str] = Field(default_factory=list)


class SiteInventoryItem(BaseModel):
    sku: str
    site_id: str
    on_hand: int = Field(ge=0)
    in_transit: int = Field(default=0, ge=0)
    safety_stock: int = Field(ge=0)
    daily_demand: float = Field(gt=0)
    days_of_cover: float = Field(ge=0)
    status: InventoryStatusType
    projected_stockout_date: Optional[str] = None


class InventoryStatusPayload(BaseModel):
    inventory: List[SiteInventoryItem] = Field(default_factory=list)
    summary: Optional[str] = None


class SupplierOption(BaseModel):
    supplier_id: str
    supplier_name: Optional[str] = None
    sku: str
    unit_price_inr: float = Field(gt=0)
    moq: int = Field(ge=1)
    lead_time_days: int = Field(ge=0)
    capacity: int = Field(ge=0)
    reliability_score: float = Field(ge=0.0, le=1.0)
    contract_ref: Optional[str] = None
    qualified: bool = True
    disqualification_reason: Optional[str] = None


class SupplierOptionsPayload(BaseModel):
    options: List[SupplierOption] = Field(default_factory=list)
    summary: Optional[str] = None


class RouteOption(BaseModel):
    route_id: str
    origin: str
    dest: str
    mode: str = Field(..., description="ROAD | RAIL | AIR | SEA")
    added_delay_days: int = Field(ge=0)
    transit_days: int = Field(ge=1)
    freight_cost_per_unit_inr: float = Field(ge=0)
    capacity_units: int = Field(ge=0)
    risk_rating: str = Field(default="LOW", description="LOW | MEDIUM | HIGH")
    carrier: Optional[str] = None
    advisory_ref: Optional[str] = None


class RouteOptionsPayload(BaseModel):
    options: List[RouteOption] = Field(default_factory=list)
    summary: Optional[str] = None


class CostBreakdown(BaseModel):
    option_id: str
    action_type: MitigationAction
    target_entity: str = Field(..., description="supplier_id or route_id or 'HOLD'")
    purchase_cost_inr: float = 0.0
    freight_cost_inr: float = 0.0
    expedite_fee_inr: float = 0.0
    holding_cost_inr: float = 0.0
    stockout_penalty_inr: float = 0.0
    total_cost_inr: float = 0.0
    arrival_days: int = 0
    is_viable: bool = True
    non_viability_reason: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)


class CostEstimatesPayload(BaseModel):
    estimates: List[CostBreakdown] = Field(default_factory=list)
    methodology: Optional[str] = None


class RejectedOption(BaseModel):
    option: str
    reason: str


class NotificationRecipient(BaseModel):
    role: str
    name: Optional[str] = None
    channel: str = "email"
    urgency: str = "normal"
    recipient_address: Optional[str] = None
    message: Optional[str] = None


class DecisionPayload(BaseModel):
    action: MitigationAction
    chosen_option_id: str
    total_cost_inr: float = 0.0
    rationale: str
    cited_entry_ids: List[str] = Field(default_factory=list)
    rejected_options: List[RejectedOption] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    notify_list: List[NotificationRecipient] = Field(default_factory=list)


class DegradedPayload(BaseModel):
    failed_agent: AgentName
    reason: str
    impact: str = "Operating with partial information"


# --- General Entry and Blackboard Models ---

class Entry(BaseModel):
    entry_id: str
    type: EntryType
    author: AgentName
    payload: Dict[str, Any]
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: List[Evidence] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1
    supersedes: Optional[str] = None


class AuditEvent(BaseModel):
    event_id: str
    event_type: str
    agent: AgentName
    details: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BlackboardSnapshot(BaseModel):
    case_id: str
    report: DisruptionReport
    entries: List[Entry]
    status: CaseStatus
    audit_log: List[AuditEvent]
    created_at: datetime = Field(default_factory=datetime.utcnow)
