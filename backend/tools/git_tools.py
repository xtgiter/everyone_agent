"""
Git tools — status, diff, commit, log for version control.
"""

import asyncio
import os
from typing import Any
from tools.base import BaseTool


async def _run_git(args: str, cwd: str | None = None) -> tuple[bool, str]:
    """Run a git command and return (success, output)."""
    proc = await asyncio.create_subprocess_shell(
        f"git {args}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
    except asyncio.TimeoutError:
        proc.kill()
        return False, "Git command timed out."

    out = stdout.decode("utf-8", errors="replace").strip()
    err = stderr.decode("utf-8", errors="replace").strip()
    output = out if out else err
    if len(output) > 10_000:
        output = output[:10_000] + "\n... (truncated)"
    return proc.returncode == 0, output


class GitStatusTool(BaseTool):
    name = "git_status"
    description = "Show the working tree status of a git repository. Returns modified, staged, and untracked files."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the git repository. Default: current directory.",
                "default": ".",
            },
        },
        "required": [],
    }

    async def execute(self, path: str = ".", **kwargs) -> dict[str, Any]:
        path = os.path.abspath(path)
        ok, output = await _run_git("status --short", cwd=path)
        if not ok:
            return {"success": False, "output": output}
        return {"success": True, "output": output if output else "(clean working tree)"}


class GitDiffTool(BaseTool):
    name = "git_diff"
    description = "Show changes in the working tree or between commits. Use to review what has been modified."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the git repository.",
                "default": ".",
            },
            "target": {
                "type": "string",
                "description": "Diff target: a file path, 'staged' for staged changes, or a commit ref. Default: all unstaged changes.",
                "default": "",
            },
        },
        "required": [],
    }

    async def execute(self, path: str = ".", target: str = "", **kwargs) -> dict[str, Any]:
        path = os.path.abspath(path)
        if target == "staged":
            cmd = "diff --cached"
        elif target:
            cmd = f"diff {target}"
        else:
            cmd = "diff"
        ok, output = await _run_git(cmd, cwd=path)
        if not ok:
            return {"success": False, "output": output}
        return {"success": True, "output": output if output else "(no differences)"}


class GitCommitTool(BaseTool):
    name = "git_commit"
    description = "Stage and commit changes. Can stage all changes or specific files before committing."
    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Commit message.",
            },
            "path": {
                "type": "string",
                "description": "Path to the git repository.",
                "default": ".",
            },
            "files": {
                "type": "string",
                "description": "Files to stage, space-separated. Use '.' for all. Default: '.' (stage all).",
                "default": ".",
            },
        },
        "required": ["message"],
    }

    async def execute(self, message: str, path: str = ".", files: str = ".", **kwargs) -> dict[str, Any]:
        path = os.path.abspath(path)
        # Stage
        ok, output = await _run_git(f"add {files}", cwd=path)
        if not ok:
            return {"success": False, "output": f"git add failed: {output}"}
        # Commit
        ok, output = await _run_git(f'commit -m "{message}"', cwd=path)
        if not ok:
            return {"success": False, "output": f"git commit failed: {output}"}
        return {"success": True, "output": output}


class GitLogTool(BaseTool):
    name = "git_log"
    description = "Show recent commit history."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the git repository.",
                "default": ".",
            },
            "count": {
                "type": "integer",
                "description": "Number of commits to show. Default 10.",
                "default": 10,
            },
        },
        "required": [],
    }

    async def execute(self, path: str = ".", count: int = 10, **kwargs) -> dict[str, Any]:
        path = os.path.abspath(path)
        ok, output = await _run_git(f"log --oneline -n {count}", cwd=path)
        if not ok:
            return {"success": False, "output": output}
        return {"success": True, "output": output if output else "(no commits)"}
