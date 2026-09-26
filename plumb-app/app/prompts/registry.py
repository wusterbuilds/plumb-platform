from app.prompts.base import PromptDefinition


class PromptRegistry:
    """Central registry for all prompt definitions. Singleton."""

    def __init__(self):
        self._prompts: dict[str, PromptDefinition] = {}

    def register(self, prompt: PromptDefinition) -> None:
        self._prompts[prompt.name] = prompt

    def get(self, name: str) -> PromptDefinition:
        if name not in self._prompts:
            raise KeyError(f"Prompt '{name}' is not registered")
        return self._prompts[name]

    def list_all(self) -> dict[str, str]:
        """Returns {name: version} for all registered prompts."""
        return {name: p.version for name, p in self._prompts.items()}


# Global registry instance
prompt_registry = PromptRegistry()
