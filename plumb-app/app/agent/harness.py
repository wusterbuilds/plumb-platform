"""Sprint 4: PlumbAgent base class — agent loop with tool use and reasoning trace."""

import uuid
from datetime import datetime, timezone
from typing import Any

import anthropic

from app.agent.progress import NULL_EMITTER, ProgressEmitter
from app.agent.tools.base import PlumbTool, ToolContext, ToolPermission, ToolResult
from app.agent.tools.registry import tool_registry
from app.config import settings
from app.models.agent import AgentRun
from app.prompts.client import PlumbLLMClient


class AgentResult:
    def __init__(
        self,
        success: bool = True,
        data: Any = None,
        reasoning_trace: list | None = None,
        error: str | None = None,
        iterations: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ):
        self.success = success
        self.data = data
        self.reasoning_trace = reasoning_trace or []
        self.error = error
        self.iterations = iterations
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class PlumbAgent:
    """Base class for all Plumb agents. Built directly on Anthropic's tool use API."""

    name: str = "base_agent"
    system_prompt: str = ""
    tool_names: list[str] = []
    model: str = "claude-sonnet-4-6"
    max_iterations: int = 10
    use_extended_thinking: bool = False

    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._llm_client = PlumbLLMClient()
        self._last_trace = []

    async def run(
        self,
        goal: str,
        deal_context: dict,
        db=None,
        deal_id: uuid.UUID | None = None,
        progress: ProgressEmitter | None = None,
    ) -> AgentResult:
        """Execute the agent loop."""
        p = progress or NULL_EMITTER
        reasoning_trace = []
        self._last_trace = reasoning_trace
        total_input_tokens = 0
        total_output_tokens = 0
        iterations = 0

        # Build system prompt with deal context
        system = self._build_system_prompt(deal_context)

        # Get tools for this agent
        tools = [
            tool_registry.get(name).to_claude_tool()
            for name in self.tool_names
            if tool_registry.get(name)
        ]

        messages = [{"role": "user", "content": goal}]

        if self.use_extended_thinking:
            await p.emit("agent_thinking", agent=self.name, model=self.model)
            # Single-pass with extended thinking
            kwargs = {
                "model": self.model,
                "max_tokens": 16000,
                "temperature": 1,  # Required for extended thinking
                "thinking": {"type": "adaptive"},
                "system": system,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools

            response = await self._client.messages.create(**kwargs)
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            result_data = self._extract_result(response)
            thinking_text = self._extract_thinking(response)
            if thinking_text:
                reasoning_trace.append({"type": "thinking", "content": thinking_text})

            return AgentResult(
                success=True,
                data=result_data,
                reasoning_trace=reasoning_trace,
                iterations=1,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )

        # Tool-use loop
        while iterations < self.max_iterations:
            iterations += 1
            await p.emit(
                "agent_iteration", agent=self.name,
                iteration=iterations, max_iterations=self.max_iterations,
            )

            kwargs = {
                "model": self.model,
                "max_tokens": 16384,
                "temperature": 0,
                "system": system,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools

            response = await self._client.messages.create(**kwargs)
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            # Check if agent is done (no tool calls)
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            if text_blocks:
                for tb in text_blocks:
                    reasoning_trace.append({"type": "text", "content": tb.text})

            if not tool_uses:
                result_data = self._extract_result(response)
                return AgentResult(
                    success=True,
                    data=result_data,
                    reasoning_trace=reasoning_trace,
                    iterations=iterations,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                )

            # Process tool calls
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tool_use in tool_uses:
                reasoning_trace.append({
                    "type": "tool_call",
                    "tool": tool_use.name,
                    "input": tool_use.input,
                })
                await p.emit(
                    "tool_call", agent=self.name,
                    tool=tool_use.name, iteration=iterations,
                )

                tool = tool_registry.get(tool_use.name)
                if tool and tool.permission != ToolPermission.ADMIN_ONLY:
                    ctx = ToolContext(
                        db=db,
                        deal_id=deal_id,
                        llm_client=self._llm_client,
                    )
                    try:
                        result = await tool.execute(_ctx=ctx, **tool_use.input)
                        result = tool.truncate_output(result)
                    except Exception as exc:
                        result = ToolResult(
                            success=False,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    reasoning_trace.append({
                        "type": "tool_result",
                        "tool": tool_use.name,
                        "success": result.success,
                        "tokens_used": result.tokens_used,
                    })
                    await p.emit(
                        "tool_result", agent=self.name,
                        tool=tool_use.name, success=result.success,
                        tokens_used=result.tokens_used, iteration=iterations,
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": str(result.data) if result.success else f"Error: {result.error}",
                    })
                else:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": f"Tool '{tool_use.name}' not available or requires admin permission.",
                    })

            messages.append({"role": "user", "content": tool_results})

        return AgentResult(
            success=False,
            error=f"Max iterations ({self.max_iterations}) reached",
            reasoning_trace=reasoning_trace,
            iterations=iterations,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )

    def _build_system_prompt(self, deal_context: dict) -> str:
        parts = [self.system_prompt]

        l1 = deal_context.get("l1", {})
        if l1:
            parts.append(f"\n## Deal Summary\n{_format_dict(l1)}")

        l2 = deal_context.get("l2", {})
        docs = l2.get("documents", [])
        if docs:
            doc_lines = []
            for d in docs:
                doc_lines.append(
                    f"- id: {d['id']} | filename: {d['filename']} | "
                    f"type: {d.get('document_type') or 'unclassified'} | "
                    f"mime: {d.get('mime_type', '')} | pages: {d.get('page_count', '?')} | "
                    f"status: {d.get('status', 'unknown')}"
                )
            parts.append(f"\n## Deal Documents\n" + "\n".join(doc_lines))

        l3 = deal_context.get("l3", {})
        if l3.get("developer_profile"):
            parts.append(f"\n## Developer Profile\n{_format_dict(l3['developer_profile'])}")
        if l3.get("correction_patterns"):
            parts.append(f"\n## Known Correction Patterns\n{l3['correction_patterns']}")
        if l3.get("episodes"):
            ep_text = "\n".join(f"- {e['lesson']}" for e in l3["episodes"])
            parts.append(f"\n## Relevant Past Lessons\n{ep_text}")

        if l3.get("knowledge"):
            k_text = "\n".join(
                f"- **{k.get('title', '')}**: {k.get('content', '')[:200]}"
                for k in l3["knowledge"]
            )
            parts.append(f"\n## Knowledge Base\n{k_text}")

        skills = l3.get("skills", [])
        if skills:
            skill_parts = []
            for s in skills:
                skill_parts.append(f"### Skill: {s['skill_name']}\n{s['instructions']}")
                if s.get("reference_examples"):
                    for ex in s["reference_examples"][:2]:
                        skill_parts.append(f"  Example: {ex}")
            parts.append(f"\n## Active Skills\n" + "\n".join(skill_parts))

        return "\n".join(parts)

    def _extract_result(self, response) -> dict:
        for block in response.content:
            if block.type == "tool_use":
                return block.input
            if block.type == "text":
                return {"text": block.text}
        return {}

    def _extract_thinking(self, response) -> str | None:
        for block in response.content:
            if block.type == "thinking":
                return block.thinking
        return None


def _format_dict(d: dict, indent: int = 0) -> str:
    lines = []
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{prefix}{k}:")
            lines.append(_format_dict(v, indent + 1))
        elif isinstance(v, list):
            lines.append(f"{prefix}{k}: {v}")
        else:
            lines.append(f"{prefix}{k}: {v}")
    return "\n".join(lines)
