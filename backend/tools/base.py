from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """All tools must inherit from this base class."""

    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    async def execute(self, **kwargs) -> dict[str, Any]:
        """Execute the tool and return a result dict with 'success' and 'output' keys."""
        ...

    def get_function_definition(self) -> dict:
        """Return OpenAI-compatible function definition for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
