"""
Notification Router: Maps mitigation decisions and context to stakeholders
based on rules in notification_rules.yaml and contacts repository.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from jinja2 import Environment, FileSystemLoader

from scdrc.core.schemas import (
    DecisionPayload,
    NotificationRecipient,
    EntryType,
    MitigationAction,
)
from scdrc.core.blackboard import BlackboardView
from scdrc.data.repositories import ContactRepository, SQLiteContactRepository
from scdrc.notify.outbox import NotificationOutbox


class NotificationRouter:
    """Routes decision notifications to the right parties via configured channels."""

    def __init__(
        self,
        rules_path: Optional[str] = None,
        contact_repo: Optional[ContactRepository] = None,
        outbox: Optional[NotificationOutbox] = None,
    ):
        if not rules_path:
            rules_path = str(Path(__file__).parent.parent.parent.parent / "configs" / "notification_rules.yaml")

        self.rules: Dict[str, Any] = {}
        if os.path.exists(rules_path):
            with open(rules_path, "r", encoding="utf-8") as f:
                self.rules = yaml.safe_load(f).get("rules", {})

        self.contact_repo = contact_repo or SQLiteContactRepository()
        self.outbox = outbox or NotificationOutbox()

        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))

    def route_and_dispatch(
        self,
        board: BlackboardView,
        decision: DecisionPayload,
    ) -> List[NotificationRecipient]:
        """Determine recipients, render notification messages, and dispatch to outbox."""
        action_name = decision.action.value
        action_rules = self.rules.get(action_name, {})

        always_rules = action_rules.get("always", [])
        conditional_rules = action_rules.get("conditional", [])

        # Gather context from Blackboard
        inv_entry = board.get_latest_entry_by_type(EntryType.INVENTORY_STATUS)
        inv_items = inv_entry.payload.get("inventory", []) if inv_entry else []
        has_stockout_risk = any(i.get("status") in ["STOCKOUT_RISK", "STOCKED_OUT"] for i in inv_items)
        has_critical_cover = any(float(i.get("days_of_cover", 10.0)) < 3.0 for i in inv_items)

        sites_entry = board.get_latest_entry_by_type(EntryType.AFFECTED_SITES)
        affected_sites = [s.get("site_id") for s in sites_entry.payload.get("sites", [])] if sites_entry else []
        target_site = affected_sites[0] if affected_sites else None

        recipient_roles: List[Dict[str, str]] = []

        # 1. Process "always" rules
        for rule in always_rules:
            recipient_roles.append({
                "role": rule["role"],
                "channel": rule.get("channel", "email"),
                "urgency": rule.get("urgency", "high"),
            })

        # 2. Process "conditional" rules
        for rule in conditional_rules:
            cond = rule.get("condition")
            triggered = False

            if cond == "cost_exceeds_threshold":
                thresh = float(rule.get("threshold_inr", 1500000.0))
                triggered = decision.total_cost_inr >= thresh
            elif cond == "has_stockout_risk":
                triggered = has_stockout_risk
            elif cond == "cover_below_critical":
                triggered = has_critical_cover
            elif cond == "no_viable_option":
                triggered = (
                    decision.action == MitigationAction.HOLD
                    and ("escalate" in decision.rationale.lower() or "no viable" in decision.rationale.lower())
                )
            elif cond == "site_affected":
                triggered = bool(target_site)
            elif cond == "delivery_delayed":
                triggered = decision.action == MitigationAction.REROUTE

            if triggered:
                recipient_roles.append({
                    "role": rule["role"],
                    "channel": rule.get("channel", "email"),
                    "urgency": rule.get("urgency", "medium"),
                })

        # 3. Resolve recipient contacts and render messages
        dispatched_recipients: List[NotificationRecipient] = []
        for r_spec in recipient_roles:
            role = r_spec["role"]
            channel = r_spec["channel"]
            urgency = r_spec["urgency"]

            # Query contacts
            contacts = self.contact_repo.get_contacts_by_role(role, target_site)
            contact_name = contacts[0]["name"] if contacts else f"{role} On-Duty"
            contact_addr = (
                contacts[0]["email"] if contacts and channel == "email"
                else (contacts[0].get("phone") if contacts else "@channel")
            )

            # Render template
            template_name = "email_template.j2" if channel == "email" else "sms_template.j2"
            template = self.jinja_env.get_template(template_name)
            message_body = template.render(
                case_id=board.case_id,
                action=decision.action.value,
                chosen_option=decision.chosen_option_id,
                total_cost=decision.total_cost_inr,
                confidence=decision.confidence,
                rationale=decision.rationale,
                cited_entries=decision.cited_entry_ids,
                recipient_name=contact_name,
                role=role,
                urgency=urgency,
            )

            rec = NotificationRecipient(
                role=role,
                name=contact_name,
                channel=channel,
                urgency=urgency,
                recipient_address=contact_addr,
                message=message_body.strip(),
            )
            dispatched_recipients.append(rec)

        # 4. Save to outbox file
        self.outbox.dispatch(board.case_id, dispatched_recipients)

        # Update decision model
        decision.notify_list = dispatched_recipients
        return dispatched_recipients
