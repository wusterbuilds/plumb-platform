from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PromptDefinition(ABC):
    """Base class for all registered prompts in the system.

    Every LLM interaction goes through a PromptDefinition subclass.
    No ad-hoc LLM calls.
    """

    name: str
    version: str
    model: str  # "claude-sonnet-4-6" | "claude-opus-4-6" | "claude-haiku-4-5-20251001"
    system_prompt: str
    max_output_tokens: int = 4096
    temperature: float = 0.0
    output_schema: dict = field(default_factory=dict)

    @abstractmethod
    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        """Build the messages list for the Claude API call.

        Returns a list of message dicts: [{"role": "user", "content": "..."}]
        """
        ...

    @abstractmethod
    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        """Validate that the LLM output matches the expected schema.

        Returns (is_valid, list_of_errors).
        """
        ...
