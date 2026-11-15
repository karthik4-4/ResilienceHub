"""
Streamlit Web Dashboard for SCDRC Multi-Agent Blackboard System.
"""

import asyncio
import json
import os
from pathlib import Path
import streamlit as st
import pandas as pd

from scdrc.core.orchestrator import Orchestrator
from scdrc.core.config import load_settings
from scdrc.core.schemas import EntryType, AgentName

st.set_page_config(
    page_title="SCDRC - Supply Chain Disruption Coordinator",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.2rem; }
    .sub-header { font-size: 1.1rem; color: #4B5563; margin-bottom: 1.5rem; }
    .agent-badge-monitor { background-color: #DBEAFE; color: #1E40AF; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .agent-badge-inventory { background-color: #FEF3C7; color: #92400E; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .agent-badge-supplier { background-color: #D1FAE5; color: #065F46; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .agent-badge-route { background-color: #F3E8FF; color: #6B21A8; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .agent-badge-cost { background-color: #FEE2E2; color: #991B1B; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .agent-badge-coordinator { background-color: #E0E7FF; color: #3730A3; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .decision-reorder { background-color: #ECFDF5; border: 2px solid #10B981; border-radius: 8px; padding: 15px; }
    .decision-reroute { background-color: #EFF6FF; border: 2px solid #3B82F6; border-radius: 8px; padding: 15px; }
    .decision-hold { background-color: #FFFBEB; border: 2px solid #F59E0B; border-radius: 8px; padding: 15px; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_orchestrator():
    settings = load_settings()
    return Orchestrator(settings=settings), settings


orchestrator, settings = get_orchestrator()

# Header
st.markdown('<div class="main-header">🌐 Supply Chain Disruption Response Coordinator (SCDRC)</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Autonomous Multi-Agent Blackboard Architecture · 6 Specialist Agents · Grounded Decision Intelligence</div>', unsafe_allow_html=True)

# Sidebar
st.sidebar.header("🕹️ Disruption Input")

# Load available scenarios
scenarios_dir = Path("./data/scenarios")
scenario_files = sorted(list(scenarios_dir.glob("*.json"))) if scenarios_dir.exists() else []

scenario_map = {}
scenario_names = ["Custom Report"]
for f in scenario_files:
    try:
        with open(f, "r", encoding="utf-8") as s_file:
            data = json.load(s_file)
            name = f"{data.get('scenario_id')}: {data.get('name')}"
            scenario_map[name] = data
            scenario_names.append(name)
    except Exception:
        pass

selected_scenario_name = st.sidebar.selectbox("Choose Evaluation Scenario:", scenario_names)

default_text = ""
scenario_desc = ""
scenario_purpose = ""
expected_action = ""

if selected_scenario_name != "Custom Report":
    scen_data = scenario_map[selected_scenario_name]
    default_text = scen_data.get("report_text", "")
    scenario_desc = scen_data.get("description", "")
    scenario_purpose = scen_data.get("test_purpose", "")
    expected_action = scen_data.get("expected_action", "")
    st.sidebar.info(f"**Expected Action:** {expected_action}\n\n**Goal:** {scenario_purpose}")

report_input = st.sidebar.text_area(
    "Disruption Report Text:",
    value=default_text or "Primary supplier Apex Micro Systems reports a 10-day delay for SKU-1042 at Chennai Plant SITE-CHN-01.",
    height=140,
)

execute_button = st.sidebar.button("🚀 Coordinate Response", type="primary", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Mode:** `{settings.mode.upper()}`")
st.sidebar.markdown(f"**Database:** SQLite (`data/scdrc.db`)")
st.sidebar.markdown(f"**Vector Store:** ChromaDB (`data/chroma_db`)")
st.sidebar.markdown(f"**Agents:** 6 (Monitor, Inventory, Supplier, Route, Cost, Coordinator)")


# State management
if "current_result" not in st.session_state:
    st.session_state["current_result"] = None


if execute_button:
    with st.spinner("Multi-Agent Blackboard coordination in progress..."):
        failure_injection = {}
        if "S10" in selected_scenario_name or "scenario_10" in selected_scenario_name:
            failure_injection["timeout_agent"] = "inventory"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            res = loop.run_until_complete(
                orchestrator.run_case(
                    report_text=report_input,
                    failure_injection=failure_injection,
                )
            )
            st.session_state["current_result"] = res
            st.success(f"Coordination complete! Case ID: {res['case_id']}")
        except Exception as e:
            st.error(f"Execution Error: {str(e)}")
        finally:
            loop.close()


res = st.session_state["current_result"]

if res:
    dec = res["decision"]
    action = dec["action"]
    chosen_opt = dec["chosen_option"]
    cost = dec["total_cost_inr"]
    confidence = dec["confidence"]
    rationale = dec["rationale"]
    cited = dec["cited_entries"]

    # Top KPI Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Mitigation Action", action)
    with col2:
        st.metric("Chosen Option", chosen_opt)
    with col3:
        st.metric("Total Landed Cost", f"₹ {cost:,.2f}" if cost > 0 else "₹ 0 (Absorbed)")
    with col4:
        st.metric("Coordinator Confidence", f"{confidence * 100:.1f} %")

    # Tabs for detailed views
    tab_decision, tab_blackboard, tab_cost, tab_notifications, tab_trace = st.tabs([
        "🎯 Decision & Justification",
        "📋 Blackboard Live State",
        "💰 Cost & Viability Analysis",
        "📬 Outbox Notifications",
        "⏱️ Execution Timeline & Telemetry",
    ])

    # Tab 1: Decision Card
    with tab_decision:
        st.markdown(f"### Optimal Mitigation: **{action}** ({chosen_opt})")

        card_class = "decision-reorder" if action == "REORDER" else ("decision-reroute" if action == "REROUTE" else "decision-hold")
        st.markdown(f"""
        <div class="{card_class}">
            <h4>Decision Rationale</h4>
            <p>{rationale}</p>
            <p><strong>Grounded Citations:</strong> {', '.join([f'<code>{c}</code>' for c in cited])}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("#### Rejected Mitigation Alternatives")
        rejected = dec.get("rejected", [])
        if rejected:
            rej_df = pd.DataFrame(rejected)
            rej_df.columns = ["Option ID", "Reason for Rejection"]
            st.dataframe(rej_df, use_container_width=True)
        else:
            st.write("No viable alternatives were evaluated or rejected.")

    # Tab 2: Blackboard State
    with tab_blackboard:
        st.markdown("### Immutable Blackboard Entries (Audit Trail)")
        snap_path = res.get("blackboard_snapshot")
        if snap_path and os.path.exists(snap_path):
            with open(snap_path, "r", encoding="utf-8") as sf:
                snapshot = json.load(sf)
                entries = snapshot.get("entries", [])

                for e in entries:
                    agent = e["author"]
                    etype = e["type"]
                    conf = e.get("confidence", 1.0)
                    eid = e["entry_id"]

                    with st.expander(f"📌 {eid} · {etype} (by {agent.upper()}) · Confidence: {conf:.2f}"):
                        st.json(e["payload"])
                        if e.get("evidence"):
                            st.markdown("**Attached Grounded Evidence:**")
                            for ev in e["evidence"]:
                                st.caption(f"- **{ev['citation']}** ({ev['source_type']}): {ev['snippet']}")

    # Tab 3: Cost & Viability Table
    with tab_cost:
        st.markdown("### Cost Agent Landed Cost Breakdown")
        snap_path = res.get("blackboard_snapshot")
        if snap_path and os.path.exists(snap_path):
            with open(snap_path, "r", encoding="utf-8") as sf:
                snapshot = json.load(sf)
                cost_entry = next((e for e in snapshot.get("entries", []) if e["type"] == "COST_ESTIMATES"), None)

                if cost_entry:
                    estimates = cost_entry["payload"].get("estimates", [])
                    if estimates:
                        df_rows = []
                        for opt in estimates:
                            df_rows.append({
                                "Option ID": opt.get("option_id"),
                                "Action": opt.get("action_type"),
                                "Target": opt.get("target_entity"),
                                "Arrival (Days)": opt.get("arrival_days"),
                                "Purchase (INR)": f"₹ {opt.get('purchase_cost_inr', 0):,.2f}",
                                "Freight (INR)": f"₹ {opt.get('freight_cost_inr', 0):,.2f}",
                                "Expedite (INR)": f"₹ {opt.get('expedite_fee_inr', 0):,.2f}",
                                "Holding (INR)": f"₹ {opt.get('holding_cost_inr', 0):,.2f}",
                                "Penalty (INR)": f"₹ {opt.get('stockout_penalty_inr', 0):,.2f}",
                                "Total Cost (INR)": f"₹ {opt.get('total_cost_inr', 0):,.2f}",
                                "Viable?": "✅ VIABLE" if opt.get("is_viable") else "❌ NON-VIABLE",
                                "Reason": opt.get("non_viability_reason") or "Viable",
                            })
                        cost_df = pd.DataFrame(df_rows)
                        st.dataframe(cost_df, use_container_width=True)
                    st.info(f"**Methodology:** {cost_entry['payload'].get('methodology')}")

    # Tab 4: Notifications Outbox
    with tab_notifications:
        st.markdown("### Dispatched Stakeholder Outbox")
        notifs = res.get("notify", [])
        if notifs:
            for n in notifs:
                col_ch, col_msg = st.columns([1, 3])
                with col_ch:
                    st.markdown(f"**Role:** {n['role']}")
                    st.markdown(f"**Recipient:** {n.get('name')}")
                    st.markdown(f"**Channel:** `{n['channel'].upper()}`")
                    st.markdown(f"**Urgency:** `{n['urgency'].upper()}`")
                with col_msg:
                    st.text_area("Message Body", value=n["message"], height=120, key=f"notif_{n['role']}_{n['channel']}")
                st.markdown("---")
        else:
            st.write("No notifications generated.")

    # Tab 5: Execution Trace
    with tab_trace:
        st.markdown("### Agent Execution Spans & Latency Telemetry")
        trace = res.get("trace_summary", {})
        st.write(f"**Total End-to-End Latency:** {trace.get('total_duration_seconds', 0):.3f} seconds · **Total Tokens:** {trace.get('total_tokens', 0)}")

        spans = trace.get("spans", [])
        if spans:
            span_rows = []
            for s in spans:
                span_rows.append({
                    "Span ID": s["span_id"],
                    "Agent": s["agent_name"].upper(),
                    "Status": s["status"],
                    "Duration (s)": round(s["duration_seconds"], 3),
                    "Tokens": s["total_tokens"],
                    "Tool Calls": ", ".join(s["tool_calls"]) if s.get("tool_calls") else "None",
                })
            st.dataframe(pd.DataFrame(span_rows), use_container_width=True)
else:
    st.info("👈 Select a disruption scenario from the sidebar and click **Coordinate Response** to run the multi-agent Blackboard system.")
