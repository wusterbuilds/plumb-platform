import uuid
from datetime import datetime, timezone

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import settings
from app.db.events import log_event, log_event_sync
from app.prompts.base import PromptDefinition
from app.prompts.registry import prompt_registry
from app.schemas.enums import EventType


class PromptOutputValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Prompt output validation failed: {errors}")


class PlumbLLMClient:
    """Claude API wrapper that routes all calls through the prompt registry
    and logs token usage on every call."""

    def __init__(self):
        self._async_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._sync_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def execute(
        self,
        prompt_name: str,
        deal_context: dict,
        task_data: dict,
        db: AsyncSession,
        deal_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> dict:
        prompt = prompt_registry.get(prompt_name)

        # Inject active skills for this prompt
        from app.services.skill_service import get_active_skills_for_prompt
        skills = await get_active_skills_for_prompt(db, prompt_name)
        if skills:
            deal_context = {**deal_context, "active_skills": skills}

        messages = prompt.build_input(deal_context, task_data)

        # Build system prompt with skill injection
        system = prompt.system_prompt
        if skills:
            skill_lines = []
            for s in skills:
                skill_lines.append(f"## Skill: {s['skill_name']}\n{s['instructions']}")
            system = system + "\n\n# Active Skills\n" + "\n\n".join(skill_lines)

        # Build API call kwargs
        kwargs = {
            "model": prompt.model,
            "system": system,
            "messages": messages,
            "max_tokens": prompt.max_output_tokens,
            "temperature": prompt.temperature,
        }

        # Add tool use for structured output if schema is defined
        if prompt.output_schema:
            kwargs["tools"] = [
                {
                    "name": f"{prompt.name}_output",
                    "description": f"Structured output for {prompt.name}",
                    "input_schema": prompt.output_schema,
                }
            ]
            kwargs["tool_choice"] = {"type": "tool", "name": f"{prompt.name}_output"}

        response = await self._async_client.messages.create(**kwargs)
        result = self._parse_response(response, prompt)

        # Validate output. On failure, retry ONCE with a correction message that
        # embeds the validation errors, then hard-fail. Covers two known failure
        # modes: (1) word-budget overruns in narrative prompts and (2) schema
        # wrapper violations in extraction prompts (e.g. missing top-level
        # 'fields' when the model produces a different shape or hits max_tokens).
        is_valid, errors = prompt.validate_output(result)
        if not is_valid:
            retry_messages = list(messages) + [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_retry",
                            "name": f"{prompt.name}_output",
                            "input": result,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_retry",
                            "content": (
                                "Output rejected. Fix these errors and resubmit:\n- "
                                + "\n- ".join(errors)
                                + "\n\nReturn output that strictly conforms to the tool's "
                                "input_schema. If a narrative field exceeded a word budget, "
                                "shorten it (cut adjectives, filler, redundant clauses). If a "
                                "required key was missing, add it — for extraction prompts the "
                                "top-level shape must be {\"fields\": {...}} with every field "
                                "as a nested object. If the previous response was truncated by "
                                "the token limit, drop the lowest-priority line items to fit."
                            ),
                            "is_error": True,
                        }
                    ],
                },
            ]
            retry_kwargs = {**kwargs, "messages": retry_messages}
            retry_response = await self._async_client.messages.create(**retry_kwargs)
            retry_result = self._parse_response(retry_response, prompt)
            is_valid, errors = prompt.validate_output(retry_result)
            if not is_valid:
                raise PromptOutputValidationError(errors)
            result = retry_result
            # Combine usage from both calls for cost logging.
            response.usage.input_tokens += retry_response.usage.input_tokens
            response.usage.output_tokens += retry_response.usage.output_tokens

        # Log token usage
        await self._log_usage(db, deal_id, actor_id, prompt, response)

        return result

    def call_llm(
        self,
        prompt_name: str,
        deal_context: dict,
        task_data: dict,
        db: Session | None = None,
        deal_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> dict:
        """Synchronous LLM call for Celery tasks. No async DB required."""
        prompt = prompt_registry.get(prompt_name)
        messages = prompt.build_input(deal_context, task_data)

        # Inject expert-feedback corrections relevant to this deal's archetype.
        # These are projected from `DraftRedline` records via the redline
        # service. The instruction is intentionally short and front-loaded with
        # the archetype qualifier so the model knows when each lesson applies.
        system = prompt.system_prompt
        past_corrections = deal_context.get("past_corrections") or []
        if past_corrections:
            lines = "\n".join(f"- {c}" for c in past_corrections[:10])
            system = (
                f"{system}\n\n# Past Expert Corrections to Apply\n"
                "The following lessons were captured from human reviewers on "
                "prior deals of similar archetype. Apply them when drafting "
                "this section if relevant; ignore lessons that don't apply.\n"
                f"{lines}"
            )

        kwargs = {
            "model": prompt.model,
            "system": system,
            "messages": messages,
            "max_tokens": prompt.max_output_tokens,
            "temperature": prompt.temperature,
        }

        if prompt.output_schema:
            kwargs["tools"] = [
                {
                    "name": f"{prompt.name}_output",
                    "description": f"Structured output for {prompt.name}",
                    "input_schema": prompt.output_schema,
                }
            ]
            kwargs["tool_choice"] = {"type": "tool", "name": f"{prompt.name}_output"}

        response = self._sync_client.messages.create(**kwargs)
        result = self._parse_response(response, prompt)

        is_valid, errors = prompt.validate_output(result)
        if not is_valid:
            raise PromptOutputValidationError(errors)

        # Log usage synchronously if db provided
        if db and deal_id:
            usage = response.usage
            input_cost = usage.input_tokens * self._get_input_price(prompt.model)
            output_cost = usage.output_tokens * self._get_output_price(prompt.model)
            log_event_sync(
                db=db,
                deal_id=deal_id,
                event_type=EventType.LLM_CALL.value,
                actor_id=actor_id,
                payload={
                    "prompt_name": prompt.name,
                    "prompt_version": prompt.version,
                    "model": prompt.model,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cost_usd": round(input_cost + output_cost, 6),
                },
            )

        return result

    def _parse_response(self, response, prompt: PromptDefinition) -> dict:
        """Extract structured data from the Claude response."""
        for block in response.content:
            if block.type == "tool_use":
                return block.input
        for block in response.content:
            if block.type == "text":
                return {"text": block.text}
        return {}

    async def _log_usage(
        self,
        db: AsyncSession,
        deal_id: uuid.UUID | None,
        actor_id: uuid.UUID | None,
        prompt: PromptDefinition,
        response,
    ) -> None:
        """Log token usage as an event for cost tracking."""
        usage = response.usage
        input_cost = usage.input_tokens * self._get_input_price(prompt.model)
        output_cost = usage.output_tokens * self._get_output_price(prompt.model)

        payload = {
            "prompt_name": prompt.name,
            "prompt_version": prompt.version,
            "model": prompt.model,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_usd": round(input_cost + output_cost, 6),
        }

        if deal_id:
            await log_event(
                db=db,
                deal_id=deal_id,
                event_type=EventType.LLM_CALL.value,
                actor_id=actor_id,
                payload=payload,
            )

    @staticmethod
    def _get_input_price(model: str) -> float:
        """Price per token (input). Updated as of April 2026."""
        prices = {
            "claude-opus-4-6": 15.0 / 1_000_000,
            "claude-sonnet-4-6": 3.0 / 1_000_000,
            "claude-haiku-4-5-20251001": 0.80 / 1_000_000,
        }
        return prices.get(model, 3.0 / 1_000_000)

    @staticmethod
    def _get_output_price(model: str) -> float:
        """Price per token (output). Updated as of April 2026."""
        prices = {
            "claude-opus-4-6": 75.0 / 1_000_000,
            "claude-sonnet-4-6": 15.0 / 1_000_000,
            "claude-haiku-4-5-20251001": 4.0 / 1_000_000,
        }
        return prices.get(model, 15.0 / 1_000_000)
