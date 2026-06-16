"""Mock client for Gemini API testing with input validation."""


def _build_mock_utd(topic: str) -> str:
    return (
        f"Unified Truth Document: {topic}\n\n"
        f"Analysis of {topic} reveals three critical developments. "
        f"First, industry leaders have accelerated investment in {topic}-related "
        f"infrastructure, driving a 40% increase in adoption rates year-over-year "
        f"[source: industry-report-2026]. "
        f"Second, regulatory bodies are actively shaping policy around {topic} "
        f"to ensure responsible deployment [source: regulatory-watchdog.org]. "
        f"Third, open-source alternatives have emerged that lower the barrier "
        f"to entry for smaller organizations [source: oss-adoption-tracker.io].\n"
        f"[UNVERIFIED] Early-stage projections suggest {topic} could "
        f"reshape market dynamics within 18 months.\n"
        f"[source: market-analysis-q2-2026]"
    )


async def mock_research_topic(topic: str, brand_voice: str = None) -> str:
    if not isinstance(topic, str) or len(topic) < 10 or len(topic) > 2000:
        raise ValueError(
            f"topic must be a string between 10 and 2000 characters, got {len(topic) if isinstance(topic, str) else type(topic)}"
        )
    if brand_voice is not None and (not isinstance(brand_voice, str) or len(brand_voice) > 1000):
        raise ValueError("brand_voice must be a string of at most 1000 characters")
    return _build_mock_utd(topic)
