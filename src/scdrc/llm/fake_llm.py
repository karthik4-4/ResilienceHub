"""
Deterministic Mock LLM for offline testing and evaluation without network/API keys.
Returns grounded, schema-valid JSON responses mimicking reasoning outputs.
"""

from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Optional


class FakeLLM:
    """Mock LLM that inspects prompts and context to generate schema-valid outputs."""

    def __init__(self):
        pass

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        response_format: Optional[Dict[str, str]] = None,
        max_tokens: int = 1500,
    ) -> Dict[str, Any]:
        """Generate deterministic grounded mock output based on system/user content."""
        prompt_content = " ".join([m.get("content", "") for m in messages])

        # 1. Monitor Agent extraction
        if "Monitor Agent" in prompt_content or "extract entities" in prompt_content:
            payload = self._generate_monitor_output(prompt_content)
        # 2. Coordinator Agent decision
        elif "Coordinator Agent" in prompt_content or "decide mitigation" in prompt_content:
            payload = self._generate_coordinator_output(prompt_content)
        # 3. Cost narrative
        elif "Cost Agent" in prompt_content or "cost assumptions" in prompt_content:
            payload = {
                "methodology": "Total cost model integrating purchase, freight, expedite fees, transit holding, and stockout risk penalty.",
                "assumptions": [
                    "Holding cost calculated at 18-20% annual rate pro-rated by lead time.",
                    "Air freight applied for express transit when road/sea breaches safety cover.",
                    "Stockout penalties applied if arrival exceeds days of cover.",
                ],
            }
        else:
            payload = {"summary": "Standard analysis completed successfully."}

        return {
            "content": json.dumps(payload),
            "latency_seconds": 0.05,
            "tokens": {"prompt_tokens": len(prompt_content) // 4, "completion_tokens": 120, "total_tokens": 200},
            "model": "fake-llm-deterministic",
        }

    def _generate_monitor_output(self, text: str) -> Dict[str, Any]:
        """Extract disruption details deterministically."""
        # Check for ambiguity (S8)
        if "vague" in text.lower() or "rumor" in text.lower() or "somewhere in the south" in text.lower():
            return {
                "disruption_type": "UNKNOWN",
                "severity": 2,
                "expected_duration_days": 0,
                "root_cause": "Ambiguous report with no verified SKU or facility",
                "items": [],
                "sites": [],
                "unresolved_tokens": ["southern logistics corridor", "rumor"],
            }

        # Check for multi-site scenario (S9)
        if "SKU-1001" in text and "SKU-1002" in text:
            return {
                "disruption_type": "SUPPLIER_DELAY",
                "severity": 4,
                "expected_duration_days": 9,
                "root_cause": "Power surge at primary semiconductor plants",
                "items": [
                    {"sku": "SKU-1001", "name": "Microcontroller Unit ARM Cortex-M4", "qty_at_risk": 2000, "criticality": "CRITICAL"},
                    {"sku": "SKU-1002", "name": "Power Management IC 5V/3.3V", "qty_at_risk": 3000, "criticality": "CRITICAL"},
                ],
                "sites": [
                    {"site_id": "SITE-CHN-01", "name": "Chennai Electronics Manufacturing Plant", "role": "PLANT", "region": "South"},
                    {"site_id": "SITE-BLR-02", "name": "Bengaluru Systems Assembly Plant", "role": "PLANT", "region": "South"},
                ],
                "unresolved_tokens": [],
            }

        # Check for cleanroom contamination / SUP-009 contract exclusion scenario (S6)
        if "cleanroom" in text.lower() or "sup-009" in text.lower():
            return {
                "disruption_type": "SUPPLIER_DELAY",
                "severity": 4,
                "expected_duration_days": 12,
                "root_cause": "Cleanroom contamination at primary supplier Apex Micro Systems",
                "items": [
                    {"sku": "SKU-1042", "name": "Industrial Microcontroller Core SOC", "qty_at_risk": 1200, "criticality": "CRITICAL"}
                ],
                "sites": [
                    {"site_id": "SITE-CHN-01", "name": "Chennai Electronics Manufacturing Plant", "role": "PLANT", "region": "South"}
                ],
                "unresolved_tokens": [],
            }

        # Check for minor delay scenario (S3)
        if re.search(r"\b2[ -]days?\b", text.lower()):
            return {
                "disruption_type": "SUPPLIER_DELAY",
                "severity": 2,
                "expected_duration_days": 2,
                "root_cause": "Minor logistics dispatch delay from supplier",
                "items": [
                    {"sku": "SKU-1001", "name": "Microcontroller Unit ARM Cortex-M4", "qty_at_risk": 1500, "criticality": "CRITICAL"}
                ],
                "sites": [
                    {"site_id": "SITE-BLR-02", "name": "Bengaluru Systems Assembly Plant", "role": "PLANT", "region": "South"}
                ],
                "unresolved_tokens": [],
            }

        # Check for highway rockslide / route block (S2)
        if "rockslide" in text.lower() or "mumbai-pune" in text.lower() or "expressway" in text.lower() or "lane-mum-pun" in text.lower():
            return {
                "disruption_type": "ROUTE_BLOCK",
                "severity": 3,
                "expected_duration_days": 3,
                "root_cause": "Monsoon rockslide along Mumbai-Pune expressway",
                "items": [
                    {"sku": "SKU-1042", "name": "Industrial Microcontroller Core SOC", "qty_at_risk": 1200, "criticality": "CRITICAL"}
                ],
                "sites": [
                    {"site_id": "SITE-PUN-03", "name": "Pune Central Distribution Center", "role": "DC", "region": "West"}
                ],
                "unresolved_tokens": [],
            }

        # Check for port strike (S7)
        if "port strike" in text.lower() or "quarantine" in text.lower() or "site-sin-08" in text.lower():
            return {
                "disruption_type": "ROUTE_BLOCK",
                "severity": 5,
                "expected_duration_days": 30,
                "root_cause": "Port strike and quarantine halting all outbound lanes",
                "items": [
                    {"sku": "SKU-1042", "name": "Industrial Microcontroller Core SOC", "qty_at_risk": 3500, "criticality": "CRITICAL"}
                ],
                "sites": [
                    {"site_id": "SITE-SIN-08", "name": "Singapore Global Distribution Center", "role": "HUB", "region": "Overseas"}
                ],
                "unresolved_tokens": [],
            }

        # Check for Delhi stockout (S4)
        if "delhi" in text.lower() or "site-del-04" in text.lower():
            return {
                "disruption_type": "STOCKOUT",
                "severity": 5,
                "expected_duration_days": 8,
                "root_cause": "Depleted local inventory buffer and delayed replenishment",
                "items": [
                    {"sku": "SKU-1042", "name": "Industrial Microcontroller Core SOC", "qty_at_risk": 400, "criticality": "CRITICAL"}
                ],
                "sites": [
                    {"site_id": "SITE-DEL-04", "name": "Delhi NCR Fulfillment Center", "role": "DC", "region": "North"}
                ],
                "unresolved_tokens": [],
            }

        # Extract days if explicitly mentioned (e.g. 14 days in S5, 12 days in S6, 10 days in S1)
        dur = 10
        days_match = re.search(r"(\d+)[ -]days?", text, re.IGNORECASE)
        if days_match:
            dur = int(days_match.group(1))

        # Default: SKU-1042 at Chennai Plant
        return {
            "disruption_type": "SUPPLIER_DELAY",
            "severity": 4,
            "expected_duration_days": dur,
            "root_cause": "Primary supplier Apex Micro Systems manufacturing delay",
            "items": [
                {"sku": "SKU-1042", "name": "Industrial Microcontroller Core SOC", "qty_at_risk": 1200, "criticality": "CRITICAL"}
            ],
            "sites": [
                {"site_id": "SITE-CHN-01", "name": "Chennai Electronics Manufacturing Plant", "role": "PLANT", "region": "South"}
            ],
            "unresolved_tokens": [],
        }

    def _generate_coordinator_output(self, text: str) -> Dict[str, Any]:
        """Generate grounded decision based on ranked options present in prompt."""
        # Find entry IDs mentioned in the prompt (matching actual blackboard entry format E-0001)
        entry_ids = re.findall(r"\bE-0\d{3}\b", text)
        cited = list(dict.fromkeys(entry_ids)) if entry_ids else ["E-0001"]

        # Extract draft action, chosen option, cost, and rationale if present
        action_match = re.search(r"Action:\s*([A-Z_]+)", text)
        action = action_match.group(1) if action_match else "HOLD"

        chosen_match = re.search(r"Chosen:\s*([A-Za-z0-9_-]+)", text)
        chosen_id = chosen_match.group(1) if chosen_match else "HOLD"

        cost_match = re.search(r"Cost:\s*([0-9.]+)", text)
        total_cost = float(cost_match.group(1)) if cost_match else 0.0

        rationale_match = re.search(r"Draft Rationale:\s*(.+?)(?:\nOutput final JSON|$)", text, re.DOTALL)
        if rationale_match:
            rationale = rationale_match.group(1).strip()
        else:
            rationale = f"{action} option {chosen_id} chosen based on cost and viability analysis. Cited: {', '.join(cited)}."

        return {
            "action": action,
            "chosen_option_id": chosen_id,
            "total_cost_inr": total_cost,
            "rationale": rationale,
            "cited_entry_ids": cited,
            "rejected_options": [],
            "confidence": 0.90,
            "notify_list": [],
        }
