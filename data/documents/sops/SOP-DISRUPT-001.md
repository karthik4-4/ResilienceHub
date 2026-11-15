---
doc_id: SOP-DISRUPT-001
doc_type: SOP
category: DISRUPTION_RESPONSE
version: 2.1
effective_date: 2025-01-10
---

# Standard Operating Procedure: Supply Chain Disruption Mitigation & Decision Framework

### 1. Purpose & Scope
This SOP defines the deterministic mitigation selection criteria across all ResilienceHub production plants (SITE-CHN-01, SITE-BLR-02) and distribution centers (SITE-PUN-03, SITE-DEL-04, SITE-HYD-05).

### 2. Decision Tree & Mitigation Actions
When a supply disruption or transit delay occurs, the Coordinator Agent must evaluate three potential actions:

1. **REORDER**:
   - Authorized when primary supplier delay or stockout exceeds current days of cover at the destination site.
   - Viable alternative suppliers must be active, qualified (`qualified=true`), and deliver before the projected stockout date or within safe buffer.
   - Selected option must be the lowest total cost among all viable options.

2. **REROUTE**:
   - Authorized when inventory at destination site can absorb the transit delay (days of cover > added transit delay), or when freight transit blockage can be bypassed via alternate lane/mode (e.g. switching from blocked road to operational rail corridor).
   - If reroute arrival ETA precedes projected stockout, rerouting is viable and often avoids secondary purchasing costs.

3. **HOLD**:
   - Authorized when days of cover comfortably absorb the delay without breaching safety stock thresholds (e.g. delay is 2 days while days of cover is 15 days).
   - Also mandatory when no viable alternative supplier or route can arrive prior to stockout, requiring human escalation to Plant General Manager and Escalation Director.

### 3. Viability Criteria (Mandatory Gate)
An option is strictly NON-VIABLE if:
- Arrival ETA is later than the destination site's projected stockout date.
- The supplier is disqualified, probationary, or restricted by exclusivity/compliance policies.
- Order quantity exceeds supplier maximum capacity.
