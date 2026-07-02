"""Tests for LLM providers and multi-model scheduler."""

from __future__ import annotations

import pytest

from agent_collab.llm import (
    AnthropicProvider,
    GoogleProvider,
    LLMConfig,
    LLMResponse,
    OpenAIProvider,
    get_provider,
)
from agent_collab.llm.moa import MoAConfig, MoAEngine
from agent_collab.llm.scheduler import (
    ModelConfig,
    ModelStats,
    MultiModelScheduler,
    SchedulerConfig,
    SelectionStrategy,
)


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_default_values(self):
        config = LLMConfig(provider="openai", model="gpt-4o")
        assert config.provider == "openai"
        assert config.model == "gpt-4o"
        assert config.api_key is None
        assert config.base_url is None
        assert config.max_tokens == 4096
        assert config.temperature == 0.7
        assert config.timeout == 60
        assert config.retry_attempts == 3
        assert config.retry_delay == 1.0

    def test_custom_values(self):
        config = LLMConfig(
            provider="anthropic",
            model="claude-3-opus",
            api_key="test-key",
            base_url="https://custom.api.com",
            max_tokens=8192,
            temperature=0.5,
            timeout=120,
            retry_attempts=5,
            retry_delay=2.0,
        )
        assert config.provider == "anthropic"
        assert config.model == "claude-3-opus"
        assert config.api_key == "test-key"
        assert config.base_url == "https://custom.api.com"
        assert config.max_tokens == 8192
        assert config.temperature == 0.5
        assert config.timeout == 120
        assert config.retry_attempts == 5
        assert config.retry_delay == 2.0


class TestLLMResponse:
    """Tests for LLMResponse."""

    def test_default_values(self):
        response = LLMResponse(content="test", model="gpt-4o", provider="openai")
        assert response.content == "test"
        assert response.model == "gpt-4o"
        assert response.provider == "openai"
        assert response.input_tokens == 0
        assert response.output_tokens == 0
        assert response.total_tokens == 0
        assert response.cost_usd == 0.0
        assert response.latency_seconds == 0.0
        assert response.metadata == {}

    def test_custom_values(self):
        response = LLMResponse(
            content="test response",
            model="claude-3-opus",
            provider="anthropic",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost_usd=0.01,
            latency_seconds=1.5,
            metadata={"key": "value"},
        )
        assert response.content == "test response"
        assert response.input_tokens == 100
        assert response.output_tokens == 50
        assert response.total_tokens == 150
        assert response.cost_usd == 0.01
        assert response.latency_seconds == 1.5
        assert response.metadata == {"key": "value"}


class TestOpenAIProvider:
    """Tests for OpenAIProvider."""

    def test_name(self):
        config = LLMConfig(provider="openai", model="gpt-4o")
        provider = OpenAIProvider(config)
        assert provider.name == "openai"

    def test_models(self):
        config = LLMConfig(provider="openai", model="gpt-4o")
        provider = OpenAIProvider(config)
        assert "gpt-4o" in provider.models
        assert "gpt-4o-mini" in provider.models
        assert "gpt-4-turbo" in provider.models

    def test_is_available_with_key(self):
        config = LLMConfig(provider="openai", model="gpt-4o", api_key="test-key")
        provider = OpenAIProvider(config)
        assert provider.is_available() is True

    def test_is_available_without_key(self):
        config = LLMConfig(provider="openai", model="gpt-4o")
        provider = OpenAIProvider(config)
        assert provider.is_available() is False


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""

    def test_name(self):
        config = LLMConfig(provider="anthropic", model="claude-3-opus")
        provider = AnthropicProvider(config)
        assert provider.name == "anthropic"

    def test_models(self):
        config = LLMConfig(provider="anthropic", model="claude-3-opus")
        provider = AnthropicProvider(config)
        assert "claude-3-opus-20240229" in provider.models
        assert "claude-3-sonnet-20240229" in provider.models


class TestGoogleProvider:
    """Tests for GoogleProvider."""

    def test_name(self):
        config = LLMConfig(provider="google", model="gemini-1.5-pro")
        provider = GoogleProvider(config)
        assert provider.name == "google"

    def test_models(self):
        config = LLMConfig(provider="google", model="gemini-1.5-pro")
        provider = GoogleProvider(config)
        assert "gemini-1.5-pro" in provider.models
        assert "gemini-1.5-flash" in provider.models


