"""
Memory service — per-session + global memory management.

Architecture:
- SOUL.md:   Global, user-maintained, Agent read-only (personality & rules)
- USER.md:   Global, Agent-curated (user preferences, shared across sessions)
- Session memory: Per-session, Agent-curated (work notes specific to each conversation)
                   Stored in session JSON under the "memory" field.
"""

from pathlib import Path
from services import session_service

MEMORY_DIR = Path(__file__).resolve().parent.parent / "data" / "memories"
SOUL_FILE = MEMORY_DIR / "SOUL.md"
USER_FILE = MEMORY_DIR / "USER.md"

SESSION_MEMORY_CHAR_LIMIT = 2200
USER_CHAR_LIMIT = 1375


def _ensure_dir():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


# ── SOUL.md (global, read-only for Agent) ──

def read_soul() -> str:
    _ensure_dir()
    if SOUL_FILE.exists():
        return SOUL_FILE.read_text(encoding="utf-8")
    return ""


# ── USER.md (global, Agent-curated) ──

def read_user_profile() -> str:
    _ensure_dir()
    if USER_FILE.exists():
        return USER_FILE.read_text(encoding="utf-8")
    return ""


def write_user_profile(content: str) -> dict:
    _ensure_dir()
    if len(content) > USER_CHAR_LIMIT:
        return {
            "success": False,
            "output": f"Content exceeds {USER_CHAR_LIMIT} char limit ({len(content)} chars). Please compress.",
        }
    USER_FILE.write_text(content, encoding="utf-8")
    return {"success": True, "output": f"USER.md updated ({len(content)} / {USER_CHAR_LIMIT} chars)"}


def append_user_profile(content: str) -> dict:
    _ensure_dir()
    current = read_user_profile()
    new_content = current.rstrip() + "\n" + content + "\n" if current.strip() else content + "\n"
    if len(new_content) > USER_CHAR_LIMIT:
        return {
            "success": False,
            "output": f"Appending would exceed {USER_CHAR_LIMIT} char limit (current: {len(current)}, adding: {len(content)}). Please clean up old entries first.",
        }
    USER_FILE.write_text(new_content, encoding="utf-8")
    return {"success": True, "output": f"Appended to USER.md ({len(new_content)} / {USER_CHAR_LIMIT} chars)"}


# ── Per-session memory (stored in session JSON) ──

def read_session_memory(session_id: str) -> str:
    """Read per-session memory."""
    if not session_id:
        return ""
    return session_service.get_session_memory(session_id)


def write_session_memory(session_id: str, content: str) -> dict:
    """Replace per-session memory entirely."""
    if not session_id:
        return {"success": False, "output": "No active session."}
    if len(content) > SESSION_MEMORY_CHAR_LIMIT:
        return {
            "success": False,
            "output": f"Content exceeds {SESSION_MEMORY_CHAR_LIMIT} char limit ({len(content)} chars). Please compress.",
        }
    result = session_service.update_session_memory(session_id, content)
    if result is None:
        return {"success": False, "output": "Session not found."}
    return {"success": True, "output": f"Session memory updated ({len(content)} / {SESSION_MEMORY_CHAR_LIMIT} chars)"}


def append_session_memory(session_id: str, content: str) -> dict:
    """Append to per-session memory."""
    if not session_id:
        return {"success": False, "output": "No active session."}
    current = read_session_memory(session_id)
    new_content = current.rstrip() + "\n" + content + "\n" if current.strip() else content + "\n"
    if len(new_content) > SESSION_MEMORY_CHAR_LIMIT:
        return {
            "success": False,
            "output": f"Appending would exceed {SESSION_MEMORY_CHAR_LIMIT} char limit (current: {len(current)}, adding: {len(content)}). Please clean up old entries first.",
        }
    result = session_service.update_session_memory(session_id, new_content)
    if result is None:
        return {"success": False, "output": "Session not found."}
    return {"success": True, "output": f"Appended to session memory ({len(new_content)} / {SESSION_MEMORY_CHAR_LIMIT} chars)"}


