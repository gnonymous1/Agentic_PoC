import pytest
from pydantic import ValidationError

from app.models.agent_contracts import (
    CopywritingContract,
    CriticVerdict,
    ModeratorVerdict,
    ResearchContract,
)


class TestResearchContract:
    def test_valid_contract(self):
        contract = ResearchContract(
            topic="AI in 2026",
            unified_truth_document=" ".join(["word"] * 200),
        )
        assert contract.confidence_score == 0.0

    def test_utd_too_short(self):
        with pytest.raises(ValidationError):
            ResearchContract(
                topic="AI",
                unified_truth_document="Too short",
            )


class TestCopywritingContract:
    def test_valid_contract(self):
        _long = "Long enough content for validation purposes. " * 20
        contract = CopywritingContract(
            utd_summary="Summary text",
            twitter_thread=["Post 1", "Post 2", "Post 3", "Post 4", "Post 5"],
            linkedin_body=_long,
            facebook_body=_long,
            blogspot_html="<h2>Heading</h2>" * 30,
        )
        assert len(contract.twitter_thread) == 5

    def test_twitter_too_long(self):
        with pytest.raises(ValidationError):
            CopywritingContract(
                utd_summary="Summary",
                twitter_thread=["X" * 241] * 5,
                linkedin_body="LinkedIn body",
                facebook_body="Facebook body",
                blogspot_html="<p>Blog</p>" * 10,
            )


class TestCriticVerdict:
    def test_approved_verdict(self):
        verdict = CriticVerdict(approved=True, critic_confidence=0.95)
        assert verdict.approved
        assert verdict.critic_confidence == 0.95

    def test_critic_confidence_range(self):
        with pytest.raises(ValidationError):
            CriticVerdict(approved=False, critic_confidence=1.5)


class TestModeratorVerdict:
    def test_clean_content(self):
        verdict = ModeratorVerdict(passed_safety_check=True)
        assert verdict.content_safe

    def test_flagged_content(self):
        verdict = ModeratorVerdict(
            passed_safety_check=False,
            flagged_categories=["hate_speech", "profanity"],
        )
        assert not verdict.passed_safety_check
