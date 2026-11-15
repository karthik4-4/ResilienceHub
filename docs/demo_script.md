# Evaluator Walkthrough & Live Demo Script
## Supply Chain Disruption Response Coordinator (SCDRC)

This document provides a concise 5–7 minute script for evaluators and stakeholders to verify all system capabilities across the CLI, Web Dashboard, and REST API.

---

## 1. Quick Verification: Automated Test & Benchmark Suite

Verify that the entire codebase, unit tests, integration tests, and benchmark scenarios pass with 100% success.

### Step 1: Run Pytest Suite
```powershell
python -m pytest tests/unit tests/integration -v
```
**Expected Outcome:**
`28 passed in ~2.3 seconds`. Verifies Blackboard append-only behavior, permissions, scoring logic, GroundingValidator, and scenario tests.

### Step 2: Run 10-Scenario Benchmark Evaluation
```powershell
python -u tests/eval/run_eval.py
```
**Expected Outcome:**
Terminal displays a rich colored benchmark table showing **10/10 PASS (100.0% Decision Accuracy, 100.0% Optimality, 100.0% Grounding Rate)**.

---

## 2. CLI Demonstrations: Key Scenarios

Test individual real-world disruption scenarios directly in the terminal with rich formatting.

### Demo 1: Supplier Delay with Imminent Stockout (Scenario S1)
```powershell
python -m scdrc.cli run --scenario S1
```
**What to Observe:**
- Monitor Agent parses 10-day delay for `SKU-1042` at `SITE-CHN-01`.
- Inventory Agent notes on-hand cover is only 4.0 days $\rightarrow$ Stockout imminent.
- Cost Agent cost-ranks alternative pre-qualified suppliers (`SUP-004` vs `SUP-012`).
- Coordinator decides **REORDER** with `SUP-004` (INR 1,943,016.00).
- Notification table alerts Procurement Manager (`Rajesh Kannan`), Plant Manager (`Sunita Menon` via SMS), and Supplier Rep.

### Demo 2: Highway Rockslide Corridor Detour (Scenario S2)
```powershell
python -m scdrc.cli run --scenario S2
```
**What to Observe:**
- Monitor Agent identifies Mumbai-Pune expressway block (`LANE-MUM-PUN-RD`).
- Route Agent detects road corridor is blocked, flags rail corridor (`LANE-MUM-PUN-RL`) as operational with 2-day added transit.
- Coordinator chooses **REROUTE** via rail at INR 18,714.00 total cost.

### Demo 3: Trap Case: Cheapest Supplier Disqualified Due to Delivery Delay (Scenario S5)
```powershell
python -m scdrc.cli run --scenario S5
```
**What to Observe:**
- `SUP-009` offers INR 1,150/unit (cheapest headline price), but lead time is 14 days.
- Plant stockout occurs on day 4.0.
- Cost Agent evaluates `SUP-009` as **non-viable** (`is_viable=False`).
- Coordinator rejects `SUP-009` and selects viable supplier `SUP-004`.

### Demo 4: RAG-Grounded Contract Exclusion (Scenario S6)
```powershell
python -m scdrc.cli run --scenario S6
```
**What to Observe:**
- Disruption report mentions probationary spot vendor `SUP-009`.
- Supplier Agent retrieves **Clause 4.2** of contract `CTR-SUP009-2025.md` via ChromaDB.
- `SUP-009` is disqualified due to OEM automotive exclusivity and uncertified spot-market status.
- Coordinator chooses certified partner `SUP-004`, citing exact contract clause on the Blackboard.

### Demo 5: Resilient Graceful Degradation (Scenario S10)
```powershell
python -m scdrc.cli run --scenario S10
```
**What to Observe:**
- Simulated network failure injected into the Inventory Agent.
- Orchestrator catches error and posts `DEGRADED` entry (`E-0004`).
- Coordinator notes incomplete inventory intelligence, safely defaults to **HOLD**, and initiates immediate escalation.

---

## 3. Interactive Web Dashboard Walkthrough

Launch the multi-page Streamlit application:
```powershell
python -m scdrc.cli ui
# or: streamlit run src/scdrc/ui/dashboard.py
```
Open browser at: `http://localhost:8501`

### What to Explore on the Dashboard:
1. **Scenario Selector:** Choose any scripted scenario (S1–S10) from the dropdown or type custom incident text.
2. **Execute Multi-Agent Response:** Click the **Run Multi-Agent Response** button.
3. **Executive Summary Cards:** View Action (`REORDER` / `REROUTE` / `HOLD`), Chosen Entity, Total Cost in INR, and Confidence score.
4. **Interactive Blackboard Inspector:**
   - Click each posted entry (`DISRUPTION_PROFILE`, `INVENTORY_STATUS`, `SUPPLIER_OPTIONS`, `COST_ESTIMATES`, `DECISION`).
   - Inspect JSON payloads, agent authors, timestamps, and RAG evidence snippets.
5. **Cost Comparison Chart:** Visual bar chart comparing total landed costs across all evaluated options.
6. **Stakeholder Notification Outbox:** View formatted Email and SMS alerts generated for managers.

---

## 4. REST API Walkthrough

Start the FastAPI application:
```powershell
python -m scdrc.cli serve
```
Open interactive Swagger UI at: `http://localhost:8000/docs`

### Sample API Call via curl or PowerShell:
```powershell
curl -X POST "http://localhost:8000/cases" -H "Content-Type: application/json" -d "{\"report_text\": \"Expressway landslide blocked Mumbai Pune road corridor for 3 days.\", \"case_id\": \"DEMO-API-01\"}"
```

### Inspect Blackboard Snapshot:
```powershell
curl "http://localhost:8000/cases/DEMO-API-01/blackboard"
```

### Inspect Stakeholder Notifications:
```powershell
curl "http://localhost:8000/cases/DEMO-API-01/notifications"
```
