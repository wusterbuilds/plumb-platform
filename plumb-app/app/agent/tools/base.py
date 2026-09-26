"""Sprint 4: PlumbTool base class — schema-validated tools with permission gates."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.prompts.client import PlumbLLMClient


class ToolPermission(str, Enum):
    AUTO = "auto"
    HUMAN_GATED = "human_gated"
    ADMIN_ONLY = "admin_only"


class CacheConfig(BaseModel):
    stable_prefix: str | None = None
    cache_ttl_seconds: int = 300


class ToolResult(BaseModel):
    success: bool = True
    data: Any = None
    error: str | None = None
    tokens_used: int = 0


class ToolError(BaseModel):
    error_code: str
    message: str
    retryable: bool = False


@dataclass
class ToolContext:
    """Runtime context passed to every tool execution — db, deal_id, LLM client."""

    db: AsyncSession
    deal_id: uuid.UUID | None = None
    llm_client: PlumbLLMClient | None = None
    extra: dict = field(default_factory=dict)


class PlumbTool(ABC):
    name: str
    description: str
    permission: ToolPermission = ToolPermission.AUTO
    cache_config: CacheConfig = CacheConfig()
    timeout_ms: int = 30_000

    @abstractmethod
    async def execute(self, _ctx: ToolContext | None = None, **kwargs) -> ToolResult:
        ...

    def to_claude_tool(self) -> dict:
        """Convert to Claude API tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.get_input_schema(),
        }

    def get_input_schema(self) -> dict:
        """Override to define input schema for Claude tool use."""
        return {"type": "object", "properties": {}}

    def truncate_output(self, result: ToolResult, max_tokens: int = 4000) -> ToolResult:
        """Truncate output to stay within token budget."""
        if result.data and isinstance(result.data, str) and len(result.data) > max_tokens * 4:
            result.data = result.data[:max_tokens * 4] + "\n... [truncated]"
        return result
