"""Mock client for OpenRouter API testing with input validation."""

from app.models.content_models import (
    MultiPlatformContent,
)


def _build_mock_content(topic: str) -> dict:
    return {
        "twitter": {
            "posts": [
                f"{topic} is transforming the industry faster than anticipated.",
                f"Key developments in {topic} are reshaping competitive dynamics.",
                f"Enterprise adoption of {topic} has grown 3x in the last year.",
                f"Regulatory frameworks for {topic} are taking shape globally.",
                f"The next wave of {topic} innovation is already underway.",
            ]
        },
        "linkedin": {
            "body": f"The evolution of {topic} demands strategic attention.\n\n"
                    f"• Market leaders are investing heavily in {topic}\n"
                    f"• Adoption costs have decreased significantly\n"
                    f"• Regulatory compliance is becoming a priority",
            "hashtags": ["#TechTrends", "#Innovation"],
        },
        "facebook": {
            "body": f"Have you been following the latest developments in {topic}? "
                    f"The pace of change is remarkable, and it is affecting everyone.",
            "call_to_action": "Share your thoughts below!",
        },
        "blogspot": {
            "title": f"Understanding {topic} in 2026",
            "seo_slug": f"understanding-{topic.lower().replace(' ', '-')}-2026",
            "meta_description": f"A comprehensive analysis of {topic} and its impact on the modern enterprise.",
            "html_body": f"<h2>Introduction to {topic}</h2>"
                        f"<p>{topic} represents a <strong>fundamental shift</strong> "
                        f"in how organizations operate. " + (" ".join([f"This is a placeholder sentence about {topic} that repeats to reach the minimum word count required for validation purposes." for _ in range(15)])) + "</p>"
                        "<h3>Current State</h3>"
                        "<p>" + (" ".join([f"Organizations across every sector are exploring {topic} and investing heavily in new capabilities to stay competitive in an increasingly digital landscape." for _ in range(20)])) + "</p>"
                        "<h3>Key Trends</h3>"
                        "<p>" + (" ".join([f"Multiple trends are converging to make {topic} more accessible and impactful than ever before in the history of technology adoption cycles." for _ in range(20)])) + "</p>",
        },
    }


def _safe_topic(utd: str) -> str:
    raw = utd.split(":")[1].strip().split("\n")[0] if ":" in utd else "AI Technology"
    if len(raw) > 50:
        raw = raw[:47] + "..."
    return raw


async def mock_generate_platform_content(utd: str, brand_voice: str = None) -> MultiPlatformContent:
    if not utd or not isinstance(utd, str):
        raise ValueError("utd must be a non-empty string")
    topic = _safe_topic(utd)
    return MultiPlatformContent.model_validate(_build_mock_content(topic))
