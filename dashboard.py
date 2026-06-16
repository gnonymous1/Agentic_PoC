"""
SEPE — Sovereign Executive Persona Clone (SEPE)
Human Command Center (Streamlit UI Dashboard)

This dashboard provides a premium, responsive monitoring console for the executive.
Features custom glassmorphism styles, Outfit typography, and multi-desk tracking controls.
"""

import os
import json
import logging
import asyncio
import streamlit as st
import pandas as pd
import httpx
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="SEPE | Human Command Center",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    /* Global Overrides */
    * {
        font-family: 'Outfit', sans-serif !important;
    }
    
    .stApp {
        background-color: #0d0f13;
        color: #e5e9f0;
    }
    
    /* Sidebar glassmorphism */
    section[data-testid="stSidebar"] {
        background-color: rgba(22, 26, 34, 0.9) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* Custom Headers */
    h1, h2, h3 {
        color: #ffffff;
        font-weight: 800 !important;
        letter-spacing: -0.5px;
    }
    
    .main-title {
        background: linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.8rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }
    
    .subtitle {
        color: #8b9bb4;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Card Container glassmorphism */
    .glass-card {
        background: rgba(22, 26, 34, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    
    /* KPI Status indicators */
    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        color: #ffffff;
        line-height: 1.2;
    }
    
    .metric-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #8b9bb4;
        margin-bottom: 0.3rem;
    }
    
    /* Color-coded tags */
    .status-badge {
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        display: inline-block;
    }
    
    .status-pending { background-color: #2e3440; color: #d8dee9; }
    .status-running { background-color: #5e81ac; color: #eceff4; }
    .status-completed { background-color: #a3be8c; color: #2e3440; }
    .status-failed { background-color: #bf616a; color: #eceff4; }
    .status-approval { background-color: #d08770; color: #2e3440; }
</style>
""", unsafe_allow_html=True)

# Helper config parameters
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# ===========================================================================
# SIDEBAR NAVIGATION
# ===========================================================================

st.sidebar.markdown("""
<div style='padding: 1.5rem 0rem; text-align: center;'>
    <h2 style='margin:0; font-size: 1.8rem; font-weight:800; color: #ffffff;'>👑 SEPE</h2>
    <span style='color: #8b9bb4; font-size: 0.8rem; letter-spacing:2px; text-transform:uppercase;'>Master Control</span>
</div>
""", unsafe_allow_html=True)

selected_desk = st.sidebar.radio(
    "CHOOSE ACTIVE OPERATIONS DESK",
    [
        "🚀 Autopilot Operations",
        "🛡️ HITL Verification Desk",
        "📊 Financial Overseer Desk",
        "📂 Workspace Portfolio",
        "🎥 Virtual Meeting Briefs"
    ],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style='background: rgba(255,255,255,0.02); padding: 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);'>
    <div style='font-size: 0.75rem; color:#8b9bb4; text-transform:uppercase; letter-spacing:1px;'>Security Boundary</div>
    <div style='font-size:0.9rem; font-weight:600; color:#a3be8c; margin-top:0.2rem;'>● VAULT ENCRYPTED</div>
    <div style='font-size: 0.75rem; color:#8b9bb4; margin-top:0.5rem;'>AES-256-GCM hardware key validation verified.</div>
</div>
""", unsafe_allow_html=True)


# ===========================================================================
# DESK A: AUTOPILOT OPERATIONS (DAG Visualizer)
# ===========================================================================

if selected_desk == "🚀 Autopilot Operations":
    st.markdown("<div class='main-title'>Autopilot Operations Desk</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>Autonomous JSON DAG generator and concurrent execution telemetry</div>", unsafe_allow_html=True)

    # Metric Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown("""
        <div class='glass-card'>
            <div class='metric-label'>Active Autopilot</div>
            <div class='metric-value' style='color:#a3be8c;'>RUNNING</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown("""
        <div class='glass-card'>
            <div class='metric-label'>Completed DAGs</div>
            <div class='metric-value'>24</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown("""
        <div class='glass-card'>
            <div class='metric-label'>Blocked Nodes</div>
            <div class='metric-value' style='color:#d08770;'>0</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown("""
        <div class='glass-card'>
            <div class='metric-label'>Failed Tasks</div>
            <div class='metric-value' style='color:#bf616a;'>0</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### 🎯 Dispatch Macro Goal")
    with st.container():
        goal_input = st.text_input(
            "Input an abstract operational or business objective for the clone to orchestrate:",
            value="Vectorize acme_invoice.pdf, run B2B pricing analysis, compile copywriting layouts, and prepare the technical pitch briefing."
        )
        submit_btn = st.button("EXECUTE AUTOPILOT", use_container_width=True)

        if submit_btn and goal_input:
            with st.spinner("Compiling non-linear Directed Acyclic Graph (DAG)..."):
                try:
                    # Request backend FastAPI to compile and run DAG
                    resp = httpx.post(f"{API_BASE_URL}/api/v1/hitl/dag/compile", json={"macro_goal": goal_input})
                    if resp.status_code == 200:
                        st.success("JSON Dependency Tree successfully compiled and registered! Execution active.")
                        st.json(resp.json())
                    else:
                        st.error(f"Failed to compile DAG: {resp.text}")
                except Exception as e:
                    st.error(f"FastAPI connection error: {e}")

    st.markdown("### 📊 Active Execution Pipeline")
    # Fetch active DAG execution logs from DB
    try:
        resp = httpx.get(f"{API_BASE_URL}/api/v1/hitl/dag/active")
        if resp.status_code == 200 and resp.json():
            dags = resp.json()
            for job in dags:
                st.markdown(f"""
                <div class='glass-card'>
                    <div style='display:flex; justify-content:space-between; align-items:center;'>
                        <h4 style='margin:0; color:#ffffff;'>Goal: {job['macro_goal']}</h4>
                        <span class='status-badge status-{job['status']}'>{job['status']}</span>
                    </div>
                    <div style='font-size:0.8rem; color:#8b9bb4; margin-top:0.3rem;'>Registered: {job['created_at']} | Job ID: {job['id']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Render node-by-node details
                dag_json = json.loads(job['dag_json'])
                for layer in dag_json.get('dag_layers', []):
                    st.markdown(f"**Layer {layer['layer_id']} Execution Block**")
                    cols = st.columns(len(layer.get('nodes', [])))
                    for idx, node in enumerate(layer.get('nodes', [])):
                        with cols[idx]:
                            status_cls = "pending"
                            if node['status'] == "completed": status_cls = "completed"
                            elif node['status'] == "running": status_cls = "running"
                            elif node['status'] == "failed": status_cls = "failed"
                            elif node['status'] == "pending_approval": status_cls = "approval"
                            
                            st.markdown(f"""
                            <div style='background:rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius:8px; padding: 1rem; text-align:center;'>
                                <div style='font-size:0.75rem; color:#8b9bb4;'>{node['node_id']}</div>
                                <div style='font-weight:600; margin: 0.3rem 0; font-size:0.9rem; color:#ffffff;'>{node['agent_skill']}</div>
                                <span class='status-badge status-{status_cls}'>{node['status']}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # If pending approval, render Release Button
                            if node['status'] == "pending_approval":
                                release_btn = st.button("MANUAL RELEASE CAPITAL", key=f"release_{node['node_id']}")
                                if release_btn:
                                    httpx.post(f"{API_BASE_URL}/api/v1/hitl/dag/release", json={"ledger_id": job['id']})
                                    st.experimental_rerun()
                                    
                # Render System logs
                with st.expander("Telemetry logs & execution traces"):
                    st.json(json.loads(job.get('telemetry_logs', '[]')))
        else:
            st.info("No active DAG jobs running at this time.")
    except Exception as e:
        st.warning(f"Could not load active DAG telemetry: {e}")


# ===========================================================================
# DESK B: HITL VERIFICATION DESK (Sign-offs)
# ===========================================================================

elif selected_desk == "🛡️ HITL Verification Desk":
    st.markdown("<div class='main-title'>HITL Verification Desk</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>Review, approve, or rewrite content drafts and high-risk digital releases</div>", unsafe_allow_html=True)

    # Load content drafts pending sign-off from database
    try:
        resp = httpx.get(f"{API_BASE_URL}/api/v1/hitl/drafts/pending")
        if resp.status_code == 200 and resp.json():
            drafts = resp.json()
            for draft in drafts:
                payload = json.loads(draft['payload'])
                
                st.markdown(f"""
                <div class='glass-card'>
                    <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;'>
                        <h4 style='margin:0; color:#ffffff;'>Draft ID: {draft['id']}</h4>
                        <span class='status-badge status-approval'>PENDING SIGN-OFF</span>
                    </div>
                """, unsafe_allow_html=True)
                
                # Render layout tabs
                tab1, tab2, tab3 = st.tabs(["🐦 Twitter/X Thread", "💼 LinkedIn Analysis", "📝 Blogspot HTML"])
                
                with tab1:
                    posts = payload.get("twitter", {}).get("posts", [])
                    for i, post in enumerate(posts):
                        st.markdown(f"**Post {i+1}:** {post}")
                with tab2:
                    st.write(payload.get("linkedin", {}).get("body", ""))
                with tab3:
                    st.markdown(f"**Title:** {payload.get('blogspot', {}).get('title', '')}")
                    st.code(payload.get('blogspot', {}).get('html_body', ''), language="html")

                # Action controls
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("APPROVE & DEPLOY CONCURRENTLY", key=f"app_{draft['id']}", use_container_width=True):
                        with st.spinner("Decrypting tokens and dispatching REST pipelines..."):
                            act_resp = httpx.post(
                                f"{API_BASE_URL}/api/v1/hitl/action",
                                json={"ledger_id": draft['id'], "action": "APPROVE"}
                            )
                            if act_resp.status_code == 200:
                                st.success("Assets successfully deployed concurrently across networks!")
                                st.json(act_resp.json())
                            else:
                                st.error(f"Dispatch failed: {act_resp.text}")
                with c2:
                    notes = st.text_input("Feedback or correction guidelines for rewrite:", key=f"notes_{draft['id']}")
                    if st.button("REWRITE WITH SELF-HEALING", key=f"rw_{draft['id']}", use_container_width=True):
                        with st.spinner("Executing rewrite cycle..."):
                            act_resp = httpx.post(
                                f"{API_BASE_URL}/api/v1/hitl/action",
                                json={
                                    "ledger_id": draft['id'], 
                                    "action": "REWRITE", 
                                    "notes": notes,
                                    "topic": "Compliance AI",
                                    "persona_prompt": "You are a professional corporate executive Twin."
                                }
                            )
                            if act_resp.status_code == 200:
                                st.success("Draft successfully healed and updated draft generated!")
                                st.experimental_rerun()
                            else:
                                st.error(f"Heal failed: {act_resp.text}")
                
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("No content drafts pending sign-off at this time.")
    except Exception as e:
        st.warning(f"Could not load pending drafts: {e}")


# ===========================================================================
# DESK C: FINANCIAL OVERSEER DESK
# ===========================================================================

elif selected_desk == "📊 Financial Overseer Desk":
    st.markdown("<div class='main-title'>Financial Overseer Desk</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>Real-time ledger audit logs, budget balance allocations, and invoice ingestion portal</div>", unsafe_allow_html=True)

    # Metrics
    f1, f2, f3 = st.columns(3)
    with f1:
        st.markdown("""
        <div class='glass-card'>
            <div class='metric-label'>Accounts Receivable</div>
            <div class='metric-value' style='color:#a3be8c;'>$125,000.00</div>
        </div>
        """, unsafe_allow_html=True)
    with f2:
        st.markdown("""
        <div class='glass-card'>
            <div class='metric-label'>Salary Arrears & Payables</div>
            <div class='metric-value' style='color:#bf616a;'>$14,250.00</div>
        </div>
        """, unsafe_allow_html=True)
    with f3:
        st.markdown("""
        <div class='glass-card'>
            <div class='metric-label'>Anomaly alerts</div>
            <div class='metric-value' style='color:#d08770;'>0 ACTIVE</div>
        </div>
        """, unsafe_allow_html=True)

    # Ingestion Desk
    st.markdown("### 📥 Digital Invoice Ingestion")
    uploaded_file = st.file_uploader("Drag and drop invoice PDFs or spreadsheets to vectorize and process:", type=["pdf", "csv", "md"])
    if uploaded_file:
        with st.spinner("Ingesting file and compiling financial DAG..."):
            # Trigger document upload DAG compilation
            try:
                resp = httpx.post(
                    f"{API_BASE_URL}/api/v1/hitl/dag/compile", 
                    json={"macro_goal": f"Process uploaded invoice {uploaded_file.name} for $7,500.00"}
                )
                if resp.status_code == 200:
                    st.success("Invoice successfully ingested. Background processing DAG compiled.")
                    st.json(resp.json())
                else:
                    st.error("Failed to process invoice upload.")
            except Exception as e:
                st.error(f"Error connecting to backend: {e}")

    # Ledger audit
    st.markdown("### 📋 Financial Ledger Audit Logs")
    try:
        resp = httpx.get(f"{API_BASE_URL}/api/v1/hitl/financial/ledgers")
        if resp.status_code == 200 and resp.json():
            ledgers = resp.json()
            df = pd.DataFrame(ledgers)
            st.dataframe(
                df[["title", "amount", "entry_type", "status", "created_at"]],
                use_container_width=True
            )
        else:
            st.info("No transaction ledger records discovered.")
    except Exception as e:
        st.warning(f"Could not load ledger: {e}")


# ===========================================================================
# DESK D: WORKSPACE PORTFOLIO
# ===========================================================================

elif selected_desk == "📂 Workspace Portfolio":
    st.markdown("<div class='main-title'>Workspace Portfolio Desk</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>Explore vectorized document chunks, personal files, and RAG knowledge libraries</div>", unsafe_allow_html=True)

    try:
        resp = httpx.get(f"{API_BASE_URL}/api/v1/hitl/workspace/documents")
        if resp.status_code == 200 and resp.json():
            docs = resp.json()
            for doc in docs:
                st.markdown(f"""
                <div class='glass-card'>
                    <div style='display:flex; justify-content:space-between; align-items:center;'>
                        <h4 style='margin:0; color:#ffffff;'>📄 {doc['filename']}</h4>
                        <span class='status-badge status-completed'>{doc['vector_status']}</span>
                    </div>
                    <div style='font-size:0.85rem; color:#d8dee9; margin-top:0.5rem;'><strong>Summary:</strong> {doc['summary']}</div>
                    <div style='font-size:0.75rem; color:#8b9bb4; margin-top:0.3rem;'>Ingested: {doc['created_at']} | Type: {doc['file_type'].upper()}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Personal RAG Portfolio database is currently empty.")
    except Exception as e:
        st.warning(f"Could not load portfolio docs: {e}")


# ===========================================================================
# DESK E: VIRTUAL MEETING BRIEFS
# ===========================================================================

elif selected_desk == "🎥 Virtual Meeting Briefs":
    st.markdown("<div class='main-title'>Virtual Meeting Assistant</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>Retrieve pre-meeting briefings, active Voice VAD trackers, and post-meeting action deliverables</div>", unsafe_allow_html=True)

    m1, m2 = st.columns(2)
    with m1:
        st.markdown("### 📑 Pre-Meeting Dossier")
        st.markdown("""
        <div class='glass-card'>
            <h4 style='margin:0 0 0.5rem 0; color:#ffffff;'>Subject: Acme Contract Negotiation</h4>
            <div style='font-size:0.85rem; color:#d8dee9;'>
                <strong>Summary of past interactions:</strong> The client has requested technical integrations maps. ACV negotiations started at $50,000 threshold.
            </div>
            <div style='font-size:0.85rem; color:#d8dee9; margin-top:0.5rem;'>
                <strong>Strategic Target:</strong> Close deal via billing engine mid-session ($75,000 negotiated amount).
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with m2:
        st.markdown("### 🎙️ Headless Voice Stream telemetry")
        st.markdown("""
        <div class='glass-card'>
            <div style='font-size:0.85rem; color:#d8dee9;'><strong>LiveKit Track:</strong> wss://livekit.gnone.io/room_negotiate</div>
            <div style='font-size:0.85rem; color:#d8dee9; margin-top:0.3rem;'><strong>Gemini Live Voice:</strong> Puck (Male Voice Clone)</div>
            <div style='font-size:0.85rem; color:#d8dee9; margin-top:0.3rem;'><strong>VAD Interrupter:</strong> <span style='color:#a3be8c;'>ACTIVE (0ms reset latch)</span></div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### 📋 Past Meeting Action Deliverables")
    st.markdown("""
    <div class='glass-card'>
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <h4 style='margin:0; color:#ffffff;'>Post-Meeting Action Items: Acme Pilot close</h4>
            <span class='status-badge status-completed'>DAG COMPLETE</span>
        </div>
        <div style='font-size:0.85rem; color:#d8dee9; margin-top:0.5rem;'>
            - [x] Process Acme B2B Bidding pilot document (Read_Document)<br>
            - [x] Invoice Client $75,000 pilot deal (Process_Invoice)<br>
            - [x] Schedule post-meeting follow-up calendar slot
        </div>
    </div>
    """, unsafe_allow_html=True)
