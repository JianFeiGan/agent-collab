"""Multi-model scheduler with strategy-based selection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agent_collab.llm import (
    BaseLLMProvider,
    LLMConfig,
    LLMResponse,
    get_provider,
)

logger = logging.getLogger(__name__)


class SelectionStrategy(Enum):
    """Strategy for selecting which model to use."""

    ROUND_ROBIN = "round_robin"
    COST_OPTIMIZED = "cost_optimized"
    QUALITY_FIRST = "quality_first"
    LATENCY_OPTIMIZED = "latency_optimized"
    RANDOM = "random"


@dataclass
class ModelConfig:
    """Configuration for a model in the pool."""

    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    weight: float = 1.0
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    quality_score: float = 0.5
    avg_latency_ms: float = 0.0
    enabled: bool = True


@dataclass
class ModelStats:
    """Statistics for a model."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_seconds: float = 0.0
    avg_latency_seconds: float = 0.0

    def update(self, response: LLMResponse, success: bool) -> None:
        """Update stats with a new response."""
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens
        self.total_cost_usd += response.cost_usd
        self.total_latency_seconds += response.latency_seconds
        if self.total_calls > 0:
            self.avg_latency_seconds = self.total_latency_seconds / self.total_calls


@dataclass
class SchedulerConfig:
    """Configuration for the multi-model scheduler."""

    models: list[ModelConfig]
    strategy: SelectionStrategy = SelectionStrategy.QUALITY_FIRST
    fallback_enabled: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 60


