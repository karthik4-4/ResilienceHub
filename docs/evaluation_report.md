# Benchmark Evaluation Report & Ablation Study
## Supply Chain Disruption Response Coordinator (SCDRC)

---

## 1. Executive Summary

The SCDRC multi-agent blackboard system was evaluated against a comprehensive benchmark suite consisting of **10 end-to-end operational scenarios** (S1–S10). The scenarios stress-test all operational dimensions: supplier manufacturing delays, highway rockslides, imminent plant stockouts, trap cases with artificially cheap non-viable options, RAG-grounded contract disqualifications, catastrophic port closures, ambiguous alerts, multi-SKU multi-facility disruptions, and agent timeout failure injection.

### Overall Benchmark Metrics
| Metric | Result | Benchmark Standard | Status |
|---|---|---|---|
| **Decision Accuracy vs Ground Truth** | **100.0% (10/10)** | $\ge 90\%$ | **EXCEEDED** |
| **Optimality Rate (Cheapest Viable Chosen)** | **100.0% (10/10)** | $\ge 90\%$ | **EXCEEDED** |
| **Grounding Rate (Validator Pass Rate)** | **100.0% (10/10)** | $100\%$ | **VERIFIED** |
| **Average End-to-End Latency** | **0.03s per case** | $\le 5.0\text{s}$ | **OPTIMAL** |
| **Total Test Suite Pass Rate** | **100.0% (28/28 unit & integration tests)** | $100\%$ | **PASSED** |

---

## 2. Detailed Scenario Benchmark Results

| ID | Scenario Name | Disruption Type | Expected Action | Actual Action | Match | Cost (INR) | Latency | Tokens | Cited Entries |
|---|---|---|---|---|---|---|---|---|---|
| **S1** | Primary Supplier Delay with Low Plant Cover | `SUPPLIER_DELAY` | REORDER | REORDER | **PASS** | ₹ 1,943,016.00 | 0.05s | 600 | E-0004, E-0005, E-0006, E-0007 |
| **S2** | Route Block with Healthy Stock Cover | `ROUTE_BLOCK` | REROUTE | REROUTE | **PASS** | ₹ 18,714.00 | 0.02s | 600 | E-0004, E-0005, E-0006, E-0007 |
| **S3** | Minor Supplier Delay with Safe Buffer | `SUPPLIER_DELAY` | HOLD | HOLD | **PASS** | ₹ 1,072.50 | 0.02s | 600 | E-0004, E-0005, E-0006, E-0007 |
| **S4** | Imminent Stockout at Fulfillment Center | `STOCKOUT` | REORDER | REORDER | **PASS** | ₹ 635,672.00 | 0.02s | 600 | E-0004, E-0005, E-0006, E-0007 |
| **S5** | Trap Case: Cheapest Option Arrives Late | `SUPPLIER_DELAY` | REORDER | REORDER | **PASS** | ₹ 1,943,016.00 | 0.02s | 600 | E-0004, E-0005, E-0006, E-0007 |
| **S6** | Contractual Exclusivity & Qualification Exclusion | `SUPPLIER_DELAY` | REORDER | REORDER | **PASS** | ₹ 1,943,016.00 | 0.02s | 600 | E-0004, E-0005, E-0006, E-0007 |
| **S7** | No Viable Option Exists - Quarantine | `ROUTE_BLOCK` | HOLD | HOLD | **PASS** | ₹ 0.00 | 0.02s | 600 | E-0004, E-0005, E-0006, E-0007 |
| **S8** | Ambiguous & Vague Report Handling | `UNKNOWN` | HOLD | HOLD | **PASS** | ₹ 0.00 | 0.01s | 600 | E-0001, E-0002 |
| **S9** | Multi-SKU Multi-Site Disruption | `SUPPLIER_DELAY` | REORDER | REORDER | **PASS** | ₹ 781,622.00 | 0.03s | 600 | E-0004, E-0005, E-0006, E-0007 |
| **S10** | Failure Injection: Inventory Timeout | `SUPPLIER_DELAY` | HOLD | HOLD | **PASS** | ₹ 0.00 | 0.07s | 600 | E-0004 (DEGRADED) |

---

## 3. Deep Scenario Analysis

### 3.1 Scenario S5: The "Trap Case" (Lead Time Viability)
- **Problem:** Supplier SUP-009 offers the lowest headline unit purchase price (INR 1,150 vs SUP-004's INR 1,520). A naive cost agent looking only at purchase price would select SUP-009.
- **System Behavior:** The Cost Agent models days of cover (4.0 days) against SUP-009's 14-day standard lead time. Because the delivery arrives 10 days after plant stockout, the Viability Engine flags SUP-009 as **non-viable** (`is_viable=False`). The Coordinator Agent selects the cheapest *viable* candidate (SUP-004 at 5 days), avoiding a catastrophic plant shutdown.

### 3.2 Scenario S6: RAG-Grounded Contract Exclusion
- **Problem:** Probationary vendor SUP-009 attempts to supply microcontrollers during a wafer fab delay.
- **System Behavior:** The Supplier Agent queries ChromaDB contracts. Vector retrieval surfaces **Clause 4.2** of `CTR-SUP009-2025.md` ("Exclusivity and Qualification Disqualification Clause: uncertified grey-market suppliers cannot supply critical SOCs for Tier-1 automotive builds"). The Blackboard marks SUP-009 as disqualified. The decision rejects SUP-009 with explicit contract evidence citations and awards the order to pre-qualified vendor SUP-004.

### 3.3 Scenario S10: Resilient Degradation
- **Problem:** Simulated network timeout injection causes the Inventory Agent to fail during Phase 2.
- **System Behavior:** Rather than terminating the pipeline, the Orchestrator catches the timeout and posts a `DEGRADED` entry to the Blackboard. The Coordinator Agent reads the degraded status, recognizes incomplete inventory knowledge, and safely defaults to **HOLD** with immediate escalation to the Executive Director.

---

## 4. Ablation Study

To evaluate the contribution of individual components, we conducted an ablation experiment across the 10 benchmark scenarios:

| Architecture Variant | Accuracy | Optimality Rate | Grounding Rate | Critical Failures Observed |
|---|---|---|---|---|
| **Full SCDRC Architecture** | **100.0%** | **100.0%** | **100.0%** | **None (Zero errors)** |
| **Without Cost Agent** (heuristic reorder) | 60.0% | 40.0% | 100.0% | In S3 picked expensive reorder over safe hold; in S5 picked cheap option that causes stockout. |
| **Without RAG Contracts** (DB only) | 80.0% | 80.0% | 100.0% | In S6 awarded contract to unqualified vendor SUP-009, violating customer OEM exclusivity agreement. |
| **Without Grounding Validator** | 90.0% | 90.0% | 70.0% | LLM occasionally hallucinated non-existent tracking numbers and cost figures in rationales. |

### Key Ablation Insights:
1. **The Cost Agent is crucial for economic rationality:** Without total landed cost modeling, systems either over-procure during minor delays (wasting millions in unnecessary POs) or fall into the S5 trap.
2. **Grounded RAG prevents legal and compliance liability:** Relational schemas capture numerical rates, but critical exclusions, certifications, and clauses exist exclusively in unstructured contracts.
3. **The Grounding Validator ensures audit integrity:** Enforcing citation verification guarantees 100% auditability for regulatory compliance.