class TestGetProvider:
    """Tests for get_provider function."""

    def test_get_openai_provider(self):
        config = LLMConfig(provider="openai", model="gpt-4o", api_key="test-key")
        provider = get_provider(config)
        assert isinstance(provider, OpenAIProvider)
        assert provider.name == "openai"

    def test_get_anthropic_provider(self):
        config = LLMConfig(provider="anthropic", model="claude-3-opus", api_key="test-key")
        provider = get_provider(config)
        assert isinstance(provider, AnthropicProvider)
        assert provider.name == "anthropic"

    def test_get_google_provider(self):
        config = LLMConfig(provider="google", model="gemini-1.5-pro", api_key="test-key")
        provider = get_provider(config)
        assert isinstance(provider, GoogleProvider)
        assert provider.name == "google"

    def test_get_unsupported_provider(self):
        config = LLMConfig(provider="unsupported", model="test")
        with pytest.raises(ValueError, match="Unsupported provider"):
            get_provider(config)


class TestModelStats:
    """Tests for ModelStats."""

    def test_default_values(self):
        stats = ModelStats()
        assert stats.total_calls == 0
        assert stats.successful_calls == 0
        assert stats.failed_calls == 0
        assert stats.total_input_tokens == 0
        assert stats.total_output_tokens == 0
        assert stats.total_cost_usd == 0.0
        assert stats.total_latency_seconds == 0.0
        assert stats.avg_latency_seconds == 0.0

    def test_update_success(self):
        stats = ModelStats()
        response = LLMResponse(
            content="test",
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
            latency_seconds=1.5,
        )
        stats.update(response, success=True)
        assert stats.total_calls == 1
        assert stats.successful_calls == 1
        assert stats.failed_calls == 0
        assert stats.total_input_tokens == 100
        assert stats.total_output_tokens == 50
        assert stats.total_cost_usd == 0.01
        assert stats.total_latency_seconds == 1.5
        assert stats.avg_latency_seconds == 1.5

    def test_update_failure(self):
        stats = ModelStats()
        response = LLMResponse(
            content="",
            model="gpt-4o",
            provider="openai",
        )
        stats.update(response, success=False)
        assert stats.total_calls == 1
        assert stats.successful_calls == 0
        assert stats.failed_calls == 1


