import pytest
from unittest.mock import Mock, patch
from core.llm_router import LLMRouter, ModelProfile, Provider, RoutingDecision

@pytest.fixture
def mock_reliability_manager():
    with patch("core.llm_router.ReliabilityManager") as mock:
        yield mock

@pytest.fixture
def mock_cache_manager():
    with patch("core.llm_router.CacheManager") as mock:
        yield mock

@pytest.fixture
def router(mock_reliability_manager, mock_cache_manager):
    config = {"providers": {}} # Empty config to avoid side effects during init
    router = LLMRouter(config)

    # Manually populate models with diverse test data
    router.models = {
        "provider1/model1": ModelProfile(
            provider=Provider.OPENAI,
            model_id="model1",
            display_name="Expensive Model",
            context_window=1000,
            cost_per_1k_input=0.1,
            cost_per_1k_output=0.1,
            speed_tier="medium",
            capability_tier="reasoning",
            supports_json=True,
            success_rate=0.9
        ),
        "provider2/model2": ModelProfile(
            provider=Provider.ANTHROPIC,
            model_id="model2",
            display_name="Cheap Model",
            context_window=1000,
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.01,
            speed_tier="fast",
            capability_tier="general",
            supports_json=True,
            success_rate=0.8
        ),
        "provider3/model3": ModelProfile(
            provider=Provider.OLLAMA,
            model_id="model3",
            display_name="Local Model",
            context_window=1000,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            speed_tier="slow",
            capability_tier="general",
            supports_json=False,
            is_local=True,
            success_rate=0.95
        ),
         "provider4/model4": ModelProfile(
            provider=Provider.GROQ,
            model_id="model4",
            display_name="Fast Model",
            context_window=1000,
            cost_per_1k_input=0.05,
            cost_per_1k_output=0.05,
            speed_tier="fast",
            capability_tier="general",
            supports_json=True,
            success_rate=0.7
        ),
    }
    return router

def test_select_model_basic(router):
    decision = router.select_model(task_type="general", priority="balanced", require_json=True)
    assert isinstance(decision, RoutingDecision)
    assert decision.model.supports_json is True
    # Should pick highest success rate among json supported models
    # model1: 0.9, model2: 0.8, model4: 0.7. model3 is excluded due to no json support.
    assert decision.model.model_id == "model1"

def test_select_model_require_json(router):
    # Test require_json=False allows non-json models
    decision = router.select_model(task_type="general", priority="balanced", require_json=False)
    # With balanced priority (success rate), model3 (0.95) should win over model1 (0.9)
    assert decision.model.model_id == "model3"

    # Test require_json=True filters out non-json models
    decision_json = router.select_model(task_type="general", priority="balanced", require_json=True)
    assert decision_json.model.supports_json is True
    assert decision_json.model.model_id != "model3"

def test_select_model_priority_cost(router):
    # Cost priority: prefers local models first (is_local=True), then lower cost
    # model3 is local. model2 is cheap. model1 is expensive.

    # Case 1: require_json=False (allows model3)
    decision = router.select_model(priority="cost", require_json=False)
    assert decision.model.is_local is True
    assert decision.model.model_id == "model3"

    # Case 2: require_json=True (excludes model3)
    # Remaining: model1 (0.1), model2 (0.01), model4 (0.05)
    # Expected: model2 (lowest cost among non-local)
    decision = router.select_model(priority="cost", require_json=True)
    assert decision.model.model_id == "model2"

def test_select_model_priority_balanced(router):
    # Balanced priority uses success_rate desc
    # model3 (0.95), model1 (0.9), model2 (0.8), model4 (0.7)

    decision = router.select_model(priority="balanced", require_json=False)
    assert decision.model.model_id == "model3"

    decision = router.select_model(priority="balanced", require_json=True)
    assert decision.model.model_id == "model1"

def test_select_model_no_candidates(router):
    # Create a router with no models
    router.models = {}
    with pytest.raises(ValueError, match="No suitable models found"):
        router.select_model()

    # Create a router with only non-json models and request json
    router.models = {
         "provider3/model3": ModelProfile(
            provider=Provider.OLLAMA,
            model_id="model3",
            display_name="Local Model",
            context_window=1000,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            speed_tier="slow",
            capability_tier="general",
            supports_json=False,
            is_local=True,
            success_rate=0.95
        )
    }
    with pytest.raises(ValueError, match="No suitable models found"):
        router.select_model(require_json=True)

def test_select_model_fallback(router):
    decision = router.select_model(priority="balanced", require_json=True)
    # Candidates sorted by success rate (desc): model1 (0.9), model2 (0.8), model4 (0.7)
    # Best: model1
    # Fallbacks: model2, model4

    assert len(decision.fallback_chain) == 2
    assert decision.fallback_chain[0].model_id == "model2"
    assert decision.fallback_chain[1].model_id == "model4"
