import pytest

from app.prompts.base import PromptDefinition
from app.prompts.registry import PromptRegistry


class ConcretePrompt(PromptDefinition):
    """Concrete implementation for testing."""

    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        return [{"role": "user", "content": "test"}]

    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        return True, []


class TestPromptRegistry:
    def test_register_and_get(self):
        registry = PromptRegistry()
        prompt = ConcretePrompt(
            name="test_prompt",
            version="1.0",
            model="claude-sonnet-4-6",
            system_prompt="You are a test assistant.",
        )
        registry.register(prompt)
        retrieved = registry.get("test_prompt")
        assert retrieved.name == "test_prompt"
        assert retrieved.version == "1.0"

    def test_get_nonexistent_raises(self):
        registry = PromptRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.get("nonexistent")

    def test_list_all(self):
        registry = PromptRegistry()
        p1 = ConcretePrompt(
            name="prompt_a", version="1.0", model="claude-sonnet-4-6", system_prompt="A"
        )
        p2 = ConcretePrompt(
            name="prompt_b", version="2.1", model="claude-opus-4-6", system_prompt="B"
        )
        registry.register(p1)
        registry.register(p2)
        result = registry.list_all()
        assert result == {"prompt_a": "1.0", "prompt_b": "2.1"}

    def test_prompt_definition_is_abstract(self):
        with pytest.raises(TypeError):
            PromptDefinition(
                name="x", version="1.0", model="claude-sonnet-4-6", system_prompt="x"
            )

    def test_global_registry_is_singleton(self):
        from app.prompts.registry import prompt_registry as reg1
        from app.prompts.registry import prompt_registry as reg2
        assert reg1 is reg2

    def test_duplicate_registration_overwrites(self):
        registry = PromptRegistry()
        p1 = ConcretePrompt(
            name="dup", version="1.0", model="claude-sonnet-4-6", system_prompt="A"
        )
        p2 = ConcretePrompt(
            name="dup", version="2.0", model="claude-opus-4-6", system_prompt="B"
        )
        registry.register(p1)
        registry.register(p2)
        assert registry.get("dup").version == "2.0"
