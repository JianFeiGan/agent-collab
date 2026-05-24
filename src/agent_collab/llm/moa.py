"""Mixture of Agents (MoA) engine for multi-model collaboration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_collab.llm import LLMResponse
    from agent_collab.llm.scheduler import MultiModelScheduler

logger = logging.getLogger(__name__)


@dataclass
class MoAConfig:
    """Configuration for Mixture of Agents."""

    reference_models: list[str]
    aggregator_model: str
    num_reference_rounds: int = 2
    num_references_per_round: int = 3
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class MoAResponse:
    """Response from MoA engine."""

    content: str
    reference_responses: list[LLMResponse] = field(default_factory=list)
    aggregator_response: LLMResponse | None = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_seconds: float = 0.0


class MoAEngine:
    """Mixture of Agents engine.

    Implements the MoA architecture:
    1. Reference models generate initial responses
    2. Aggregator model synthesizes the final response

    This approach leverages the strengths of multiple models
    to produce higher quality outputs.
    """

    def __init__(
        self,
        scheduler: MultiModelScheduler,
        config: MoAConfig,
    ) -> None:
        self.scheduler = scheduler
        self.config = config

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> MoAResponse:
        """Generate a response using MoA architecture.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            **kwargs: Additional parameters.

        Returns:
            MoAResponse with the synthesized content.
        """
        reference_responses: list[LLMResponse] = []
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0
        total_latency = 0.0

        # Phase 1: Generate reference responses
        for round_num in range(self.config.num_reference_rounds):
            logger.info(f"MoA reference round {round_num + 1}/{self.config.num_reference_rounds}")

            # Generate multiple reference responses in parallel
            import asyncio

            tasks = []
            for _i in range(self.config.num_references_per_round):
                ref_prompt = self._create_reference_prompt(prompt, reference_responses, round_num)
                tasks.append(
                    self.scheduler.generate(
                        prompt=ref_prompt,
                        system_prompt=system_prompt,
                        max_tokens=self.config.max_tokens,
                        temperature=self.config.temperature,
                    )
                )

            # Wait for all reference responses
            round_responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Process responses
            for resp in round_responses:
                if isinstance(resp, Exception):
                    logger.warning(f"Reference model failed: {resp}")
                    continue
                reference_responses.append(resp)
                total_input_tokens += resp.input_tokens
                total_output_tokens += resp.output_tokens
                total_cost += resp.cost_usd
                total_latency += resp.latency_seconds

        # Phase 2: Aggregate responses
        logger.info("MoA aggregation phase")
        aggregator_prompt = self._create_aggregator_prompt(prompt, reference_responses)

        aggregator_response = await self.scheduler.generate(
            prompt=aggregator_prompt,
            system_prompt=system_prompt,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )

        total_input_tokens += aggregator_response.input_tokens
        total_output_tokens += aggregator_response.output_tokens
        total_cost += aggregator_response.cost_usd
        total_latency += aggregator_response.latency_seconds

        return MoAResponse(
            content=aggregator_response.content,
            reference_responses=reference_responses,
            aggregator_response=aggregator_response,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_cost_usd=total_cost,
            total_latency_seconds=total_latency,
        )

    def _create_reference_prompt(
        self,
        original_prompt: str,
        previous_responses: list[LLMResponse],
        round_num: int,
    ) -> str:
        """Create a prompt for reference models.

        Args:
            original_prompt: The original user prompt.
            previous_responses: Responses from previous rounds.
            round_num: Current round number.

        Returns:
            The prompt for the reference model.
        """
        if round_num == 0:
            return original_prompt

        # Include previous responses for refinement
        previous_content = "\n\n".join(
            f"Reference {i + 1}:\n{resp.content}"
            for i, resp in enumerate(previous_responses[-self.config.num_references_per_round :])
        )

        return f"""Original prompt: {original_prompt}

Previous responses from other models:
{previous_content}

Please provide your refined response, considering the perspectives from other models.
Focus on improving accuracy, completeness, and clarity."""

    def _create_aggregator_prompt(
        self,
        original_prompt: str,
        reference_responses: list[LLMResponse],
    ) -> str:
        """Create a prompt for the aggregator model.

        Args:
            original_prompt: The original user prompt.
            reference_responses: All reference responses.

        Returns:
            The prompt for the aggregator model.
        """
        reference_content = "\n\n".join(
            f"Reference {i + 1}:\n{resp.content}" for i, resp in enumerate(reference_responses)
        )

        return f"""Original prompt: {original_prompt}

Multiple models have provided their responses:
{reference_content}

Please synthesize these responses into a single, high-quality response.
Consider the strengths of each response and combine them to create the best possible answer.
Focus on:
1. Accuracy and correctness
2. Completeness and thoroughness
3. Clarity and readability
4. Proper structure and organization

Provide your synthesized response:"""