class MultiModelScheduler:
    """Scheduler that routes requests to multiple LLM providers.

    Supports multiple selection strategies:
    - round_robin: Cycles through models sequentially
    - cost_optimized: Selects the cheapest model
    - quality_first: Selects the highest quality model
    - latency_optimized: Selects the fastest model
    - random: Randomly selects a model
    """

    def __init__(self, config: SchedulerConfig) -> None:
        self.config = config
        self._providers: dict[str, BaseLLMProvider] = {}
        self._stats: dict[str, ModelStats] = {}
        self._round_robin_index: int = 0
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize all providers from config."""
        for model_cfg in self.config.models:
            if not model_cfg.enabled:
                continue

            key = f"{model_cfg.provider}/{model_cfg.model}"
            llm_config = LLMConfig(
                provider=model_cfg.provider,
                model=model_cfg.model,
                api_key=model_cfg.api_key,
                base_url=model_cfg.base_url,
                max_tokens=model_cfg.max_tokens,
                temperature=model_cfg.temperature,
                timeout=self.config.timeout,
            )
            try:
                provider = get_provider(llm_config)
                self._providers[key] = provider
                self._stats[key] = ModelStats()
                logger.info(f"Initialized provider: {key}")
            except ValueError as e:
                logger.warning(f"Failed to initialize provider {key}: {e}")

    def _select_provider(self) -> tuple[str, BaseLLMProvider]:
        """Select a provider based on the configured strategy.

        Returns:
            Tuple of (provider_key, provider_instance).

        Raises:
            RuntimeError: If no providers are available.
        """
        if not self._providers:
            raise RuntimeError("No providers available")

        enabled_providers = [
            (key, provider)
            for key, provider in self._providers.items()
            if self.config.models[
                next(
                    i
                    for i, m in enumerate(self.config.models)
                    if f"{m.provider}/{m.model}" == key
                )
            ].enabled
        ]

        if not enabled_providers:
            raise RuntimeError("No enabled providers available")

        strategy = self.config.strategy

        if strategy == SelectionStrategy.ROUND_ROBIN:
            return self._select_round_robin(enabled_providers)
        elif strategy == SelectionStrategy.COST_OPTIMIZED:
            return self._select_cost_optimized(enabled_providers)
        elif strategy == SelectionStrategy.QUALITY_FIRST:
            return self._select_quality_first(enabled_providers)
        elif strategy == SelectionStrategy.LATENCY_OPTIMIZED:
            return self._select_latency_optimized(enabled_providers)
        elif strategy == SelectionStrategy.RANDOM:
            return self._select_random(enabled_providers)
        else:
            return enabled_providers[0]

    def _select_round_robin(
        self, providers: list[tuple[str, BaseLLMProvider]]
    ) -> tuple[str, BaseLLMProvider]:
        """Select provider using round-robin strategy."""
        idx = self._round_robin_index % len(providers)
        self._round_robin_index += 1
        return providers[idx]

    def _select_cost_optimized(
        self, providers: list[tuple[str, BaseLLMProvider]]
    ) -> tuple[str, BaseLLMProvider]:
        """Select the cheapest provider."""
        def get_cost(key: str) -> float:
            model_cfg = next(
                m for m in self.config.models if f"{m.provider}/{m.model}" == key
            )
            return model_cfg.cost_per_1k_input

        return min(providers, key=lambda x: get_cost(x[0]))

    def _select_quality_first(
        self, providers: list[tuple[str, BaseLLMProvider]]
    ) -> tuple[str, BaseLLMProvider]:
        """Select the highest quality provider."""
        def get_quality(key: str) -> float:
            model_cfg = next(
                m for m in self.config.models if f"{m.provider}/{m.model}" == key
            )
            return model_cfg.quality_score

        return max(providers, key=lambda x: get_quality(x[0]))

    def _select_latency_optimized(
        self, providers: list[tuple[str, BaseLLMProvider]]
    ) -> tuple[str, BaseLLMProvider]:
        """Select the fastest provider."""
        def get_latency(key: str) -> float:
            stats = self._stats.get(key)
            if stats and stats.total_calls > 0:
                return stats.avg_latency_seconds
            model_cfg = next(
                m for m in self.config.models if f"{m.provider}/{m.model}" == key
            )
            return model_cfg.avg_latency_ms / 1000.0

        return min(providers, key=lambda x: get_latency(x[0]))

    def _select_random(
        self, providers: list[tuple[str, BaseLLMProvider]]
    ) -> tuple[str, BaseLLMProvider]:
        """Randomly select a provider."""
        import random
        return random.choice(providers)

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response using the selected provider.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            **kwargs: Additional parameters.

        Returns:
            LLMResponse with the generated content.

        Raises:
            RuntimeError: If all providers fail.
        """
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries):
            try:
                key, provider = self._select_provider()
                logger.debug(f"Selected provider: {key} (attempt {attempt + 1})")

                response = await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    **kwargs,
                )

                # Update stats
                self._stats[key].update(response, success=True)
                return response

            except Exception as e:
                last_error = e
                logger.warning(f"Provider {key} failed: {e}")
                if self._stats.get(key):
                    self._stats[key].update(
                        LLMResponse(
                            content="",
                            model="",
                            provider=key,
                        ),
                        success=False,
                    )

                if not self.config.fallback_enabled:
                    raise

        raise RuntimeError(
            f"All providers failed after {self.config.max_retries} attempts: {last_error}"
        )

    async def generate_with_messages(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response using message history.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            **kwargs: Additional parameters.

        Returns:
            LLMResponse with the generated content.

        Raises:
            RuntimeError: If all providers fail.
        """
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries):
            try:
                key, provider = self._select_provider()
                logger.debug(f"Selected provider: {key} (attempt {attempt + 1})")

                response = await provider.generate_with_messages(
                    messages=messages,
                    **kwargs,
                )

                # Update stats
                self._stats[key].update(response, success=True)
                return response

            except Exception as e:
                last_error = e
                logger.warning(f"Provider {key} failed: {e}")
                if self._stats.get(key):
                    self._stats[key].update(
                        LLMResponse(
                            content="",
                            model="",
                            provider=key,
                        ),
                        success=False,
                    )

                if not self.config.fallback_enabled:
                    raise

        raise RuntimeError(
            f"All providers failed after {self.config.max_retries} attempts: {last_error}"
        )

    def get_stats(self) -> dict[str, ModelStats]:
        """Get statistics for all providers."""
        return dict(self._stats)

    def get_total_cost(self) -> float:
        """Get total cost across all providers."""
        return sum(stats.total_cost_usd for stats in self._stats.values())

    def get_total_tokens(self) -> tuple[int, int]:
        """Get total input and output tokens across all providers."""
        input_tokens = sum(stats.total_input_tokens for stats in self._stats.values())
        output_tokens = sum(stats.total_output_tokens for stats in self._stats.values())
        return input_tokens, output_tokens

    def reset_stats(self) -> None:
        """Reset statistics for all providers."""
        for stats in self._stats.values():
            stats.total_calls = 0
            stats.successful_calls = 0
            stats.failed_calls = 0
            stats.total_input_tokens = 0
            stats.total_output_tokens = 0
            stats.total_cost_usd = 0.0
            stats.total_latency_seconds = 0.0
            stats.avg_latency_seconds = 0.0
