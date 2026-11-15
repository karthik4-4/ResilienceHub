# Agent Specifications & Capability Directory
## Supply Chain Disruption Response Coordinator (SCDRC)

---

## 1. Monitor Agent

### 1.1 Role & Objective
The **Monitor Agent** is the ingestion gateway of the system. It receives unstructured or semi-structured disruption reports, extracts critical entities, establishes disruption taxonomy, estimates event duration, and normalizes entities against master catalogs.

### 1.2 Inputs
- `report.text`: Raw text of the disruption alert (e.g. email, Slack bulletin, carrier notice).

### 1.3 Tools & Plugins
- **LLM Entity Extractor:** Prompts LLM for structured extraction of affected items, sites, root cause, and duration.
- **Master Data Catalog Lookup:** Normalizes fuzzy names (e.g., "Chennai plant" $\rightarrow$ `SITE-CHN-01`, "Apex" $\rightarrow$ `SUP-001`).

### 1.4 Outputs Posted to Blackboard
1. `DISRUPTION_PROFILE`: Disruption category (`SUPPLIER_DELAY`, `STOCKOUT`, `ROUTE_BLOCK`), severity (1–5), expected duration in days, and root cause.
2. `AFFECTED_ITEMS`: List of impacted SKUs, quantities at risk, and product criticality.
3. `AFFECTED_SITES`: Impacted production plants, assembly sites, and distribution centers.

### 1.5 Fallback & Error Handling
- If text contains ambiguous or unverifiable claims, flags `unresolved_tokens` and sets severity to lower confidence, triggering safe `HOLD` downstream.

---

## 2. Inventory Agent

### 2.1 Role & Objective
The **Inventory Agent** assesses stock health across all affected facilities. It computes whether the plant or warehouse can absorb the disruption using available buffer stock.

### 2.2 Inputs
- Reads `AFFECTED_ITEMS` and `AFFECTED_SITES` from Blackboard.

### 2.3 Tools & Plugins
- `InventoryRepository`: Queries `inventory` and `in_transit` tables in SQLite database.
- Inventory Formulas:
  $$\text{Effective Stock} = \text{On-Hand} + \text{In-Transit}$$
  $$\text{Days of Cover} = \frac{\text{On-Hand}}{\text{Daily Demand}}$$
  $$\text{Buffer Breach} = \text{On-Hand} < \text{Safety Stock}$$

### 2.4 Outputs Posted to Blackboard
- `INVENTORY_STATUS`: Itemized status for each SKU at each site, including `on_hand`, `in_transit`, `safety_stock`, `daily_demand`, `days_of_cover`, status (`CRITICAL`, `WARNING`, `OK`), and projected stockout date.

### 2.5 Fallback & Error Handling
- If database query returns no records, falls back to default safety-stock thresholds and flags warning.

---

## 3. Supplier Agent

### 3.1 Role & Objective
The **Supplier Agent** discovers alternative pre-qualified suppliers for affected items, retrieves negotiated pricing and lead times, and enforces contract clauses using grounded RAG.

### 3.2 Inputs
- Reads `AFFECTED_ITEMS` from Blackboard.

### 3.3 Tools & Plugins
- `SupplierRepository`: Queries `suppliers` and `supplier_items` tables in SQLite.
- `ChromaDB Contract Retriever`: Semantic search over supplier contracts (`CTR-*.md`) for exclusivity, probationary status, and surge capacity clauses.

### 3.4 Processing Logic
1. Identifies secondary and spot suppliers capable of supplying the required SKUs.
2. Evaluates supplier capacity against required quantity.
3. Retrieves contract excerpts from vector store:
   - If contract contains disqualification, probationary status, or quality exclusion clauses (e.g., Clause 4.2), marks `qualified=False` with cited contract section.
4. Generates candidate list with standard lead times and expedited options.

### 3.5 Outputs Posted to Blackboard
- `SUPPLIER_OPTIONS`: Array of `SupplierOption` objects detailing unit prices, MOQ, lead times, capacity, qualification status, and evidence citations.

---

## 4. Route Agent

### 4.1 Role & Objective
The **Route Agent** evaluates transit corridors between suppliers, ports, and destination plants. It identifies alternate modes (express road, freight rail, air cargo) and checks real-time advisories.

