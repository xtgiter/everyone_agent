from typing import Any

from tavily import TavilyClient
from tools.base import BaseTool
from config import settings


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web using Tavily and return relevant results. Use this to find up-to-date information from the internet."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return. Default 5.",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    async def execute(self, query: str, max_results: int = 5, **kwargs) -> dict[str, Any]:
        api_key = settings.TAVILY_API_KEY
        if not api_key:
            return {"success": False, "output": "TAVILY_API_KEY not configured in .env"}
        try:
            client = TavilyClient(api_key=api_key)
            response = client.search(query=query, max_results=max_results, search_depth="basic")
            results = response.get("results", [])
            if not results:
                return {"success": True, "output": "No search results found."}

            formatted = []
            for i, r in enumerate(results, 1):
                title = r.get("title", "")
                url = r.get("url", "")
                content = r.get("content", "")[:200]
                formatted.append(f"[{i}] {title}\n    URL: {url}\n    {content}")
            return {"success": True, "output": "\n\n".join(formatted)}
        except Exception as e:
            return {"success": False, "output": f"Search failed: {str(e)}"}
