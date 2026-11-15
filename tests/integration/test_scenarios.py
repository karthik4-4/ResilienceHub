"""
Integration tests for SCDRC across all 10 benchmark disruption scenarios.
"""

import pytest
import asyncio
from scdrc.core.orchestrator import Orchestrator


@pytest.fixture
def orchestrator():
    return Orchestrator()


@pytest.mark.asyncio
async def test_scenario_s1_supplier_delay(orchestrator):
    report = "Primary supplier Apex Micro Systems (SUP-001) reports a 10-day delay in wafer production affecting shipment SHP-8801 of 1200 units of SKU-1042 destined for Chennai Electronics Manufacturing Plant (SITE-CHN-01). Severity: 4."
    res = await orchestrator.run_case(report, case_id="TEST-INT-S1")
    dec = res["decision"]
    assert dec["action"] == "REORDER"
    assert "SUP-004" in dec["chosen_option"]
    assert len(dec["cited_entries"]) >= 1


@pytest.mark.asyncio
async def test_scenario_s2_route_block_healthy_cover(orchestrator):
    report = "DISRUPTION ALERT: Rockslide has blocked Mumbai-Pune Expressway along LANE-MUM-PUN-RD. Transit for incoming shipments to Pune Central Distribution Center (SITE-PUN-03) is blocked for 48-72 hours. Severity: 3."
    res = await orchestrator.run_case(report, case_id="TEST-INT-S2")
    dec = res["decision"]
    assert dec["action"] == "REROUTE"
    assert "LANE-MUM-PUN-RL" in dec["chosen_option"]


@pytest.mark.asyncio
async def test_scenario_s3_minor_delay_rational_hold(orchestrator):
    report = "LOGISTICS NOTICE: Supplier Apex Micro Systems (SUP-001) notified a 2-day minor logistics dispatch delay for SKU-1001 to Bengaluru Systems Assembly Plant (SITE-BLR-02). Severity: 2."
    res = await orchestrator.run_case(report, case_id="TEST-INT-S3")
    dec = res["decision"]
    assert dec["action"] == "HOLD"


@pytest.mark.asyncio
async def test_scenario_s4_stockout_cheaper_viable(orchestrator):
    report = "CRITICAL INCIDENT: Stockout at Delhi NCR Fulfillment Center (SITE-DEL-04) for SKU-1042. Current inventory is critically depleted (50 units). Need 400 units urgently. Severity: 5."
    res = await orchestrator.run_case(report, case_id="TEST-INT-S4")
    dec = res["decision"]
    assert dec["action"] == "REORDER"
    assert "SUP-004" in dec["chosen_option"]


@pytest.mark.asyncio
async def test_scenario_s5_trap_case_cheapest_non_viable(orchestrator):
    report = "SUPPLIER DISRUPTION: Primary vendor Apex Micro Systems reports machinery breakdown delaying SKU-1042 for Chennai Plant (SITE-CHN-01) by 14 days. On-hand cover is 4 days. Need 1200 units. Severity: 4."
    res = await orchestrator.run_case(report, case_id="TEST-INT-S5")
    dec = res["decision"]
    assert dec["action"] == "REORDER"
    # SUP-004 is selected because cheaper SUP-009 arrives too late
    assert "SUP-004" in dec["chosen_option"]


@pytest.mark.asyncio
async def test_scenario_s6_contract_exclusion(orchestrator):
    report = "DISRUPTION NOTICE: Supplier Apex Micro Systems (SUP-001) unable to supply SKU-1042 for Chennai Plant (SITE-CHN-01) due to cleanroom contamination for 12 days. Low-cost vendor SUP-009 has offered stock. Severity: 4."
    res = await orchestrator.run_case(report, case_id="TEST-INT-S6")
    dec = res["decision"]
    assert dec["action"] == "REORDER"
    assert "SUP-004" in dec["chosen_option"]


@pytest.mark.asyncio
async def test_scenario_s7_no_viable_option_escalate(orchestrator):
    report = "CATASTROPHIC INCIDENT: Complete port strike and quarantine at Singapore Global Distribution Center (SITE-SIN-08). All outgoing maritime and air cargo lanes suspended for 30 days. Severity: 5."
    res = await orchestrator.run_case(report, case_id="TEST-INT-S7")
    dec = res["decision"]
    assert dec["action"] == "HOLD"


@pytest.mark.asyncio
async def test_scenario_s8_ambiguous_report(orchestrator):
    report = "Vague rumor: Heard there are big shipment problems somewhere in the southern logistics corridor, maybe things will be late next week."
    res = await orchestrator.run_case(report, case_id="TEST-INT-S8")
    dec = res["decision"]
    assert dec["action"] == "HOLD"
    assert dec["confidence"] <= 0.70


@pytest.mark.asyncio
async def test_scenario_s9_multi_sku_disruption(orchestrator):
    report = "MULTI-SITE ALERT: Power surge halted deliveries of SKU-1001 and SKU-1002 to both Chennai Plant (SITE-CHN-01) and Bengaluru Plant (SITE-BLR-02) for 9 days. Severity: 4."
    res = await orchestrator.run_case(report, case_id="TEST-INT-S9")
    dec = res["decision"]
    assert dec["action"] == "REORDER"


@pytest.mark.asyncio
async def test_scenario_s10_inventory_agent_timeout_degraded(orchestrator):
    report = "DISRUPTION NOTICE: Supplier Apex Micro Systems delays SKU-1042 delivery by 6 days to Chennai Plant (SITE-CHN-01). Severity: 3."
    res = await orchestrator.run_case(
        report,
        case_id="TEST-INT-S10",
        failure_injection={"timeout_agent": "inventory"},
    )
    dec = res["decision"]
    assert dec["action"] == "HOLD"
    assert "DEGRADED" in dec["rationale"] or dec["confidence"] < 0.75
