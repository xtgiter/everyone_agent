"""
Memory tools — allow the Agent to read/write its own long-term memory.

Memory architecture:
- Session memory (per-session): work notes, project context, task progress
- User profile (global): user preferences, shared across all sessions
- SOUL.md (global): read-only personality & rules, user-maintained
"""

from tools.base import BaseTool
from services.memory_service import (
    read_session_memory,
    write_session_memory,
    append_session_memory,
    read_user_profile,
    write_user_profile,
    append_user_profile,
    get_memory_stats,
)


class ReadMemoryTool(BaseTool):
    name = "read_memory"
    description = "Read the Agent's long-term memory. Use target='memory' for this session's memory (work notes, project context), target='user' for USER.md (global user preferences), or target='stats' for usage statistics."

    parameters = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "enum": ["memory", "user", "stats"],
                "description": "Which memory to read: 'memory' for session memory, 'user' for global user profile, 'stats' for usage statistics",
            },
        },
        "required": ["target"],
    }

    async def execute(self, **kwargs) -> dict:
        target = kwargs.get("target", "memory")
        session_id = kwargs.get("_session_id", "")
        if target == "memory":
            content = read_session_memory(session_id)
            return {"success": True, "output": content or "(Session memory is empty)"}
        elif target == "user":
            content = read_user_profile()
            return {"success": True, "output": content or "(USER.md is empty)"}
        elif target == "stats":
            stats = get_memory_stats(session_id)
            return {"success": True, "output": str(stats)}
        return {"success": False, "output": f"Unknown target: {target}"}


class UpdateMemoryTool(BaseTool):
    name = "update_memory"
    description = "Update this session's memory. Use mode='replace' to rewrite entirely (for cleanup/compression), or mode='append' to add new entries. Store work notes, environment facts, project conventions, task progress here. Each session has its own independent memory. Max ~2200 chars."

    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The content to write or append to session memory",
            },
            "mode": {
                "type": "string",
                "enum": ["replace", "append"],
                "description": "Write mode: 'replace' overwrites entirely, 'append' adds to the end",
                "default": "append",
            },
        },
        "required": ["content"],
    }

    async def execute(self, **kwargs) -> dict:
        content = kwargs.get("content", "")
        mode = kwargs.get("mode", "append")
        session_id = kwargs.get("_session_id", "")
        if not content.strip():
            return {"success": False, "output": "Content cannot be empty"}
        if mode == "replace":
            return write_session_memory(session_id, content)
        return append_session_memory(session_id, content)


class UpdateUserProfileTool(BaseTool):
    name = "update_user_profile"
    description = "Update the global USER.md file with user preferences, communication style, and work habits. This is shared across ALL sessions. Use mode='replace' to rewrite entirely, or mode='append' to add. Only store stable, long-term user preferences here. Max ~1375 chars."

    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The content to write or append to USER.md",
            },
            "mode": {
                "type": "string",
                "enum": ["replace", "append"],
                "description": "Write mode: 'replace' overwrites entire file, 'append' adds to the end",
                "default": "append",
            },
        },
        "required": ["content"],
    }

    async def execute(self, **kwargs) -> dict:
        content = kwargs.get("content", "")
        mode = kwargs.get("mode", "append")
        if not content.strip():
            return {"success": False, "output": "Content cannot be empty"}
        if mode == "replace":
            return write_user_profile(content)
        return append_user_profile(content)
