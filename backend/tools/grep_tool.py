"""
Grep tool — search file contents by pattern or keyword.
"""

import os
import re
from typing import Any
from tools.base import BaseTool


class GrepTool(BaseTool):
    name = "grep"
    description = "Search for a pattern or keyword in files within a directory. Returns matching lines with file paths and line numbers. Supports regex and recursive search."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Search pattern (regex supported).",
            },
            "path": {
                "type": "string",
                "description": "File or directory path to search in.",
            },
            "recursive": {
                "type": "boolean",
                "description": "Search subdirectories recursively. Default true.",
                "default": True,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum matches to return. Default 50.",
                "default": 50,
            },
            "include": {
                "type": "string",
                "description": "File extension filter, e.g. '*.py' or '*.js'. Optional.",
            },
        },
        "required": ["pattern", "path"],
    }

    async def execute(self, pattern: str, path: str, recursive: bool = True,
                      max_results: int = 50, include: str = "", **kwargs) -> dict[str, Any]:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            return {"success": False, "output": f"Path not found: {path}"}

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return {"success": False, "output": f"Invalid regex: {e}"}

        matches = []

        def search_file(filepath: str):
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        if len(matches) >= max_results:
                            return
                        if regex.search(line):
                            matches.append(f"{filepath}:{lineno}: {line.rstrip()}")
            except (PermissionError, IsADirectoryError):
                pass

        def matches_filter(name: str) -> bool:
            if not include:
                return True
            import fnmatch
            return fnmatch.fnmatch(name, include)

        if os.path.isfile(path):
            search_file(path)
        else:
            if recursive:
                for root, dirs, files in os.walk(path):
                    # Skip hidden dirs and common junk
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__', '.git')]
                    for name in files:
                        if matches_filter(name) and len(matches) < max_results:
                            search_file(os.path.join(root, name))
            else:
                for name in os.listdir(path):
                    full = os.path.join(path, name)
                    if os.path.isfile(full) and matches_filter(name):
                        search_file(full)

        if not matches:
            return {"success": True, "output": "No matches found."}

        header = f"Found {len(matches)} match(es)"
        if len(matches) >= max_results:
            header += f" (limited to {max_results})"
        return {"success": True, "output": header + ":\n" + "\n".join(matches)}
