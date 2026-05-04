import os
from typing import Any
from tools.base import BaseTool


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read the contents of a file at the given path. Use this to inspect files on the local system."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file to read.",
            }
        },
        "required": ["path"],
    }

    async def execute(self, path: str, **kwargs) -> dict[str, Any]:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            return {"success": False, "output": f"File not found: {path}"}
        if not os.path.isfile(path):
            return {"success": False, "output": f"Not a file: {path}"}
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(100_000)  # limit to 100KB
            return {"success": True, "output": content}
        except Exception as e:
            return {"success": False, "output": str(e)}


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write content to a file. Creates the file and parent directories if they don't exist."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file to write.",
            },
            "content": {
                "type": "string",
                "description": "The content to write into the file.",
            },
        },
        "required": ["path", "content"],
    }

    async def execute(self, path: str, content: str, **kwargs) -> dict[str, Any]:
        path = os.path.abspath(path)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "output": f"File written: {path}"}
        except Exception as e:
            return {"success": False, "output": str(e)}


class ListDirectoryTool(BaseTool):
    name = "list_directory"
    description = "List files and subdirectories in a directory. Returns names, types, and sizes."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the directory. Defaults to current directory.",
                "default": ".",
            }
        },
        "required": [],
    }

    async def execute(self, path: str = ".", **kwargs) -> dict[str, Any]:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            return {"success": False, "output": f"Path not found: {path}"}
        if not os.path.isdir(path):
            return {"success": False, "output": f"Not a directory: {path}"}
        try:
            entries = []
            for name in sorted(os.listdir(path)):
                full = os.path.join(path, name)
                if os.path.isdir(full):
                    entries.append(f"[DIR]  {name}")
                else:
                    size = os.path.getsize(full)
                    entries.append(f"[FILE] {name}  ({size} bytes)")
            result = f"Directory: {path}\n" + "\n".join(entries) if entries else f"Empty directory: {path}"
            return {"success": True, "output": result}
        except Exception as e:
            return {"success": False, "output": str(e)}
