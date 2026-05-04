import json
import os
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from services.llm_service import chat_completion, stream_chat_completion
from services.memory_service import get_memory_snapshot, build_nudge_prompt, compress_session_memory_if_needed
from services.context_service import manage_context, count_messages_tokens
from services.skill_service import get_skill_names
from tools.registry import tool_registry

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

MAX_TOOL_ROUNDS = 10


def _load_system_prompt(session_id: str = "") -> str:
    """Load system prompt template and fill in runtime details."""
    template_path = PROMPT_DIR / "system_prompt.md"
    template = template_path.read_text(encoding="utf-8")

    # Build tool list description
    tool_lines = []
    for tool in tool_registry._tools.values():
        params = ", ".join(f"`{k}`" for k in tool.parameters.get("properties", {}).keys())
        tool_lines.append(f"- **{tool.name}**: {tool.description} (params: {params})")
    tool_list = "\n".join(tool_lines) if tool_lines else "No tools available."

    # Get frozen memory snapshot (per-session + global)
    memory_snapshot = get_memory_snapshot(session_id) or "(No long-term memories yet. Use memory tools to save important information.)"

    # Get available skills
    skills = get_skill_names()
    skill_list = "\n".join(f"- {s}" for s in skills) if skills else "（暂无技能，完成复杂任务后可创建）"

    return template.format(
        os_name=f"{platform.system()} {platform.release()} ({platform.version()})",
        computer_name=platform.node(),
        username=os.getenv("USERNAME") or os.getenv("USER") or "unknown",
        working_dir=os.getcwd(),
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        python_version=sys.version.split()[0],
        home_dir=str(Path.home()),
        tool_list=tool_list,
        memory_snapshot=memory_snapshot,
        skill_list=skill_list,
    )


async def run_agent(
    messages: list[dict], model: str | None = None, session_id: str = ""
) -> AsyncGenerator[str, None]:
    """
    Run the agent loop:
    1. Send messages + tool definitions to LLM
    2. If LLM wants to call tools, execute them and feed results back
    3. Repeat until LLM gives a final text response
    4. Stream the final response to the client
    """
    from config import settings as _settings

    # Prepend system prompt if not already present
    if not messages or messages[0].get("role") != "system":
        system_prompt = _load_system_prompt(session_id)
        messages = [{"role": "system", "content": system_prompt}] + messages

    # Tool execution context (passes session_id to memory tools)
    tool_context = {"session_id": session_id} if session_id else None

    # Count user-assistant rounds for nudge timing
    user_rounds = sum(1 for m in messages if m.get("role") == "user")
    nudge_interval = _settings.NUDGE_INTERVAL

    # Memory nudge every N rounds
    if nudge_interval > 0 and user_rounds > 0 and user_rounds % nudge_interval == 0:
        nudge = build_nudge_prompt(session_id)
        messages.append({"role": "system", "content": f"[Memory Nudge] {nudge}"})
        yield json.dumps({
            "type": "memory_nudge",
            "round": user_rounds,
            "done": False,
        })
    elif session_id and user_rounds > 0:
        # Lightweight mini-nudge: one-line reminder on non-nudge rounds
        messages.append({"role": "system", "content":
            "[Reminder] 如果本轮对话中发生了值得记录的事（任务完成、重要信息、关系变化等），请顺手调用 update_memory 记一笔。"
        })

    # Compress context if exceeding token limit (with summary caching)
    messages = await manage_context(messages, model=model, session_id=session_id)

    # Hook: auto-compress session memory if >= 80% full
    if session_id:
        compressed = await compress_session_memory_if_needed(session_id)
        if compressed:
            yield json.dumps({"type": "memory_compressed", "done": False})

    # Notify frontend about context status
    token_count = count_messages_tokens(messages, model or "gpt-3.5-turbo")
    yield json.dumps({
        "type": "context_info",
        "tokens": token_count,
        "max_tokens": _settings.MAX_CONTEXT_TOKENS,
        "done": False,
    })

    tool_definitions = tool_registry.get_all_definitions()

    for round_num in range(MAX_TOOL_ROUNDS):
        # Call LLM with tools (non-streaming to detect tool calls)
        try:
            response = await chat_completion(messages, model, tools=tool_definitions)
        except Exception as e:
            yield json.dumps({"type": "error", "content": f"LLM API error: {str(e)}", "done": True})
            return

        choice = response["choices"][0]
        msg = choice["message"]
        finish_reason = choice.get("finish_reason", "")

        # If the model wants to call tools
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            # Add assistant message with tool calls to history
            messages.append(msg)

            for tc in tool_calls:
                func = tc["function"]
                tool_name = func["name"]
                try:
                    arguments = json.loads(func["arguments"])
                except json.JSONDecodeError:
                    arguments = {}

                # Notify frontend about tool call
                yield json.dumps({
                    "type": "tool_call",
                    "tool": tool_name,
                    "arguments": arguments,
                    "done": False,
                })

                # Execute tool (with session context for memory tools)
                result = await tool_registry.call(tool_name, arguments, context=tool_context)

                # Notify frontend about tool result
                yield json.dumps({
                    "type": "tool_result",
                    "tool": tool_name,
                    "success": result["success"],
                    "output": result["output"][:3000],  # truncate for display
                    "done": False,
                })

                # Add tool result to messages for next LLM call
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result["output"][:8000],  # truncate for context window
                })

            # Continue loop — LLM will process tool results
            continue

        # No tool calls — this is the final text response, stream it
        final_content = msg.get("content", "")
        if final_content:
            # Yield the final answer as streamed text chunks
            # For better UX, we chunk the pre-generated text
            chunk_size = 4
            for i in range(0, len(final_content), chunk_size):
                yield json.dumps({
                    "type": "text",
                    "content": final_content[i:i + chunk_size],
                    "done": False,
                })

        yield json.dumps({"type": "text", "content": "", "done": True})
        return

    # If we hit the max rounds
    yield json.dumps({
        "type": "text",
        "content": "I've reached the maximum number of tool-calling rounds. Here's what I've gathered so far — please refine your request if needed.",
        "done": True,
    })