class TestMultiModelScheduler:
    """Tests for MultiModelScheduler."""

    def test_initialization(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
                ModelConfig(provider="anthropic", model="claude-3-opus", api_key="key2"),
            ],
            strategy=SelectionStrategy.QUALITY_FIRST,
        )
        scheduler = MultiModelScheduler(config)
        assert len(scheduler._providers) == 2
        assert "openai/gpt-4o" in scheduler._providers
        assert "anthropic/claude-3-opus" in scheduler._providers

    def test_initialization_with_disabled_model(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
                ModelConfig(
                    provider="anthropic",
                    model="claude-3-opus",
                    api_key="key2",
                    enabled=False,
                ),
            ],
        )
        scheduler = MultiModelScheduler(config)
        assert len(scheduler._providers) == 1
        assert "openai/gpt-4o" in scheduler._providers
        assert "anthropic/claude-3-opus" not in scheduler._providers

    def test_select_round_robin(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
                ModelConfig(provider="anthropic", model="claude-3-opus", api_key="key2"),
            ],
            strategy=SelectionStrategy.ROUND_ROBIN,
        )
        scheduler = MultiModelScheduler(config)

        key1, _ = scheduler._select_provider()
        key2, _ = scheduler._select_provider()
        key3, _ = scheduler._select_provider()

        assert key1 != key2
        assert key1 == key3

    def test_select_cost_optimized(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(
                    provider="openai",
                    model="gpt-4o",
                    api_key="key1",
                    cost_per_1k_input=0.01,
                ),
                ModelConfig(
                    provider="anthropic",
                    model="claude-3-opus",
                    api_key="key2",
                    cost_per_1k_input=0.015,
                ),
            ],
            strategy=SelectionStrategy.COST_OPTIMIZED,
        )
        scheduler = MultiModelScheduler(config)

        key, _ = scheduler._select_provider()
        assert key == "openai/gpt-4o"

    def test_select_quality_first(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(
                    provider="openai",
                    model="gpt-4o",
                    api_key="key1",
                    quality_score=0.8,
                ),
                ModelConfig(
                    provider="anthropic",
                    model="claude-3-opus",
                    api_key="key2",
                    quality_score=0.9,
                ),
            ],
            strategy=SelectionStrategy.QUALITY_FIRST,
        )
        scheduler = MultiModelScheduler(config)

        key, _ = scheduler._select_provider()
        assert key == "anthropic/claude-3-opus"

    def test_get_stats(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(config)

        stats = scheduler.get_stats()
        assert "openai/gpt-4o" in stats
        assert stats["openai/gpt-4o"].total_calls == 0

    def test_get_total_cost(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(config)

        assert scheduler.get_total_cost() == 0.0

    def test_get_total_tokens(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(config)

        input_tokens, output_tokens = scheduler.get_total_tokens()
        assert input_tokens == 0
        assert output_tokens == 0

    def test_reset_stats(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(config)

        # Manually update stats
        scheduler._stats["openai/gpt-4o"].total_calls = 10
        scheduler._stats["openai/gpt-4o"].total_cost_usd = 0.5

        scheduler.reset_stats()
        assert scheduler._stats["openai/gpt-4o"].total_calls == 0
        assert scheduler._stats["openai/gpt-4o"].total_cost_usd == 0.0


class TestMoAConfig:
    """Tests for MoAConfig."""

    def test_default_values(self):
        config = MoAConfig(
            reference_models=["gpt-4o", "claude-3-opus"],
            aggregator_model="gpt-4o",
        )
        assert config.reference_models == ["gpt-4o", "claude-3-opus"]
        assert config.aggregator_model == "gpt-4o"
        assert config.num_reference_rounds == 2
        assert config.num_references_per_round == 3
        assert config.temperature == 0.7
        assert config.max_tokens == 4096

    def test_custom_values(self):
        config = MoAConfig(
            reference_models=["gpt-4o", "claude-3-opus", "gemini-1.5-pro"],
            aggregator_model="claude-3-opus",
            num_reference_rounds=3,
            num_references_per_round=5,
            temperature=0.5,
            max_tokens=8192,
        )
        assert config.num_reference_rounds == 3
        assert config.num_references_per_round == 5
        assert config.temperature == 0.5
        assert config.max_tokens == 8192


class TestMoAEngine:
    """Tests for MoAEngine."""

    def test_initialization(self):
        scheduler_config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(scheduler_config)

        moa_config = MoAConfig(
            reference_models=["gpt-4o"],
            aggregator_model="gpt-4o",
        )
        engine = MoAEngine(scheduler, moa_config)
        assert engine.scheduler == scheduler
        assert engine.config == moa_config

    def test_create_reference_prompt_first_round(self):
        scheduler_config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(scheduler_config)

        moa_config = MoAConfig(
            reference_models=["gpt-4o"],
            aggregator_model="gpt-4o",
        )
        engine = MoAEngine(scheduler, moa_config)

        prompt = engine._create_reference_prompt("test prompt", [], 0)
        assert prompt == "test prompt"

    def test_create_reference_prompt_subsequent_round(self):
        scheduler_config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(scheduler_config)

        moa_config = MoAConfig(
            reference_models=["gpt-4o"],
            aggregator_model="gpt-4o",
        )
        engine = MoAEngine(scheduler, moa_config)

        previous_responses = [
            LLMResponse(content="response 1", model="gpt-4o", provider="openai"),
            LLMResponse(content="response 2", model="gpt-4o", provider="openai"),
        ]
        prompt = engine._create_reference_prompt("test prompt", previous_responses, 1)
        assert "Original prompt: test prompt" in prompt
        assert "Reference 1:" in prompt
        assert "response 1" in prompt
        assert "Reference 2:" in prompt
        assert "response 2" in prompt

    def test_create_aggregator_prompt(self):
        scheduler_config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(scheduler_config)

        moa_config = MoAConfig(
            reference_models=["gpt-4o"],
            aggregator_model="gpt-4o",
        )
        engine = MoAEngine(scheduler, moa_config)

        reference_responses = [
            LLMResponse(content="response 1", model="gpt-4o", provider="openai"),
            LLMResponse(content="response 2", model="gpt-4o", provider="openai"),
        ]
        prompt = engine._create_aggregator_prompt("test prompt", reference_responses)
        assert "Original prompt: test prompt" in prompt
        assert "Multiple models have provided their responses:" in prompt
        assert "Reference 1:" in prompt
        assert "response 1" in prompt
        assert "Reference 2:" in prompt
        assert "response 2" in prompt
        assert "Please synthesize these responses" in prompt


class TestMoAEngineAsync:
    """Async tests for MoAEngine."""

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test MoAEngine.generate with a mock scheduler."""
        from unittest.mock import AsyncMock

        scheduler_config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
                ModelConfig(provider="openai", model="gpt-4o-mini", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(scheduler_config)

        # Mock providers to avoid real API calls
        mock_response = LLMResponse(
            content="test response",
            model="gpt-4o",
            provider="openai",
            input_tokens=10,
            output_tokens=20,
            cost_usd=0.001,
            latency_seconds=0.5,
        )

        # Replace providers with mocks
        for key in scheduler._providers:
            provider = scheduler._providers[key]
            provider.generate = AsyncMock(return_value=mock_response)

        moa_config = MoAConfig(
            reference_models=["gpt-4o"],
            aggregator_model="gpt-4o",
            num_reference_rounds=1,
            num_references_per_round=2,
        )
        engine = MoAEngine(scheduler, moa_config)

        result = await engine.generate("test prompt")

        assert result.content == "test response"
        assert len(result.reference_responses) == 2  # 1 round × 2 references
        assert result.aggregator_response is not None
        assert result.aggregator_response.content == "test response"
        assert result.total_input_tokens > 0
        assert result.total_output_tokens > 0

    @pytest.mark.asyncio
    async def test_generate_with_reference_failures(self):
        """Test MoAEngine.generate handles reference model failures gracefully."""
        scheduler_config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(scheduler_config)

        mock_response = LLMResponse(
            content="aggregated",
            model="gpt-4o",
            provider="openai",
            input_tokens=5,
            output_tokens=10,
        )

        call_count = [0]

        async def mock_generate(prompt, system_prompt=None, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 3:  # First 3 calls fail (2 refs + 1 retry = exhausted)
                raise RuntimeError("Reference model failed")
            return mock_response  # Aggregator succeeds after retries

        for provider in scheduler._providers.values():
            provider.generate = mock_generate

        moa_config = MoAConfig(
            reference_models=["gpt-4o"],
            aggregator_model="gpt-4o",
            num_reference_rounds=1,
            num_references_per_round=1,
        )
        engine = MoAEngine(scheduler, moa_config)

        result = await engine.generate("test prompt")

        # Should still produce result from aggregator
        assert result.content == "aggregated"
        # Failed references should be skipped (gather with return_exceptions catches the errors)
        assert len(result.reference_responses) == 0

    @pytest.mark.asyncio
    async def test_generate_with_system_prompt(self):
        """Test MoAEngine.generate passes system_prompt through."""
        from unittest.mock import AsyncMock

        scheduler_config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(scheduler_config)

        captured_system_prompts = []

        async def mock_generate(prompt, system_prompt=None, **kwargs):
            captured_system_prompts.append(system_prompt)
            return LLMResponse(
                content="response",
                model="gpt-4o",
                provider="openai",
            )

        for provider in scheduler._providers.values():
            provider.generate = mock_generate

        moa_config = MoAConfig(
            reference_models=["gpt-4o"],
            aggregator_model="gpt-4o",
            num_reference_rounds=1,
            num_references_per_round=1,
        )
        engine = MoAEngine(scheduler, moa_config)

        await engine.generate("test prompt", system_prompt="You are a helpful assistant.")

        # System prompt should be passed to both reference and aggregator calls
        for sp in captured_system_prompts:
            assert sp == "You are a helpful assistant."


class TestSchedulerEdgeCases:
    """Edge cases for MultiModelScheduler."""

    def test_empty_providers(self):
        config = SchedulerConfig(models=[])
        scheduler = MultiModelScheduler(config)
        assert len(scheduler._providers) == 0
        with pytest.raises(RuntimeError, match="No providers available"):
            scheduler._select_provider()

    def test_no_enabled_providers(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1", enabled=False),
            ],
        )
        scheduler = MultiModelScheduler(config)
        assert len(scheduler._providers) == 0

    def test_invalid_provider_config(self):
        """Provider with unsupported type should be skipped."""
        config = SchedulerConfig(
            models=[
                ModelConfig(provider="nonexistent", model="test", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(config)
        assert len(scheduler._providers) == 0

    def test_select_random_strategy(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
                ModelConfig(provider="anthropic", model="claude-3-opus", api_key="key2"),
            ],
            strategy=SelectionStrategy.RANDOM,
        )
        scheduler = MultiModelScheduler(config)
        key, provider = scheduler._select_provider()
        assert key in ("openai/gpt-4o", "anthropic/claude-3-opus")
        assert provider is not None

    def test_select_latency_optimized(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(
                    provider="openai", model="gpt-4o", api_key="key1",
                    avg_latency_ms=500,
                ),
                ModelConfig(
                    provider="anthropic", model="claude-3-opus", api_key="key2",
                    avg_latency_ms=200,
                ),
            ],
            strategy=SelectionStrategy.LATENCY_OPTIMIZED,
        )
        scheduler = MultiModelScheduler(config)
        key, _ = scheduler._select_provider()
        assert key == "anthropic/claude-3-opus"

    def test_select_latency_optimized_with_stats(self):
        """Latency-optimized should use recorded stats when available."""
        config = SchedulerConfig(
            models=[
                ModelConfig(
                    provider="openai", model="gpt-4o", api_key="key1",
                    avg_latency_ms=1000,
                ),
                ModelConfig(
                    provider="anthropic", model="claude-3-opus", api_key="key2",
                    avg_latency_ms=200,
                ),
            ],
            strategy=SelectionStrategy.LATENCY_OPTIMIZED,
        )
        scheduler = MultiModelScheduler(config)
        # Manually set stats to override latency: openai becomes faster
        scheduler._stats["openai/gpt-4o"].avg_latency_seconds = 0.05
        scheduler._stats["openai/gpt-4o"].total_calls = 1
        scheduler._stats["openai/gpt-4o"].total_latency_seconds = 0.05
        key, _ = scheduler._select_provider()
        assert key == "openai/gpt-4o"

    def test_unknown_strategy_fallback(self):
        """Unknown strategy should fall back to first provider."""
        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(config)
        # Override strategy to unknown value
        scheduler.config.strategy = "unknown"  # type: ignore[assignment]
        key, _ = scheduler._select_provider()
        assert key == "openai/gpt-4o"


class TestBaseLLMProvider:
    """Tests for BaseLLMProvider."""

    def test_is_available_with_key(self):
        config = LLMConfig(provider="openai", model="gpt-4o", api_key="test-key")
        provider = OpenAIProvider(config)
        assert provider.is_available() is True

    def test_is_available_without_key(self):
        config = LLMConfig(provider="openai", model="gpt-4o")
        provider = OpenAIProvider(config)
        assert provider.is_available() is False

    def test_custom_base_url(self):
        config = LLMConfig(
            provider="openai", model="gpt-4o",
            api_key="test-key",
            base_url="https://custom.api.com/v1",
        )
        provider = OpenAIProvider(config)
        assert provider.config.base_url == "https://custom.api.com/v1"


class TestLLMResponseEdgeCases:
    """Edge cases for LLMResponse."""

    def test_empty_content(self):
        response = LLMResponse(content="", model="", provider="")
        assert response.content == ""
        assert response.total_tokens == 0

    def test_large_token_counts(self):
        response = LLMResponse(
            content="test",
            model="gpt-4o",
            provider="openai",
            input_tokens=100000,
            output_tokens=50000,
            cost_usd=10.0,
        )
        # total_tokens is NOT auto-computed in the dataclass
        assert response.input_tokens == 100000
        assert response.output_tokens == 50000
        assert response.cost_usd == 10.0


class TestSchedulerGenerate:
    """Async tests for MultiModelScheduler.generate."""

    @pytest.mark.asyncio
    async def test_generate_success(self):
        from unittest.mock import AsyncMock

        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(config)

        mock_response = LLMResponse(
            content="hello", model="gpt-4o", provider="openai",
        )
        for provider in scheduler._providers.values():
            provider.generate = AsyncMock(return_value=mock_response)

        response = await scheduler.generate("test")
        assert response.content == "hello"
        assert scheduler._stats["openai/gpt-4o"].successful_calls == 1

    @pytest.mark.asyncio
    async def test_generate_with_messages_success(self):
        from unittest.mock import AsyncMock

        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(config)

        mock_response = LLMResponse(
            content="hello", model="gpt-4o", provider="openai",
        )
        for provider in scheduler._providers.values():
            provider.generate_with_messages = AsyncMock(return_value=mock_response)

        response = await scheduler.generate_with_messages(
            [{"role": "user", "content": "test"}]
        )
        assert response.content == "hello"

    @pytest.mark.asyncio
    async def test_generate_all_providers_fail(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(config)

        for provider in scheduler._providers.values():
            provider.generate = None  # Will cause AttributeError

        with pytest.raises(RuntimeError, match="All providers failed"):
            await scheduler.generate("test")

    @pytest.mark.asyncio
    async def test_generate_fallback_disabled(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
            fallback_enabled=False,
        )
        scheduler = MultiModelScheduler(config)

        for provider in scheduler._providers.values():
            provider.generate = None

        # With fallback disabled, the original exception (TypeError) is raised
        with pytest.raises(TypeError):
            await scheduler.generate("test")

    @pytest.mark.asyncio
    async def test_generate_with_messages_all_fail(self):
        config = SchedulerConfig(
            models=[
                ModelConfig(provider="openai", model="gpt-4o", api_key="key1"),
            ],
        )
        scheduler = MultiModelScheduler(config)

        for provider in scheduler._providers.values():
            provider.generate_with_messages = None

        with pytest.raises(RuntimeError, match="All providers failed"):
            await scheduler.generate_with_messages(
                [{"role": "user", "content": "test"}]
            )
