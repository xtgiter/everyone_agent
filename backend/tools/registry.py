from typing import Any
from tools.base import BaseTool


class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_all_definitions(self, only: list[str] | None = None) -> list[dict]:
        """Return tool definitions for the LLM API.
        If `only` is provided, return only the named tools."""
        tools = self._tools.values() if only is None else [
            self._tools[n] for n in only if n in self._tools
        ]
        return [tool.get_function_definition() for tool in tools]

    def get_tools_description(self, only: list[str] | None = None) -> str:
        """Build a human-readable tool list (for sub-agent system prompts)."""
        tools = self._tools.values() if only is None else [
            self._tools[n] for n in only if n in self._tools
        ]
        lines = []
        for tool in tools:
            params = ", ".join(f"`{k}`" for k in tool.parameters.get("properties", {}).keys())
            lines.append(f"- **{tool.name}**: {tool.description} (params: {params})")
        return "\n".join(lines) if lines else "No tools available."

    async def call(self, name: str, arguments: dict[str, Any],
                   context: dict | None = None,
                   allowed: list[str] | None = None) -> dict[str, Any]:
        """Execute a tool by name. If `allowed` is set, reject tools not in the list."""
        if allowed is not None and name not in allowed:
            return {"success": False, "output": f"Tool '{name}' is not available for this agent."}
        tool = self._tools.get(name)
        if not tool:
            return {"success": False, "output": f"Tool '{name}' not found."}
        try:
            # Inject context (e.g. _session_id) as hidden kwargs
            if context:
                arguments = {**arguments, **{f"_{k}": v for k, v in context.items()}}
            return await tool.execute(**arguments)
        except Exception as e:
            return {"success": False, "output": f"Tool error: {str(e)}"}


tool_registry = ToolRegistry()
