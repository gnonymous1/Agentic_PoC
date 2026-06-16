"""GNONE Content Studio — Streamlit frontend for the GNONE content manufacturing platform."""

import asyncio
from datetime import datetime
from uuid import uuid4

import streamlit as st

st.set_page_config(page_title="GNONE Content Studio", page_icon=":brain:", layout="wide")

# ── Patch service functions with mock implementations ────────────────────
import app.services.gemini_grounding as gg
import app.agents.research_agent as ra
import app.services.openrouter_generator as og
import app.agents.copywriting_agent as ca
import app.services.critic_loop as cl
import app.agents.critic_agent as cra
from tests.mocks.mock_gemini import mock_research_topic
from tests.mocks.mock_openrouter import mock_generate_platform_content
from tests.mocks.mock_critic import (
    mock_call_critic_eval,
    mock_call_critic_correct,
    mock_critic_verification_loop,
)

gg.research_topic = mock_research_topic
ra.research_topic = mock_research_topic
og.generate_platform_content = mock_generate_platform_content
ca.generate_platform_content = mock_generate_platform_content
cl.call_critic_eval = mock_call_critic_eval
cl.call_critic_correct = mock_call_critic_correct
cra.critic_verification_loop = mock_critic_verification_loop


async def _run_pipeline(topic: str, brand_voice: str) -> dict:
    from app.core.orchestrator import DAGOrchestrator, AgentContext
    from app.agents.research_agent import ResearchAgent
    from app.agents.copywriting_agent import CopywritingAgent
    from app.agents.critic_agent import CriticAgent
    from app.agents.moderator_agent import ModeratorAgent

    request_id = str(uuid4())
    orchestrator = DAGOrchestrator()
    orchestrator.register(ResearchAgent())
    orchestrator.register(CopywritingAgent(), depends_on=["research_agent"])
    orchestrator.register(CriticAgent(), depends_on=["copywriting_agent"])
    orchestrator.register(ModeratorAgent(), depends_on=["critic_agent"])

    ctx = AgentContext(
        correlation_id=request_id,
        topic=topic,
        brand_voice=brand_voice or "",
    )
    ctx = await orchestrator.run(ctx)

    return {
        "request_id": request_id,
        "topic": topic,
        "unified_truth_document": ctx.unified_truth_document,
        "generated_content": ctx.generated_content,
        "critic_approved": ctx.critic_approved,
        "refinement_cycles": ctx.refinement_cycles,
        "created_at": datetime.utcnow(),
    }


# ── UI ───────────────────────────────────────────────────────────────────

st.markdown(
    "<h1 style='text-align:center; margin-bottom:0;'>"
    ":brain: GNONE Content Studio"
    "</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align:center; color:#888; margin-top:0;'>"
    "Multi-agent content manufacturing pipeline</p>",
    unsafe_allow_html=True,
)

topic = st.text_area(
    "Topic",
    height=120,
    placeholder="Enter your topic seed or news snippet (10–2000 characters)...",
)
if topic:
    st.caption(f"{len(topic)} / 2000 characters")

col_bv, _ = st.columns([2, 1])
with col_bv:
    brand_voice = st.text_input(
        "Brand Voice Override (optional)",
        placeholder="e.g., Professional, authoritative, data-driven",
        max_chars=1000,
    )

platforms = st.multiselect(
    "Target Platforms",
    ["twitter", "linkedin", "facebook", "blogspot"],
    default=["twitter", "linkedin", "facebook", "blogspot"],
)

if st.button("Generate Content", type="primary", use_container_width=True):
    if not topic or len(topic) < 10:
        st.error("Topic must be at least 10 characters.")
    elif len(topic) > 2000:
        st.error("Topic must not exceed 2000 characters.")
    else:
        with st.spinner("Running content manufacturing pipeline..."):
            try:
                result = asyncio.run(_run_pipeline(topic, brand_voice))
            except Exception as e:
                st.error(f"Pipeline failed: {e}")
                st.stop()

        st.success("Content generated successfully!")

        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Critic Approved",
            ":white_check_mark: Yes" if result["critic_approved"] else ":x: No",
        )
        col2.metric("Refinement Cycles", result["refinement_cycles"])
        col3.metric("Request ID", result["request_id"][:8] + "...")

        _filtered = [p for p in platforms if p in result["generated_content"]]
        if _filtered:
            tabs = st.tabs([p.title() for p in _filtered])
            for tab, platform in zip(tabs, _filtered):
                content = result["generated_content"][platform]
                with tab:
                    if platform == "twitter":
                        for i, post in enumerate(content.get("posts", []), 1):
                            cc = len(post)
                            st.markdown(f"**Post {i}** — {cc}/240 chars")
                            st.info(post)
                            st.progress(min(cc / 240, 1.0))
                            st.divider()
                    elif platform == "linkedin":
                        st.markdown(content.get("body", ""))
                        tags = content.get("hashtags", [])
                        if tags:
                            st.markdown(" ".join(tags))
                    elif platform == "facebook":
                        st.markdown(content.get("body", ""))
                        cta = content.get("call_to_action")
                        if cta:
                            st.markdown(f"**CTA:** {cta}")
                    elif platform == "blogspot":
                        st.markdown(f"**{content.get('title', '')}**")
                        st.markdown(f"*Slug:* `{content.get('seo_slug', '')}`")
                        st.markdown(f"*Meta:* {content.get('meta_description', '')}")
                        st.components.v1.html(
                            content.get("html_body", ""),
                            scrolling=True,
                            height=500,
                        )

        with st.expander("View Unified Truth Document"):
            st.text(result["unified_truth_document"])
