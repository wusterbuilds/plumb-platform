"""SSE progress emitter for agent pipeline observability.

Emits structured events as the pipeline runs so clients can stream real-time progress
instead of waiting for the full pipeline to complete.
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProgressEvent:
    """A single progress event emitted during pipeline execution."""
    type: str
    agent: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        payload = {
            "type": self.type,
            "agent": self.agent,
            "timestamp": self.timestamp,
            **self.data,
        }
        return f"data: {json.dumps(payload)}\n\n"


class ProgressEmitter:
    """Async queue-backed progress emitter for SSE streaming.

    Usage in orchestrator:
        emitter = ProgressEmitter()
        await emitter.emit("agent_starting", agent="research_agent", data={"goal": "..."})

    Usage in SSE endpoint:
        async for event in emitter:
            yield event.to_sse()
    """

    def __init__(self):
        self._queue: asyncio.Queue[ProgressEvent | None] = asyncio.Queue()
        self._closed = False

    async def emit(
        self,
        event_type: str,
        agent: str | None = None,
        **data: Any,
    ) -> None:
        if not self._closed:
            event = ProgressEvent(type=event_type, agent=agent, data=data)
            await self._queue.put(event)

    async def close(self) -> None:
        """Send sentinel to signal stream end."""
        self._closed = True
        await self._queue.put(None)

    def __aiter__(self):
        return self

    async def __anext__(self) -> ProgressEvent:
        event = await self._queue.get()
        if event is None:
            raise StopAsyncIteration
        return event


# Null emitter for non-streaming calls (no-op, zero overhead)
class NullEmitter(ProgressEmitter):
    async def emit(self, event_type: str, agent: str | None = None, **data: Any) -> None:
        pass

    async def close(self) -> None:
        pass


NULL_EMITTER = NullEmitter()
