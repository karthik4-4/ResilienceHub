# Supply Chain Disruption Response Coordinator (SCDRC)
### Autonomous Multi-Agent Disruption Mitigation Engine using LangChain, LangGraph & Blackboard Architecture

[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.14-blue.svg)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-1.5+-1C3C3C.svg)](https://www.langchain.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2+-blueviolet.svg)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.42+-FF4B4B.svg)](https://streamlit.io)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.6+-orange.svg)](https://www.trychroma.com)
[![Tests](https://img.shields.io/badge/Tests-28%2F28%20Passing-brightgreen.svg)](tests/)
[![Evaluation](https://img.shields.io/badge/Evaluation-100%25%20Accuracy-success.svg)](data/scenarios/)

---

## 1. Project Overview

When global supply chains experience sudden disruptions (supplier factory delays, highway rockslides, sudden inventory stockouts, or port strikes), enterprises face millions of dollars in downtime and emergency freight costs. 

The **Supply Chain Disruption Response Coordinator (SCDRC)** is a production-ready multi-agent system designed to automate disruption response. Built on **LangChain** and **LangGraph**, the system coordinates six specialized autonomous agents through an explicit, compiled **LangGraph StateGraph** over a shared **Blackboard Architecture**. The agents ingest disruption alerts, assess stock health, discover alternate suppliers, evaluate detour lanes, model comprehensive landed costs, decide the optimal mitigation action (**REORDER**, **REROUTE**, or **HOLD**), and dispatch targeted stakeholder notifications.

---

## 2. Key Highlights & Features

- **LangGraph StateGraph Orchestration:** Multi-agent state transition graph featuring parallel fan-out (Inventory, Supplier, Route) and fan-in (Cost, Coordinator, Notification) over typed Blackboard state.
- **LangChain Model & Prompt Layer:** Standardized LangChain Chat Models (`ChatGroq`), `ChatPromptTemplate`, and structured output schemas with deterministic offline execution fallback.
- **Decoupled Blackboard Architecture:** Agents communicate strictly through a shared, typed, append-only Blackboard state. Agents never call each other directly.
- **Group-of-3 Cost Agent:** Formulates a total landed cost model combining purchasing, freight, expedite fees, transit holding, and stockout risk penalties to ensure the cheapest *viable* mitigation is selected.
- **Zero-Hallucination Grounding Validator:** The Coordinator's decisions are verified against existing Blackboard entry IDs, factual numbers, and contract citations before persistence.
- **Grounded Semantic RAG:** Vector retrieval over supplier contracts (`CTR-*.md`), SOPs, and route advisories (`ADV-*.md`) stored in ChromaDB to enforce quality and exclusivity clauses (such as rejecting uncertified spot vendors).
- **Graceful Fault Tolerance:** Built-in error degradation handles agent timeouts and failures, safely falling back to conservative actions with executive escalation.
- **100% Benchmark Score:** Evaluated across 10 end-to-end scenarios (S1–S10), achieving **100% Decision Accuracy**, **100% Optimality**, and **100% Grounding Rate**.

---

## 3. System Architecture & Coordination Protocol

```
                     Disruption Report (Text / JSON / API / UI)
                                        │
                                        ▼
                           ┌────────────────────────┐
                           │      Orchestrator      │
                           │  (Deterministic Engine)│
                           └───────────┬────────────┘
                                       │ Initializes
                                       ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │                       SHARED BLACKBOARD STATE                          │
   │   case_id · status · entries[] · audit_log · versioning · views        │
   └───▲─────────────▲─────────────▲─────────────▲─────────────▲────────▲───┘
       │             │             │             │             │        │
  ┌────┴───┐    ┌────┴────┐   ┌────┴────┐   ┌────┴────┐   ┌────┴───┐ ┌──┴────────┐
  │Monitor │    │Inventory│   │Supplier │   │ Route   │   │ Cost   │ │Coordinator│
  │ Agent  │    │ Agent   │   │ Agent   │   │ Agent   │   │ Agent  │ │   Agent   │
  └────┬───┘    └────┬────┘   └────┬────┘   └────┬────┘   └────┬───┘ └───┬───────┘
       │             │             │             │              │         │
       ▼             ▼             ▼             ▼              ▼         ▼
   Groq/Mock    SQLite WMS     SQLite +      SQLite +        Economic   Grounding
      LLM        Database      ChromaDB      ChromaDB         Model     Validator
                               (Contracts)   (Advisories)                 Gate
                                                                          │
                                                                          ▼
                                                                 Notification Router
                                                                          │
                                                                          ▼
                                                             Stakeholder Outbox (Email/SMS)
```

### Specialist Agent Directory

| Agent | Responsibility | Data Sources / Tools | Outputs Posted |
|---|---|---|---|
| **Monitor Agent** | Parses disruption reports, normalizes entities, and determines duration | LLM Entity Extractor, Master Catalog | `DISRUPTION_PROFILE`, `AFFECTED_ITEMS`, `AFFECTED_SITES` |
| **Inventory Agent** | Computes on-hand stock, in-transit units, and days of cover | SQLite Inventory Repo (`inventory`, `in_transit`) | `INVENTORY_STATUS` |
| **Supplier Agent** | Identifies alternate suppliers, verifies MOQ, checks contract clauses | SQLite Supplier Repo + ChromaDB Contracts | `SUPPLIER_OPTIONS` |
| **Route Agent** | Identifies transit corridors, modes, and checks live travel advisories | SQLite Lane Repo + ChromaDB Advisories | `ROUTE_OPTIONS` |
| **Cost Agent** | Computes landed cost breakdown and evaluates viability for all options | SQLite Cost Repo, Economic Cost Engine | `COST_ESTIMATES` |
| **Coordinator Agent** | Ranks viable options, selects cheapest, synthesizes grounded rationale | Blackboard State View, Grounding Validator | `DECISION` |

---

## 4. Benchmark Evaluation Results (S1–S10)

The system is validated against a 10-scenario benchmark suite covering diverse disruption classes:

| ID | Scenario Description | Expected | Actual | Status | Total Cost | Cited Entries |
|---|---|---|---|---|---|---|
| **S1** | Primary Supplier Delay with Low Plant Cover | REORDER | REORDER | **PASS** | ₹ 1,943,016.00 | E-0004, E-0005, E-0006, E-0007 |
| **S2** | Highway Rockslide with Healthy Cover | REROUTE | REROUTE | **PASS** | ₹ 18,714.00 | E-0004, E-0005, E-0006, E-0007 |
| **S3** | Minor Supplier Delay (Safe Buffer) | HOLD | HOLD | **PASS** | ₹ 1,072.50 | E-0004, E-0005, E-0006, E-0007 |
| **S4** | Imminent Stockout at Fulfillment Center | REORDER | REORDER | **PASS** | ₹ 635,672.00 | E-0004, E-0005, E-0006, E-0007 |
| **S5** | Trap Case: Cheapest Option Arrives Late | REORDER | REORDER | **PASS** | ₹ 1,943,016.00 | E-0004, E-0005, E-0006, E-0007 |
| **S6** | Contractual Exclusivity Clause 4.2 Exclusion | REORDER | REORDER | **PASS** | ₹ 1,943,016.00 | E-0004, E-0005, E-0006, E-0007 |
| **S7** | No Viable Option Exists (Port Quarantine) | HOLD | HOLD | **PASS** | ₹ 0.00 | E-0004, E-0005, E-0006, E-0007 |
| **S8** | Ambiguous & Vague Report Handling | HOLD | HOLD | **PASS** | ₹ 0.00 | E-0001, E-0002 |
| **S9** | Multi-SKU Multi-Site Disruption | REORDER | REORDER | **PASS** | ₹ 781,622.00 | E-0004, E-0005, E-0006, E-0007 |
| **S10** | Failure Injection: Inventory Timeout | HOLD | HOLD | **PASS** | ₹ 0.00 | E-0004 (DEGRADED) |

- **Decision Accuracy:** 100.0% (10/10)
- **Optimality Rate:** 100.0% (Cheapest viable option selected in all cases)
- **Grounding Rate:** 100.0% (Zero hallucinations)
- **Average Latency:** 0.03 seconds per case

---

## 5. Quickstart & Installation

### 5.1 Prerequisites
- Python 3.11+
- Virtual environment (recommended)

### 5.2 Installation
```bash
# Clone the repository
git clone https://github.com/your-org/ResilienceHub.git
cd ResilienceHub

# Install dependencies
pip install -r requirements.txt
# or install in editable mode:
pip install -e .
```

### 5.3 Initialize Database and Vector Store
```bash
python -m scdrc.cli seed
```
This populates SQLite database `data/scdrc.db` (41 items, 8 facilities, 12 suppliers, 25 lanes, 33 contacts, cost rates) and indexes 35 document chunks in ChromaDB (`data/chroma_db/`).

---

## 6. How to Run

### 6.1 Run Test Suite & Evaluation Harness
```bash
# Run 28 unit and integration tests
python -m pytest tests/unit tests/integration -v

# Run the 10-scenario benchmark evaluation
python -u tests/eval/run_eval.py
```

### 6.2 Run via CLI
```bash
# Run a scripted benchmark scenario (e.g. S1, S2, S5, S6)
python -m scdrc.cli run --scenario S1

# Run an ad-hoc disruption report
python -m scdrc.cli run --report "Supplier delay of 14 days affecting SKU-1042 at Chennai Plant."
```

### 6.3 Run the Interactive Web Dashboard
```bash
python -m scdrc.cli ui
# or: streamlit run src/scdrc/ui/dashboard.py
```
Access the interactive dashboard in your browser at `http://localhost:8501`.

### 6.4 Run the REST API
```bash
python -m scdrc.cli serve
```
Interactive Swagger documentation is available at `http://localhost:8000/docs`.

---

## 7. Docker Deployment

Deploy the complete multi-service stack with a single command:

```bash
docker-compose up --build
```

- **REST API:** `http://localhost:8000` (Swagger UI at `/docs`)
- **Web Dashboard:** `http://localhost:8501`

---

## 8. Detailed Documentation Links

- [System Architecture Specification](docs/architecture.md)
- [Blackboard Specification & Protocol](docs/blackboard_spec.md)
- [Agent Specifications Directory](docs/agent_specs.md)
- [REST API Reference](docs/api.md)
- [Benchmark Evaluation & Ablation Report](docs/evaluation_report.md)
- [Evaluator Demo Walkthrough Script](docs/demo_script.md)

---

## 9. Project Structure

```
ResilienceHub/
├── configs/                      # Configuration files
│   ├── settings.yaml             # Core operational settings, thresholds
│   ├── notification_rules.yaml   # Stakeholder routing matrix
│   └── logging.yaml
├── data/
│   ├── seed/                     # Master enterprise CSVs (items, suppliers, sites, etc.)
│   ├── documents/                # RAG corpus (contracts, SOPs, advisories)
│   ├── scenarios/                # Scripted benchmark scenarios (scenario_01 - 10)
│   ├── scdrc.db                  # Relational database (SQLite)
│   └── chroma_db/                # Local vector store (ChromaDB)
├── docs/                         # Comprehensive engineering documentation
│   ├── architecture.md
│   ├── blackboard_spec.md
│   ├── agent_specs.md
│   ├── api.md
│   ├── evaluation_report.md
│   └── demo_script.md
├── src/scdrc/                    # Source code package
│   ├── agents/                   # 6 Specialist agents (Monitor, Inventory, etc.)
│   ├── api/                      # FastAPI routes and server
│   ├── core/                     # Blackboard, Orchestrator, Schemas, Config
│   ├── data/                     # Database repositories and seeding
│   ├── decision/                 # Options builder, Viability, Scoring, Validator
│   ├── llm/                      # LLM clients, Prompts, Deterministic Mock
│   ├── notify/                   # Notification router, Outbox, Templates
│   ├── retrieval/                # ChromaDB vector store, Ingestion, Retriever
│   ├── ui/                       # Streamlit web dashboard
│   └── cli.py                    # Rich-formatted CLI entrypoint
├── tests/                        # Comprehensive test suite
│   ├── eval/                     # Evaluation harness (run_eval.py)
│   ├── integration/              # Integration tests
│   └── unit/                     # Unit tests
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pyproject.toml
└── README.md
```

---

## 10. License
Enterprise Multi-Agent Supply Chain Disruption Response Coordinator. Built for resilient, autonomous supply network operations.
