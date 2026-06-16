import pytest

from app.models.content_models import (
    BlogspotPost,
    FacebookPost,
    LinkedInPost,
    MultiPlatformContent,
    TwitterThread,
)


@pytest.fixture
def sample_twitter_thread() -> TwitterThread:
    return TwitterThread(posts=[
        "AGI timelines are compressing faster than most realize. Thread on what changed in 2026.",
        "1/ AlphaProof solved IMO gold medal problems. That's not just a flex, it's a paradigm shift in how we train reasoning models.",
        "2/ Inference costs dropped another 10x. The marginal cost of intelligence is approaching zero.",
        "3/ Multimodal is now table stakes. Every model ships vision, audio, and text natively.",
        "4/ Regulation is accelerating. EU AI Act enforcement begins Q3. US executive orders are shaping compute governance.",
        "5/ Open-weight models are eating the world. Llama 4, DeepSeek V4, Qwen 3 — all within 5% of GPT-5 on key benchmarks.",
        "Summary: The bottleneck is no longer capability. It's alignment, regulation, and distribution.",
    ])


@pytest.fixture
def sample_linkedin_post() -> LinkedInPost:
    return LinkedInPost(
        body="The AI landscape in 2026 demands a fundamentally different approach to enterprise deployment.\n\n"
             "• Costs have collapsed 10x year-over-year for inference\n"
             "• Multimodal capabilities are now standard across all major providers\n"
             "• Open-weight models rival proprietary systems within 5%",
        hashtags=["#ArtificialIntelligence", "#EnterpriseTech", "#AITransformation"],
    )


@pytest.fixture
def sample_facebook_post() -> FacebookPost:
    return FacebookPost(
        body="I've been watching the AI space evolve in real-time, and honestly? "
             "The pace is staggering. Open models are now competing with the big players. "
             "What do you think — is open-source AI the future or a risk?",
        call_to_action="Drop your thoughts in the comments!",
    )


@pytest.fixture
def sample_blogspot_post() -> BlogspotPost:
    _long_text = (
        "Inference costs have dropped 10x year-over-year. "
        "Open-weight models now rival proprietary systems across every benchmark. "
        "The regulatory landscape is shifting with new EU AI Act enforcement. "
        "Multimodal capabilities are now standard across all major providers. "
        "Enterprise adoption continues to accelerate as costs decrease. "
        "Security and alignment remain critical challenges for deployment. "
    ) * 20
    return BlogspotPost(
        title="The 2026 AI Landscape: Open Models, Falling Costs, and Regulatory Reality",
        seo_slug="2026-ai-landscape-open-models-falling-costs",
        meta_description="Explore the 2026 AI landscape: open-weight models, 10x cost reductions, and new regulations.",
        html_body=f"<h2>The Cost Collapse</h2><p>{_long_text}</p>"
                  f"<h3>Open Models Lead</h3><p>Llama 4 and DeepSeek V4 rival proprietary systems. {_long_text}</p>",
    )


@pytest.fixture
def sample_multiplatform_content(
    sample_twitter_thread,
    sample_linkedin_post,
    sample_facebook_post,
    sample_blogspot_post,
) -> MultiPlatformContent:
    return MultiPlatformContent(
        twitter=sample_twitter_thread,
        linkedin=sample_linkedin_post,
        facebook=sample_facebook_post,
        blogspot=sample_blogspot_post,
    )
