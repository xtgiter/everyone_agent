"""
Edit file tool — patch specific lines without rewriting the whole file.
"""

import os
from typing import Any
from tools.base import BaseTool


class EditFileTool(BaseTool):
    name = "edit_file"
    description = "Edit a file by replacing a specific string with new content. More precise than write_file — use this for targeted modifications instead of rewriting entire files."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file to edit.",
            },
            "old_string": {
                "type": "string",
                "description": "The exact string to find and replace. Must match file content exactly.",
            },
            "new_string": {
                "type": "string",
                "description": "The replacement string.",
            },
        },
        "required": ["path", "old_string", "new_string"],
    }

    async def execute(self, path: str, old_string: str, new_string: str, **kwargs) -> dict[str, Any]:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            return {"success": False, "output": f"File not found: {path}"}
        if not os.path.isfile(path):
            return {"success": False, "output": f"Not a file: {path}"}

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return {"success": False, "output": f"Read error: {e}"}

        count = content.count(old_string)
        if count == 0:
            # Show a snippet of the file to help debug
            preview = content[:500] + "..." if len(content) > 500 else content
            return {"success": False, "output": f"old_string not found in file. File preview:\n{preview}"}
        if count > 1:
            return {"success": False, "output": f"old_string found {count} times — must be unique. Add more context to disambiguate."}

        new_content = content.replace(old_string, new_string, 1)

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return {"success": True, "output": f"File edited: {path} (replaced 1 occurrence)"}
        except Exception as e:
            return {"success": False, "output": f"Write error: {e}"}
