"""
Delegate tools — allow the main agent to spawn sub-agents for task delegation.

Three modes:
  - single:   delegate_task       → one sub-agent, one task
  - parallel: delegate_parallel   → multiple sub-agents simultaneously
  - chain:    delegate_chain      → pipeline: A output → B input → C input
"""

import json
from typing import Any
from tools.base import BaseTool
from services.multi_agent_service import (
    list_agent_profiles, run_sub_agent,
    run_parallel_sub_agents, run_chain_sub_agents,
)


class ListAgentsTool(BaseTool):
    name = "list_agents"
    description = "List all available sub-agent profiles that can be used with delegate_task."
    parameters = {
        "type": "object",
        "properties": {},
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        profiles = list_agent_profiles()
        if not profiles:
            return {"success": True, "output": "No agent profiles available."}
        lines = [f"- **{p['name']}**: {p['description']}" for p in profiles]
        return {"success": True, "output": "Available sub-agents:\n" + "\n".join(lines)}


class DelegateTaskTool(BaseTool):
    name = "delegate_task"
    description = (
        "Delegate a task to a specialized sub-agent. The sub-agent runs independently "
        "with its own context and tools, then returns the result. "
        "IMPORTANT: You must pass all necessary context — the sub-agent has NO access "
        "to the current conversation history."
    )
    parameters = {
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "Name of the sub-agent profile (e.g. 'researcher', 'coder', 'reviewer'). Use list_agents to see available profiles.",
            },
            "goal": {
                "type": "string",
                "description": "Clear description of what the sub-agent should accomplish.",
            },
            "context": {
                "type": "string",
                "description": "All background information the sub-agent needs: file paths, error messages, prior findings, constraints, etc. Be thorough — the sub-agent knows nothing about the current conversation.",
            },
        },
        "required": ["agent", "goal", "context"],
    }

    async def execute(self, agent: str, goal: str, context: str = "",
                      _session_id: str = "", **kwargs) -> dict[str, Any]:
        result = await run_sub_agent(
            agent_name=agent,
            goal=goal,
            context=context,
            session_id=_session_id,
        )

        # Format output for the main agent
        output_parts = []
        if result.get("tool_calls"):
            tool_summary = ", ".join(
                f"{tc['tool']}({'✓' if tc['success'] else '✗'})"
                for tc in result["tool_calls"]
            )
            output_parts.append(f"[Sub-agent '{agent}' used tools: {tool_summary}]")

        output_parts.append(result.get("output", "(no output)"))

        return {
            "success": result.get("success", False),
            "output": "\n\n".join(output_parts),
        }


class DelegateParallelTool(BaseTool):
    name = "delegate_parallel"
    description = (
        "Run multiple sub-agents IN PARALLEL and return all results. "
        "Use this when you have independent sub-tasks that can run simultaneously. "
        "Each task specifies its own agent, goal, and context. Max 3 concurrent."
    )
    parameters = {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "string",
                "description": (
                    'JSON array of tasks. Each task: {"agent": "name", "goal": "...", "context": "..."}. '
                    'Example: [{"agent":"researcher","goal":"search AI jobs","context":"..."},'
                    '{"agent":"researcher","goal":"search CS jobs","context":"..."}]'
                ),
            },
        },
        "required": ["tasks"],
    }

    async def execute(self, tasks: str, _session_id: str = "", **kwargs) -> dict[str, Any]:
        try:
            task_list = json.loads(tasks)
        except json.JSONDecodeError:
            return {"success": False, "output": "Invalid JSON in 'tasks' parameter."}

        if not isinstance(task_list, list) or len(task_list) == 0:
            return {"success": False, "output": "'tasks' must be a non-empty JSON array."}
        if len(task_list) > 3:
            return {"success": False, "output": "Max 3 parallel tasks allowed."}

        results = await run_parallel_sub_agents(
            tasks=task_list,
            session_id=_session_id,
        )

        output_parts = []
        all_success = True
        for i, (task, result) in enumerate(zip(task_list, results)):
            status = "✓" if result["success"] else "✗"
            agent = task.get("agent", "?")
            goal = task.get("goal", "")[:60]
            tool_info = ""
            if result.get("tool_calls"):
                tool_summary = ", ".join(
                    f"{tc['tool']}({'✓' if tc['success'] else '✗'})"
                    for tc in result["tool_calls"]
                )
                tool_info = f" [tools: {tool_summary}]"
            output_parts.append(
                f"### Task {i+1} [{status}] ({agent}): {goal}{tool_info}\n\n{result.get('output', '(no output)')}"
            )
            if not result["success"]:
                all_success = False

        return {
            "success": all_success,
            "output": "\n\n---\n\n".join(output_parts),
        }


class DelegateChainTool(BaseTool):
    name = "delegate_chain"
    description = (
        "Run sub-agents in a CHAIN (pipeline): each step's output becomes the next step's context. "
        "Use this for multi-stage workflows like: researcher → coder → reviewer. "
        "If any step fails, the chain stops."
    )
    parameters = {
        "type": "object",
        "properties": {
            "steps": {
                "type": "string",
                "description": (
                    'JSON array of steps (executed in order). Each step: {"agent": "name", "goal": "..."}. '
                    'Example: [{"agent":"researcher","goal":"find best practices for X"},'
                    '{"agent":"coder","goal":"implement based on research"},'
                    '{"agent":"reviewer","goal":"review the implementation"}]'
                ),
            },
            "context": {
                "type": "string",
                "description": "Initial context shared with the first step. Include all background info needed.",
            },
        },
        "required": ["steps", "context"],
    }

    async def execute(self, steps: str, context: str = "",
                      _session_id: str = "", **kwargs) -> dict[str, Any]:
        try:
            step_list = json.loads(steps)
        except json.JSONDecodeError:
            return {"success": False, "output": "Invalid JSON in 'steps' parameter."}

        if not isinstance(step_list, list) or len(step_list) == 0:
            return {"success": False, "output": "'steps' must be a non-empty JSON array."}

        result = await run_chain_sub_agents(
            steps=step_list,
            initial_context=context,
            session_id=_session_id,
        )

        # Format step summaries
        output_parts = []
        for s in result.get("steps", []):
            status = "✓" if s["success"] else "✗"
            output_parts.append(
                f"**Step {s['step']}** [{status}] ({s['agent']}): {s['goal'][:60]}\n> {s['output_preview'][:150]}..."
            )

        output_parts.append(f"\n### Final Output\n\n{result.get('output', '(no output)')}")

        return {
            "success": result.get("success", False),
            "output": "\n\n".join(output_parts),
        }
