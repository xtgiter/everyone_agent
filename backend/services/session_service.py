"""
Tree-shaped session management with JSONL persistence.

Storage format (.jsonl, append-only):
  Line types:
    {"type":"meta", "id":"...", "title":"...", "mode":"...", "active_leaf":"...", "memory":"...", ...}
    {"type":"node", "id":"n1", "parent":null, "role":"user", "content":"...", "ts":"..."}
    {"type":"node", "id":"n2", "parent":"n1", "role":"assistant", "content":"...", "toolCalls":[...], "ts":"..."}
    {"type":"summary", "id":"s1", "covers":["n1","n2","n3","n4"], "content":"...", "ts":"..."}

Tree structure:
  - Each node has a parent pointer → forms a tree
  - Multiple children of the same parent = branches (like Git)
  - active_leaf tracks which leaf is currently displayed
  - Path from root to active_leaf = current conversation

JSONL benefits:
  - Append-only for new messages (fast writes)
  - Meta updates append a new meta line (latest wins)
  - Branching: just append a new node with a different parent
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sessions"


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _session_path(session_id: str) -> Path:
    return DATA_DIR / f"{session_id}.jsonl"


def _memory_path(session_id: str) -> Path:
    return DATA_DIR / f"{session_id}_memory.md"


def _gen_id() -> str:
    return uuid.uuid4().hex[:8]


# ── JSONL I/O ──

def _read_lines(session_id: str) -> list[dict]:
    path = _session_path(session_id)
    if not path.exists():
        return []
    lines = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        line = line.strip()
        if line:
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return lines


def _append(session_id: str, entry: dict):
    _ensure_dir()
    with open(_session_path(session_id), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _rewrite(session_id: str, entries: list[dict]):
    _ensure_dir()
    with open(_session_path(session_id), "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


# ── Internal parsing ──

def _parse(session_id: str) -> tuple[dict, dict[str, dict], list[dict]]:
    """Parse JSONL → (latest_meta, {node_id: node}, [summaries])."""
    lines = _read_lines(session_id)
    meta = {}
    nodes: dict[str, dict] = {}
    summaries: list[dict] = []
    for entry in lines:
        t = entry.get("type")
        if t == "meta":
            meta = entry  # latest meta wins
        elif t == "node":
            nodes[entry["id"]] = entry
        elif t == "summary":
            summaries.append(entry)
    return meta, nodes, summaries


def _path_to_root(nodes: dict[str, dict], leaf_id: str) -> list[dict]:
    """Trace from leaf to root, return [root, ..., leaf]."""
    path = []
    cur = leaf_id
    visited = set()
    while cur and cur in nodes:
        if cur in visited:
            break
        visited.add(cur)
        path.append(nodes[cur])
        cur = nodes[cur].get("parent")
    path.reverse()
    return path


def _children_of(nodes: dict[str, dict], parent_id: str | None) -> list[dict]:
    return [n for n in nodes.values() if n.get("parent") == parent_id]


def _update_meta(session_id: str, **kwargs):
    """Append a new meta line with updates (latest-wins strategy)."""
    meta, _, _ = _parse(session_id)
    meta.update(kwargs)
    meta["type"] = "meta"
    _append(session_id, meta)


# ── Public API ──

def create_session(title: str = "", mode: str = "agent") -> dict:
    _ensure_dir()
    session_id = uuid.uuid4().hex[:12]
    now = datetime.now().isoformat()
    meta = {
        "type": "meta",
        "id": session_id,
        "title": title or "New Chat",
        "mode": mode,
        "created_at": now,
        "updated_at": now,
        "active_leaf": None,
    }
    _rewrite(session_id, [meta])
    # Create empty per-session memory file
    _memory_path(session_id).write_text("", encoding="utf-8")
    return {k: v for k, v in meta.items() if k != "type"}


def list_sessions() -> list[dict]:
    _ensure_dir()
    sessions = []
    # Support both .jsonl (new) and .json (legacy)
    for f in list(DATA_DIR.glob("*.jsonl")) + list(DATA_DIR.glob("*.json")):
        try:
            if f.suffix == ".jsonl":
                meta, nodes, _ = _parse(f.stem)
                if not meta:
                    continue
                sessions.append({
                    "id": meta["id"],
                    "title": meta.get("title", "New Chat"),
                    "mode": meta.get("mode", "agent"),
                    "created_at": meta["created_at"],
                    "updated_at": meta.get("updated_at", meta["created_at"]),
                    "message_count": len(nodes),
                })
            else:
                # Legacy .json format
                data = json.loads(f.read_text(encoding="utf-8"))
                sessions.append({
                    "id": data["id"],
                    "title": data.get("title", "New Chat"),
                    "mode": data.get("mode", "agent"),
                    "created_at": data["created_at"],
                    "updated_at": data.get("updated_at", data["created_at"]),
                    "message_count": len(data.get("messages", [])),
                })
        except Exception:
            continue
    sessions.sort(key=lambda s: s["updated_at"], reverse=True)
    return sessions


def get_session(session_id: str) -> dict | None:
    """Get session with current path messages + branch info."""
    # Try new JSONL format first
    if _session_path(session_id).exists():
        return _get_session_jsonl(session_id)
    # Fallback to legacy JSON
    legacy = DATA_DIR / f"{session_id}.json"
    if legacy.exists():
        return _get_session_legacy(session_id)
    return None


def _get_session_jsonl(session_id: str) -> dict | None:
    meta, nodes, summaries = _parse(session_id)
    if not meta:
        return None

    # Get current conversation path
    leaf = meta.get("active_leaf")
    path = _path_to_root(nodes, leaf) if leaf and leaf in nodes else []

    # Convert to messages array (frontend-compatible)
    messages = []
    for node in path:
        msg = {"role": node["role"], "content": node.get("content", "")}
        if node.get("toolCalls"):
            msg["toolCalls"] = node["toolCalls"]
        msg["_node_id"] = node["id"]
        messages.append(msg)

    # Build branch info: for each node on the path, check if it has siblings
    branches = {}
    for node in path:
        siblings = [n for n in nodes.values() if n.get("parent") == node.get("parent") and n["id"] != node["id"]]
        if siblings:
            branch_list = [{"id": node["id"], "preview": node.get("content", "")[:50], "active": True}]
            for s in siblings:
                branch_list.append({"id": s["id"], "preview": s.get("content", "")[:50], "active": False})
            branches[node["id"]] = branch_list

    return {
        "id": meta["id"],
        "title": meta.get("title", "New Chat"),
        "mode": meta.get("mode", "agent"),
        "created_at": meta["created_at"],
        "updated_at": meta.get("updated_at", meta["created_at"]),
        "memory": get_session_memory(session_id),
        "messages": messages,
        "branches": branches,
        "active_leaf": leaf,
        "summaries": [{"covers": s.get("covers", []), "content": s.get("content", "")} for s in summaries],
    }


def _get_session_legacy(session_id: str) -> dict | None:
    """Read legacy .json format for backward compatibility."""
    path = DATA_DIR / f"{session_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("mode", "agent")
        data.setdefault("memory", "")
        data.setdefault("branches", {})
        data.setdefault("active_leaf", None)
        data.setdefault("summaries", [])
        return data
    except Exception:
        return None


# ── Message operations (tree-aware) ──

def add_message(session_id: str, role: str, content: str,
                parent_id: str | None = None, tool_calls: list | None = None) -> dict | None:
    """Add a message node. Returns the new node. If parent_id is None, uses active_leaf."""
    meta, nodes, _ = _parse(session_id)
    if not meta:
        return None

    if parent_id is None:
        parent_id = meta.get("active_leaf")

    node_id = _gen_id()
    now = datetime.now().isoformat()
    node = {
        "type": "node",
        "id": node_id,
        "parent": parent_id,
        "role": role,
        "content": content,
        "ts": now,
    }
    if tool_calls:
        node["toolCalls"] = tool_calls

    _append(session_id, node)

    # Update meta: active_leaf + updated_at + auto-title
    updates = {"active_leaf": node_id, "updated_at": now}
    if meta.get("title") == "New Chat" and role == "user" and content:
        updates["title"] = content[:40] + ("..." if len(content) > 40 else "")
    _update_meta(session_id, **updates)

    return {k: v for k, v in node.items() if k != "type"}


def update_session(session_id: str, messages: list[dict], mode: str | None = None) -> dict | None:
    """Incremental update: append only truly new messages, preserving existing tree branches.
    Messages with a `_node_id` matching an existing node are skipped (already persisted).
    New messages (no `_node_id` or unknown id) are appended with correct parent pointers."""
    meta, existing_nodes, _ = _parse(session_id)
    if not meta:
        return None

    now = datetime.now().isoformat()

    # Walk the flat messages: track parent chain, only create nodes for new ones
    parent = None
    last_id = None
    new_nodes = []
    for msg in messages:
        node_id = msg.get("_node_id")
        if node_id and node_id in existing_nodes:
            # Already persisted — just track chain position
            parent = node_id
            last_id = node_id
            continue

        # New message — create a tree node
        new_id = _gen_id()
        node = {
            "type": "node",
            "id": new_id,
            "parent": parent,
            "role": msg["role"],
            "content": msg.get("content", ""),
            "ts": now,
        }
        if msg.get("toolCalls"):
            node["toolCalls"] = msg["toolCalls"]
        new_nodes.append(node)
        parent = new_id
        last_id = new_id

    # Append new nodes (existing file stays intact → branches preserved)
    for node in new_nodes:
        _append(session_id, node)

    # Update meta
    updates: dict = {"active_leaf": last_id, "updated_at": now}
    if mode is not None:
        updates["mode"] = mode
    if meta.get("title") == "New Chat":
        for msg in messages:
            if msg.get("role") == "user" and msg.get("content"):
                updates["title"] = msg["content"][:40] + ("..." if len(msg["content"]) > 40 else "")
                break
    _update_meta(session_id, **updates)

    return {"id": meta["id"], "title": updates.get("title", meta.get("title", "New Chat")),
            "mode": updates.get("mode", meta.get("mode", "agent")), "updated_at": now}


def switch_branch(session_id: str, node_id: str) -> dict | None:
    """Switch the active path to go through node_id. Finds the deepest leaf descendant."""
    meta, nodes, _ = _parse(session_id)
    if not meta or node_id not in nodes:
        return None

    # Find deepest leaf reachable from this node
    leaf = _find_deepest_leaf(nodes, node_id)
    _update_meta(session_id, active_leaf=leaf, updated_at=datetime.now().isoformat())
    return get_session(session_id)


def _find_deepest_leaf(nodes: dict[str, dict], start_id: str) -> str:
    """Find the deepest leaf by always following the first child."""
    cur = start_id
    while True:
        children = _children_of(nodes, cur)
        if not children:
            return cur
        # Pick the newest child
        children.sort(key=lambda n: n.get("ts", ""), reverse=True)
        cur = children[0]["id"]


def backtrack(session_id: str, node_id: str) -> dict | None:
    """Set active_leaf to a specific node (go back in history)."""
    meta, nodes, _ = _parse(session_id)
    if not meta or node_id not in nodes:
        return None
    _update_meta(session_id, active_leaf=node_id, updated_at=datetime.now().isoformat())
    return get_session(session_id)


# ── Summary storage ──

def add_summary(session_id: str, covers: list[str], content: str) -> dict | None:
    """Store a compression summary for a set of node IDs."""
    meta, _, _ = _parse(session_id)
    if not meta:
        return None
    summary = {
        "type": "summary",
        "id": _gen_id(),
        "covers": covers,
        "content": content,
        "ts": datetime.now().isoformat(),
    }
    _append(session_id, summary)
    return summary


def get_summaries(session_id: str) -> list[dict]:
    """Get all stored summaries for a session."""
    _, _, summaries = _parse(session_id)
    return summaries


# ── Memory (per-session, stored as {session_id}_memory.md) ──

def get_session_memory(session_id: str) -> str:
    p = _memory_path(session_id)
    if p.exists():
        return p.read_text(encoding="utf-8")
    # Fallback: try legacy JSONL meta field or .json
    meta, _, _ = _parse(session_id)
    if meta and meta.get("memory"):
        # Migrate: write to .md file and clear meta field
        _memory_path(session_id).write_text(meta["memory"], encoding="utf-8")
        return meta["memory"]
    legacy = DATA_DIR / f"{session_id}.json"
    if legacy.exists():
        try:
            data = json.loads(legacy.read_text(encoding="utf-8"))
            return data.get("memory", "")
        except Exception:
            pass
    return ""


def update_session_memory(session_id: str, memory: str) -> dict | None:
    # Verify session exists
    if not _session_path(session_id).exists():
        legacy = DATA_DIR / f"{session_id}.json"
        if not legacy.exists():
            return None
    _ensure_dir()
    _memory_path(session_id).write_text(memory, encoding="utf-8")
    return {"id": session_id, "memory": memory}


# ── Other operations ──

def rename_session(session_id: str, title: str) -> dict | None:
    meta, _, _ = _parse(session_id)
    if not meta:
        # Try legacy
        legacy = DATA_DIR / f"{session_id}.json"
        if legacy.exists():
            try:
                data = json.loads(legacy.read_text(encoding="utf-8"))
                data["title"] = title
                data["updated_at"] = datetime.now().isoformat()
                legacy.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                return {"id": data["id"], "title": title}
            except Exception:
                pass
        return None
    _update_meta(session_id, title=title, updated_at=datetime.now().isoformat())
    return {"id": meta["id"], "title": title}


def delete_session(session_id: str) -> bool:
    deleted = False
    for ext in (".jsonl", ".json"):
        p = DATA_DIR / f"{session_id}{ext}"
        if p.exists():
            p.unlink()
            deleted = True
    # Also delete memory file
    mp = _memory_path(session_id)
    if mp.exists():
        mp.unlink()
    return deleted


# ── JSONL compaction ──

def compact_session(session_id: str):
    """Remove redundant meta lines, keeping only the latest. Reduces file size."""
    lines = _read_lines(session_id)
    if not lines:
        return
    # Keep only the last meta, plus all nodes and summaries
    last_meta = None
    others = []
    for entry in lines:
        if entry.get("type") == "meta":
            last_meta = entry
        else:
            others.append(entry)
    if last_meta:
        _rewrite(session_id, [last_meta] + others)
