---
doc_id: SOP-INV-002
doc_type: SOP
category: INVENTORY_MANAGEMENT
version: 1.8
effective_date: 2025-01-15
---

# SOP: Inventory Cover, Buffer Calculation, and Stockout Risk Classification

### 1. Daily Cover Calculation
Days of cover at any site is computed deterministically as:
$$\text{Days of Cover} = \frac{\text{On Hand} + \text{Usable In-Transit}}{\text{Daily Demand}}$$

### 2. Stock Health Classifications
- **OK**: Days of cover $\ge$ 14 days, and on-hand $\ge$ safety stock.
- **BELOW_SAFETY**: On-hand $<$ safety stock, but days of cover $\ge$ 7 days.
- **STOCKOUT_RISK**: Days of cover $<$ 7 days, indicating imminent line stoppage if unmitigated.
- **STOCKED_OUT**: On-hand equals 0, production lines halted.

### 3. Emergency Procurement Buffer
For Critical items (Criticality=CRITICAL), procurement actions must trigger whenever days of cover drops below 5 days.
