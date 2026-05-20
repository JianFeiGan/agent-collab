"""Tests for LLM providers and multi-model scheduler."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_collab.llm import (
    AnthropicProvider,
    GoogleProvider,
    LLMConfig,
    LLMResponse,
    OpenAIProvider,
    get_provider,
)
from agent_collab.llm.scheduler import (
    ModelConfig,
    ModelStats,
    MultiModelScheduler,
    SchedulerConfig,
    SelectionStrategy,
)
from agent_collab.llm.moa import MoAConfig, MoAEngine


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
