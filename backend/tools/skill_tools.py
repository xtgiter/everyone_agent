"""
Skill management tools — create, read, update, list, delete skills.
"""

from tools.base import BaseTool
from services import skill_service


class ListSkillsTool(BaseTool):
    name = "list_skills"
    description = "List all available skills with their names and descriptions."
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> dict:
        skills = skill_service.list_skills()
        if not skills:
            return {"success": True, "output": "No skills found. You can create one with create_skill."}
        lines = [f"- **{s['name']}**: {s['description']}" for s in skills]
        return {"success": True, "output": f"Found {len(skills)} skill(s):\n" + "\n".join(lines)}


class ReadSkillTool(BaseTool):
    name = "read_skill"
    description = "Read a skill's full content by name."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name to read"},
        },
        "required": ["name"],
    }

    async def execute(self, name: str, **kwargs) -> dict:
        content = skill_service.read_skill(name)
        if content is None:
            return {"success": False, "output": f"Skill '{name}' not found."}
        return {"success": True, "output": content}


class CreateSkillTool(BaseTool):
    name = "create_skill"
    description = "Create a new reusable skill (structured SOP). Include trigger conditions, steps, notes, and verification method."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name (e.g. 'docker-cleanup')"},
            "description": {"type": "string", "description": "One-line description of what this skill does"},
            "triggers": {"type": "string", "description": "When to use this skill (trigger conditions)"},
            "steps": {"type": "string", "description": "Step-by-step execution instructions"},
            "notes": {"type": "string", "description": "Gotchas, warnings, or things learned"},
            "verification": {"type": "string", "description": "How to verify the skill executed successfully"},
            "category": {"type": "string", "description": "Category tag (e.g. 'devops', 'data', 'general')"},
        },
        "required": ["name", "description", "triggers", "steps"],
    }

    async def execute(self, name: str, description: str, triggers: str, steps: str,
                      notes: str = "", verification: str = "", category: str = "general", **kwargs) -> dict:
        return skill_service.create_skill(name, description, triggers, steps, notes, verification, category)


class UpdateSkillTool(BaseTool):
    name = "update_skill"
    description = "Update an existing skill's content. Provide the full updated markdown content."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name to update"},
            "content": {"type": "string", "description": "Full updated skill content (markdown)"},
        },
        "required": ["name", "content"],
    }

    async def execute(self, name: str, content: str, **kwargs) -> dict:
        return skill_service.update_skill(name, content)


class DeleteSkillTool(BaseTool):
    name = "delete_skill"
    description = "Delete a skill by name."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name to delete"},
        },
        "required": ["name"],
    }

    async def execute(self, name: str, **kwargs) -> dict:
        return skill_service.delete_skill(name)
