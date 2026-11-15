"""
FastAPI REST API routes for SCDRC.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from scdrc.core.orchestrator import Orchestrator
from scdrc.core.config import load_settings


router = APIRouter()
settings = load_settings()
orchestrator = Orchestrator(settings=settings)

# In-memory case cache
CASES_CACHE: Dict[str, Dict[str, Any]] = {}


class SubmitCaseRequest(BaseModel):
    report_text: str = Field(..., description="Free text or structured disruption report")
    case_id: Optional[str] = None


class ScenarioInfo(BaseModel):
    scenario_id: str
    name: str
    description: str
    report_text: str
    expected_action: str
    test_purpose: str


@router.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "Supply Chain Disruption Response Coordinator (SCDRC)",
        "version": settings.version,
        "mode": settings.mode,
    }


@router.get("/scenarios", response_model=List[ScenarioInfo])
def list_scenarios() -> List[Dict[str, Any]]:
    scenarios_dir = Path(settings.paths.scenarios_dir)
    scenarios: List[Dict[str, Any]] = []
    if scenarios_dir.exists():
        for f in sorted(scenarios_dir.glob("*.json")):
            with open(f, "r", encoding="utf-8") as s_file:
                scenarios.append(json.load(s_file))
    return scenarios


@router.post("/cases")
async def submit_case(request: SubmitCaseRequest) -> Dict[str, Any]:
    try:
        result = await orchestrator.run_case(
            report_text=request.report_text,
            case_id=request.case_id,
        )
        CASES_CACHE[result["case_id"]] = result
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Coordination failed: {str(e)}")


@router.post("/cases/scenario/{scenario_id}")
async def run_scenario(scenario_id: str) -> Dict[str, Any]:
    scenarios_dir = Path(settings.paths.scenarios_dir)
    matching_files = list(scenarios_dir.glob(f"*{scenario_id}*.json"))
    if not matching_files:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")

    with open(matching_files[0], "r", encoding="utf-8") as f:
        scen_data = json.load(f)

    report_text = scen_data["report_text"]
    case_id = f"CASE-{scenario_id}"

    # Handle scenario 10 failure injection
    failure_injection = {}
    if scenario_id == "S10" or "scenario_10" in matching_files[0].name:
        failure_injection["timeout_agent"] = "inventory"

    try:
        result = await orchestrator.run_case(
            report_text=report_text,
            case_id=case_id,
            failure_injection=failure_injection,
        )
        CASES_CACHE[result["case_id"]] = result
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scenario execution failed: {str(e)}")


@router.get("/cases/{case_id}")
def get_case(case_id: str) -> Dict[str, Any]:
    if case_id in CASES_CACHE:
        return CASES_CACHE[case_id]

    snapshot_file = Path(settings.paths.outputs_dir) / case_id / "blackboard.json"
    if snapshot_file.exists():
        with open(snapshot_file, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
        return {"case_id": case_id, "snapshot": snapshot}

    raise HTTPException(status_code=404, detail=f"Case {case_id} not found")


@router.get("/cases/{case_id}/blackboard")
def get_case_blackboard(case_id: str) -> Dict[str, Any]:
    snapshot_file = Path(settings.paths.outputs_dir) / case_id / "blackboard.json"
    if snapshot_file.exists():
        with open(snapshot_file, "r", encoding="utf-8") as f:
            return json.load(f)

    if case_id in CASES_CACHE:
        snap_path = CASES_CACHE[case_id].get("blackboard_snapshot")
        if snap_path and os.path.exists(snap_path):
            with open(snap_path, "r", encoding="utf-8") as f:
                return json.load(f)

    raise HTTPException(status_code=404, detail=f"Blackboard snapshot for case {case_id} not found")


@router.get("/cases/{case_id}/notifications")
def get_case_notifications(case_id: str) -> List[Dict[str, Any]]:
    if case_id in CASES_CACHE:
        return CASES_CACHE[case_id].get("notify", [])

    outbox_file = Path(settings.paths.outputs_dir) / case_id / "outbox.json"
    if outbox_file.exists():
        with open(outbox_file, "r", encoding="utf-8") as f:
            return json.load(f)

    raise HTTPException(status_code=404, detail=f"Notifications for case {case_id} not found")


@router.get("/cases/{case_id}/trace")
def get_case_trace(case_id: str) -> Dict[str, Any]:
    if case_id in CASES_CACHE:
        return CASES_CACHE[case_id].get("trace_summary", {})

    trace_file = Path(settings.paths.outputs_dir) / case_id / "trace.json"
    if trace_file.exists():
        with open(trace_file, "r", encoding="utf-8") as f:
            return json.load(f)

    raise HTTPException(status_code=404, detail=f"Trace for case {case_id} not found")
