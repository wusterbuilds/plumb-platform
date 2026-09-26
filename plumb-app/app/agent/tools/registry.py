"""Sprint 4: Tool registry — register, discover, execute tools."""

from app.agent.tools.base import PlumbTool, ToolPermission, ToolResult


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, PlumbTool] = {}

    def register(self, tool: PlumbTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> PlumbTool | None:
        return self._tools.get(name)

    def list_all(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "permission": t.permission.value,
            }
            for t in self._tools.values()
        ]

    def get_tools_for_agent(
        self,
        tool_names: list[str],
        include_human_gated: bool = False,
    ) -> list[PlumbTool]:
        tools = []
        for name in tool_names:
            tool = self._tools.get(name)
            if not tool:
                continue
            if tool.permission == ToolPermission.HUMAN_GATED and not include_human_gated:
                continue
            if tool.permission == ToolPermission.ADMIN_ONLY:
                continue
            tools.append(tool)
        return tools

    def to_claude_tools(self, tool_names: list[str]) -> list[dict]:
        """Convert a set of tools to Claude API tool format."""
        tools = self.get_tools_for_agent(tool_names)
        return [t.to_claude_tool() for t in tools]

    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{tool_name}' not found")
        return await tool.execute(**kwargs)


# Global singleton
tool_registry = ToolRegistry()
