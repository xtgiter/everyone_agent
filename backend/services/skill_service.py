"""
Skill service — manage reusable structured skills (procedural knowledge).

Skills are stored in data/skills/ in two forms:
  1. Flat file:    data/skills/{name}.md
  2. Subdirectory: data/skills/{name}/SKILL.md  (for imported / complex skills)

Metadata is extracted from YAML frontmatter (name, description).
Fallback: if no frontmatter, parse # heading and > blockquote (legacy format).
"""

import re
import yaml
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "skills"

# Regex for YAML frontmatter block
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)

SKILL_TEMPLATE = """---
name: {name}
description: {description}
category: {category}
created_at: {created_at}
---

# {name}

## 触发条件
{triggers}

## 操作步骤
{steps}

## 注意事项
{notes}

## 验证方法
{verification}
"""


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_name(name: str) -> str:
    """Sanitize skill name for filesystem use."""
    return name.replace(" ", "-").replace("/", "-").lower()


def _skill_path(name: str) -> Path:
    """Return the path for a flat-file skill."""
    return DATA_DIR / f"{_sanitize_name(name)}.md"


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from markdown content. Returns dict of key-value pairs."""
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return {}
    try:
        fm = yaml.safe_load(m.group(1))
        return fm if isinstance(fm, dict) else {}
    except yaml.YAMLError:
        return {}


def _parse_legacy(content: str, fallback_name: str) -> dict:
    """Fallback: extract name from # heading and description from > blockquote."""
    name = fallback_name
    desc = ""
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# ") and name == fallback_name:
            name = line[2:].strip()
        elif line.startswith("> ") and not desc:
            desc = line[2:].strip()
            break
    return {"name": name, "description": desc}


def _discover_skill_files() -> list[tuple[Path, str]]:
    """Discover all skill files. Returns list of (file_path, identifier).
    Scans:
      - data/skills/*.md          → identifier = stem
      - data/skills/*/SKILL.md    → identifier = parent dir name
    """
    _ensure_dir()
    results = []
    for f in sorted(DATA_DIR.glob("*.md")):
        results.append((f, f.stem))
    for f in sorted(DATA_DIR.glob("*/SKILL.md")):
        results.append((f, f.parent.name))
    return results


def _extract_meta(path: Path, identifier: str) -> dict:
    """Extract skill metadata from a file."""
    content = path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(content)
    if fm.get("name"):
        return {"name": fm["name"], "file": identifier, "description": fm.get("description", ""), "path": path}
    legacy = _parse_legacy(content, identifier)
    return {"name": legacy["name"], "file": identifier, "description": legacy["description"], "path": path}


def _find_skill(name: str) -> Path | None:
    """Find a skill file by name (exact match, then fuzzy)."""
    _ensure_dir()
    name_lower = name.lower()
    safe = _sanitize_name(name)

    # 1. Exact flat file
    p = DATA_DIR / f"{safe}.md"
    if p.exists():
        return p

    # 2. Exact subdirectory
    p = DATA_DIR / safe / "SKILL.md"
    if p.exists():
        return p

    # 3. Match by frontmatter name or fuzzy filename
    for path, identifier in _discover_skill_files():
        if name_lower in identifier.lower():
            return path
        content = path.read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)
        if fm.get("name", "").lower() == name_lower:
            return path

    return None


def list_skills() -> list[dict]:
    """List all available skills with name and description."""
    skills = []
    seen = set()
    for path, identifier in _discover_skill_files():
        if identifier in seen:
            continue
        seen.add(identifier)
        meta = _extract_meta(path, identifier)
        skills.append({"name": meta["name"], "file": meta["file"], "description": meta["description"]})
    return skills


def read_skill(name: str) -> str | None:
    """Read a skill's full content."""
    path = _find_skill(name)
    return path.read_text(encoding="utf-8") if path else None


def create_skill(name: str, description: str, triggers: str,
                 steps: str, notes: str = "", verification: str = "",
                 category: str = "general") -> dict:
    """Create a new skill from structured components."""
    _ensure_dir()
    path = _skill_path(name)
    if path.exists() or (DATA_DIR / _sanitize_name(name) / "SKILL.md").exists():
        return {"success": False, "output": f"Skill '{name}' already exists. Use update_skill to modify."}

    content = SKILL_TEMPLATE.format(
        name=name,
        description=description,
        triggers=triggers,
        steps=steps,
        notes=notes or "（暂无）",
        verification=verification or "（暂无）",
        category=category,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    path.write_text(content, encoding="utf-8")
    return {"success": True, "output": f"Skill '{name}' created at {path.name}"}


def update_skill(name: str, content: str) -> dict:
    """Update a skill's content (full replace)."""
    path = _find_skill(name)
    if not path:
        return {"success": False, "output": f"Skill '{name}' not found."}
    path.write_text(content, encoding="utf-8")
    return {"success": True, "output": f"Skill '{name}' updated."}


def delete_skill(name: str) -> dict:
    """Delete a skill (flat file only; subdirectory skills must be deleted manually)."""
    path = _find_skill(name)
    if not path:
        return {"success": False, "output": f"Skill '{name}' not found."}
    if path.name == "SKILL.md":
        return {"success": False, "output": f"Skill '{name}' is a subdirectory skill — please delete the folder manually."}
    path.unlink()
    return {"success": True, "output": f"Skill '{name}' deleted."}


def get_skill_names() -> list[str]:
    """Get skill names with descriptions for system prompt injection."""
    skills = list_skills()
    return [f"{s['name']}: {s['description']}" if s.get("description") else s["name"] for s in skills]
