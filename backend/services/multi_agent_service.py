"""
Multi-Agent Service — spawn and run sub-agents with isolated context.

Sub-agents:
  - Load a profile from data/agents/{name}.yaml
  - Get their own system prompt, tool subset, and fresh context
  - Run a non-streaming ReAct loop to completion
  - Return the final text result to the caller
  - Cannot recursively call delegate_task (no infinite spawning)
"""

import json
import asyncio
import yaml
from pathlib import Path
from typing import Any

from services.llm_service import chat_completion
from tools.registry import tool_registry

AGENTS_DIR = Path(__file__).resolve().parent.parent / "data" / "agents"
DEFAULT_MAX_ROUNDS = 6
MAX_CONCURRENT_SUB_AGENTS = 3

# Semaphore to limit concurrent sub-agent runs
_sub_agent_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SUB_AGENTS)


def list_agent_profiles() -> list[dict]:
    """List all available agent profiles."""
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    profiles = []
    for f in sorted(AGENTS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            profiles.append({
                "name": data.get("name", f.stem),
                "description": data.get("description", ""),
            })
        except Exception:
            continue
    return profiles


def load_agent_profile(name: str) -> dict | None:
    """Load a single agent profile by name."""
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = AGENTS_DIR / f"{name}.yaml"
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _build_sub_agent_prompt(profile: dict, goal: str, context: str) -> str:
    """Build the system prompt for a sub-agent."""
    base_prompt = profile.get("system_prompt", "You are a helpful sub-agent.")
    tools_desc = tool_registry.get_tools_description(only=profile.get("tools"))

    return f"""{base_prompt}

## 你的工具

{tools_desc}

## 当前任务

**目标**: {goal}

**上下文**:
{context}

## 重要限制

- 你是一个子 Agent，完成任务后直接输出结果
- 不要询问用户更多信息，基于已有上下文尽力完成
- 输出应简明扼要、结构清晰
"""


async def run_sub_agent(
    agent_name: str,
    goal: str,
    context: str = "",
    model: str | None = None,
    session_id: str = "",
) -> dict[str, Any]:
    """
    Run a sub-agent to completion (non-streaming).

    Returns:
        {"success": bool, "output": str, "tool_calls": list[dict]}
    """
    profile = load_agent_profile(agent_name)
    if not profile:
        return {
            "success": False,
            "output": f"Agent profile '{agent_name}' not found. Available: {[p['name'] for p in list_agent_profiles()]}",
            "tool_calls": [],
        }

    allowed_tools = profile.get("tools")
    max_rounds = profile.get("max_rounds", DEFAULT_MAX_ROUNDS)

    # Build system prompt
    system_prompt = _build_sub_agent_prompt(profile, goal, context)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": goal},
    ]

    # Get tool definitions (filtered to allowed tools)
    tool_definitions = tool_registry.get_all_definitions(only=allowed_tools)

    # Context for tool execution
    tool_context = {"session_id": session_id} if session_id else None

    tool_call_log = []

    async with _sub_agent_semaphore:
        for round_num in range(max_rounds):
            try:
                response = await chat_completion(messages, model, tools=tool_definitions or None)
            except Exception as e:
                return {
                    "success": False,
                    "output": f"Sub-agent LLM error: {str(e)}",
                    "tool_calls": tool_call_log,
                }

            choice = response["choices"][0]
            msg = choice["message"]
            tool_calls = msg.get("tool_calls")

            if tool_calls:
                messages.append(msg)

                for tc in tool_calls:
                    func = tc["function"]
                    tool_name = func["name"]
                    try:
                        arguments = json.loads(func["arguments"])
                    except json.JSONDecodeError:
                        arguments = {}

                    # Execute tool (with allowed filter)
                    result = await tool_registry.call(
                        tool_name, arguments,
                        context=tool_context,
                        allowed=allowed_tools,
                    )

                    tool_call_log.append({
                        "tool": tool_name,
                        "arguments": arguments,
                        "success": result["success"],
                        "output_preview": result["output"][:200],
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result["output"][:8000],
                    })

                continue

            # Final text response
            final_content = msg.get("content", "")
            return {
                "success": True,
                "output": final_content,
                "tool_calls": tool_call_log,
            }

    # Hit max rounds
    return {
        "success": True,
        "output": f"[Sub-agent '{agent_name}' reached max rounds ({max_rounds}). Partial results may be incomplete.]",
        "tool_calls": tool_call_log,
    }


async def run_parallel_sub_agents(
    tasks: list[dict],
    model: str | None = None,
    session_id: str = "",
) -> list[dict]:
    """
    Run multiple sub-agents in parallel (parallel mode).

    tasks: list of {"agent": str, "goal": str, "context": str}
    Returns: list of results in same order as tasks
    """
    coros = [
        run_sub_agent(
            agent_name=t["agent"],
            goal=t["goal"],
            context=t.get("context", ""),
            model=model,
            session_id=session_id,
        )
        for t in tasks
    ]
    return await asyncio.gather(*coros)


async def run_chain_sub_agents(
    steps: list[dict],
    initial_context: str = "",
    model: str | None = None,
    session_id: str = "",
) -> dict[str, Any]:
    """
    Run sub-agents in a chain/pipeline (chain mode).
    Each step's output is appended to the context of the next step.

    steps: list of {"agent": str, "goal": str}
    initial_context: shared context passed to the first step
    Returns: {"success": bool, "output": str, "steps": list[dict]}
    """
    accumulated_context = initial_context
    step_results = []

    for i, step in enumerate(steps):
        agent = step.get("agent", "")
        goal = step.get("goal", "")

        result = await run_sub_agent(
            agent_name=agent,
            goal=goal,
            context=accumulated_context,
            model=model,
            session_id=session_id,
        )

        step_results.append({
            "step": i + 1,
            "agent": agent,
            "goal": goal,
            "success": result["success"],
            "output_preview": result["output"][:300],
        })

        if not result["success"]:
            return {
                "success": False,
                "output": f"Chain failed at step {i + 1} ({agent}): {result['output']}",
                "steps": step_results,
            }

        # Append this step's output to context for the next step
        accumulated_context += f"\n\n--- Step {i + 1} ({agent}) output ---\n{result['output']}"

    # Final output is the last step's result
    return {
        "success": True,
        "output": result["output"],
        "steps": step_results,
    }