MEMORY_COMPRESS_PROMPT = """请将以下会话记忆精简压缩到原来的一半左右长度，保留最重要的信息，删除过时或重复的内容。
输出格式与原文相同（markdown 列表），只输出压缩后的内容，不要解释。

原始记忆：
{memory}"""


async def compress_session_memory_if_needed(session_id: str) -> bool:
    """Hook: auto-compress session memory when >= 80% full. Returns True if compressed."""
    if not session_id:
        return False
    current = read_session_memory(session_id)
    if not current.strip():
        return False
    usage_pct = len(current) / SESSION_MEMORY_CHAR_LIMIT * 100
    if usage_pct < 80:
        return False

    # Call LLM to compress
    from services.llm_service import chat_completion
    try:
        resp = await chat_completion(
            [{"role": "user", "content": MEMORY_COMPRESS_PROMPT.format(memory=current)}],
            model=None,
            tools=None,
        )
        compressed = resp["choices"][0]["message"].get("content", "").strip()
        if compressed and len(compressed) < len(current):
            write_session_memory(session_id, compressed)
            return True
    except Exception:
        pass
    return False


# ── Snapshot for system prompt ──

def get_memory_snapshot(session_id: str = "") -> str:
    """Get frozen snapshot of all memory for system prompt injection."""
    soul = read_soul().strip()
    user = read_user_profile().strip()
    session_mem = read_session_memory(session_id).strip() if session_id else ""

    parts = []
    if soul:
        parts.append(f"## Agent Soul (SOUL.md — DO NOT modify)\n{soul}")
    if user:
        parts.append(f"## User Profile (USER.md — global)\n{user}")
    if session_mem:
        parts.append(f"## Session Memory (this conversation only)\n{session_mem}")

    if not parts:
        return ""
    return "\n\n".join(parts)


def get_memory_stats(session_id: str = "") -> dict:
    """Get current memory usage statistics."""
    session_mem = read_session_memory(session_id) if session_id else ""
    user = read_user_profile()
    return {
        "memory_chars": len(session_mem),
        "memory_limit": SESSION_MEMORY_CHAR_LIMIT,
        "memory_pct": round(len(session_mem) / SESSION_MEMORY_CHAR_LIMIT * 100) if SESSION_MEMORY_CHAR_LIMIT else 0,
        "user_chars": len(user),
        "user_limit": USER_CHAR_LIMIT,
        "user_pct": round(len(user) / USER_CHAR_LIMIT * 100) if USER_CHAR_LIMIT else 0,
    }


# ── Nudge: memory reflection prompt ──

NUDGE_PROMPT = """Review the recent conversation and save important context to memory.

**Session Memory** (`update_memory`) — ALWAYS update this with:
- What the user is working on / discussing in this conversation
- Key decisions, results, or conclusions reached
- Any task context that would help you give better answers in later messages

**User Profile** (`update_user_profile`) — Only for STABLE cross-session facts:
- User name, preferences, communication style
- Persistent habits or environment info

**Do NOT save:**
- Trivial greetings or chitchat
- Information already in memory

Current memory contents:
{memory_snapshot}

Current memory stats:
- Session memory: {memory_chars}/{memory_limit} chars ({memory_pct}%)
- User profile: {user_chars}/{user_limit} chars ({user_pct}%)

**Action required:** Call `update_memory` to save a brief summary of the conversation so far. Use mode='replace' to rewrite if updating existing content.
If memory is getting full (>80%), compress it with mode='replace'.
If truly nothing worth saving, continue normally."""


def build_nudge_prompt(session_id: str = "") -> str:
    """Build the nudge prompt with current memory state."""
    snapshot = get_memory_snapshot(session_id)
    stats = get_memory_stats(session_id)
    return NUDGE_PROMPT.format(
        memory_snapshot=snapshot or "(empty)",
        **stats,
    )
