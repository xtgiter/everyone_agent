"""
Read URL tool — fetch and extract text content from a web page or API endpoint.
"""

import re
from typing import Any
import httpx
from tools.base import BaseTool


class ReadUrlTool(BaseTool):
    name = "read_url"
    description = "Fetch content from a URL. For HTML pages, extracts readable text. For JSON APIs, returns the raw JSON. Useful for reading documentation, articles, or API responses."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch.",
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum characters to return. Default 8000.",
                "default": 8000,
            },
        },
        "required": ["url"],
    }

    async def execute(self, url: str, max_length: int = 8000, **kwargs) -> dict[str, Any]:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return {"success": False, "output": f"HTTP {e.response.status_code}: {url}"}
        except Exception as e:
            return {"success": False, "output": f"Request failed: {str(e)}"}

        content_type = resp.headers.get("content-type", "")

        # JSON response — return raw
        if "json" in content_type:
            text = resp.text[:max_length]
            return {"success": True, "output": text}

        # HTML — extract readable text
        if "html" in content_type:
            text = self._extract_text(resp.text)
        else:
            text = resp.text

        if len(text) > max_length:
            text = text[:max_length] + "\n... (truncated)"

        return {"success": True, "output": text if text.strip() else "(Empty page)"}

    @staticmethod
    def _extract_text(html: str) -> str:
        """Extract readable text from HTML, removing scripts, styles, and tags."""
        # Remove script and style blocks
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Convert block elements to newlines
        html = re.sub(r'<(br|p|div|h[1-6]|li|tr)[^>]*>', '\n', html, flags=re.IGNORECASE)
        # Remove all remaining tags
        text = re.sub(r'<[^>]+>', '', html)
        # Decode entities
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#x27;', "'").replace('&nbsp;', ' ')
        # Collapse whitespace
        lines = [line.strip() for line in text.split('\n')]
        lines = [l for l in lines if l]
        return '\n'.join(lines)