### 4.2 Inputs
- Reads `AFFECTED_SITES` from Blackboard.

### 4.3 Tools & Plugins
- `LaneRepository`: Queries `lanes` table for connected origin-destination pairs.
- `ChromaDB Advisory Retriever`: Semantic search over weather advisories, highway incident reports, and port notices (`ADV-*.md`).

### 4.4 Processing Logic
1. Discovers primary and secondary shipping lanes.
2. Cross-references active route advisories (e.g. monsoon rockslides, port strikes).
3. Evaluates transit times and added delays.
4. Flags compromised corridors with `risk_rating="BLOCKED"` and identifies operational detour corridors.

### 4.5 Outputs Posted to Blackboard
- `ROUTE_OPTIONS`: Array of `RouteOption` objects detailing route IDs, origin/destination, transport mode, transit days, added delays, capacity, and operational risk status.

---

## 5. Cost Agent (Group-of-3 Feature)

### 5.1 Role & Objective
The **Cost Agent** models comprehensive landed costs for all candidate mitigation actions (**REORDER**, **REROUTE**, **HOLD**) to ensure the Coordinator chooses the cheapest *viable* solution.

### 5.2 Inputs
- Reads `AFFECTED_ITEMS`, `INVENTORY_STATUS`, `SUPPLIER_OPTIONS`, and `ROUTE_OPTIONS`.

### 5.3 Cost Model Specification
For each candidate option, calculates:
$$\text{Total Landed Cost} = C_{\text{purchase}} + C_{\text{freight}} + C_{\text{expedite}} + C_{\text{holding}} + C_{\text{stockout}}$$

Where:
- $C_{\text{purchase}} = \max(\text{Needed Qty}, \text{MOQ}) \times \text{Unit Price}$ (for REORDER)
- $C_{\text{freight}} = \text{Volume} \times \text{Freight Rate}$
- $C_{\text{expedite}} = \text{Base Expedite Surcharge}$ (if lead time $\le 3$ days)
- $C_{\text{holding}} = (\text{Volume} \times \text{Standard Cost}) \times \text{Holding Rate} \times \text{Duration}$
- $C_{\text{stockout}} = \max(0, \text{Arrival Days} - \text{Days of Cover}) \times \text{Volume} \times \text{Stockout Penalty Rate}$

### 5.4 Viability Rules Engine
- **Lead Time Constraint:** If supplier lead time arrives after projected stockout date, option is marked `is_viable=False`.
- **Capacity Constraint:** If required quantity exceeds supplier or route capacity, marked `is_viable=False`.
- **Corridor Constraint:** If lane is blocked by incident, marked `is_viable=False`.
- **Contractual Constraint:** If supplier is disqualified under contract terms, marked `is_viable=False`.
- **HOLD Viability:** HOLD is viable *only* if days of cover $\ge$ disruption duration and no physical shipment is stranded on a blocked highway.

### 5.5 Outputs Posted to Blackboard
- `COST_ESTIMATES`: Comprehensive breakdown for every option with viability flags and explicit economic assumptions.

---

## 6. Coordinator Agent

### 6.1 Role & Objective
The **Coordinator Agent** reads the complete Blackboard state, selects the optimal mitigation action, grounds the rationale strictly in verified Blackboard entries, and submits the decision to the Grounding Validator.

### 6.2 Inputs
- Reads entire `Blackboard` state via `BlackboardView`.

### 6.3 Decision Protocol
1. **Filter:** Extracts viable options from `COST_ESTIMATES`.
2. **Rank:** Sorts viable options strictly by total landed cost in ascending order.
3. **Select:**
   - If viable options exist, chooses the lowest-cost option.
   - If no viable option can avert stockout, or if the case is marked `DEGRADED`, defaults to `HOLD` and escalates to human leadership.
4. **Rationale Synthesis:** Generates explanation explicitly citing Blackboard entry IDs (`E-0001`, `E-0004`, etc.).
5. **Grounding Validation Gate:** Passes decision payload through `GroundingValidator`. If any citation or fact is invalid, falls back to a deterministic grounded decision.

### 6.4 Outputs Posted to Blackboard
- `DECISION`: Final mitigation payload containing `action`, `chosen_option_id`, `total_cost_inr`, `rationale`, `cited_entry_ids`, `rejected_options`, and `confidence`.
