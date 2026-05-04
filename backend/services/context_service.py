"""
Tiered memory compression for context management.

Architecture (3-tier):
  Tier 1 — Archive:  Compressed summaries of old conversation segments (~100-200 tokens each)
  Tier 2 — Recent:   Full messages from recent rounds (kept intact for coherence)
  Tier 3 — Current:  The latest exchange (always in full)

Compression strategy for 30 rounds:
  Original: ~6000 tokens (all messages in full)
  Compressed: [summary_1: 150t] + [summary_2: 150t] + [recent 6 msgs: 1200t] = ~1500t → 75% reduction

Summaries are cached in session JSONL as "summary" entries so they don't need recalculation.
"""

import tiktoken
from services.llm_service import chat_completion
from config import settings

# ── Tuning parameters ──
SEGMENT_SIZE = 10        # messages per compression segment
KEEP_RECENT = 6          # number of recent messages to keep in full
MIN_MESSAGES_TO_COMPRESS = 8  # don't compress if fewer than this


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def count_messages_tokens(messages: list[dict], model: str = "gpt-3.5-turbo") -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    total = 0
    for msg in messages:
        total += 4
        for key, value in msg.items():
            if isinstance(value, str):
                total += len(enc.encode(value))
    total += 2
    return total


# ── Summarization ──

SEGMENT_SUMMARY_PROMPT = """Summarize the following conversation segment concisely in the SAME LANGUAGE as the conversation.
Keep ONLY the essential information: key decisions, file paths, commands, errors, and outcomes.
Be extremely concise — aim for 2-4 sentences max.

Conversation segment:
{conversation}

Concise summary:"""

META_SUMMARY_PROMPT = """Combine and compress these conversation summaries into one ultra-concise summary.
Preserve only the most important facts and decisions. Same language as input.

Summaries to combine:
{summaries}

Combined summary:"""


async def _summarize_segment(messages: list[dict], model: str | None = None) -> str:
    model = model or settings.LLM_MODEL
    text = ""
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if content and role in ("user", "assistant"):
            text += f"[{role}]: {content[:800]}\n"

    try:
        resp = await chat_completion(
            [{"role": "user", "content": SEGMENT_SUMMARY_PROMPT.format(conversation=text[:4000])}],
            model
        )
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        return f"(Summary failed: {e})"


async def _combine_summaries(summaries: list[str], model: str | None = None) -> str:
    model = model or settings.LLM_MODEL
    text = "\n---\n".join(summaries)
    try:
        resp = await chat_completion(
            [{"role": "user", "content": META_SUMMARY_PROMPT.format(summaries=text[:4000])}],
            model
        )
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        return f"(Meta-summary failed: {e})"


# ── Main compression engine ──

async def manage_context(
    messages: list[dict],
    max_tokens: int = 0,
    model: str | None = None,
    session_id: str = "",
) -> list[dict]:
    """
    Tiered context compression.

    Strategy:
    1. If under token limit → return as-is
    2. Split conversation into segments of SEGMENT_SIZE
    3. Summarize each old segment individually (Tier 1 - Archive)
    4. Keep the most recent KEEP_RECENT messages in full (Tier 2 - Recent)
    5. If too many summaries, combine them into a meta-summary
    6. Cache summaries in session for reuse
    """
    max_tokens = max_tokens or settings.MAX_CONTEXT_TOKENS
    model = model or settings.LLM_MODEL
    total_tokens = count_messages_tokens(messages, model)

    if total_tokens <= max_tokens:
        return messages

    # Separate system prompt
    system_msg = None
    conversation = messages
    if messages and messages[0].get("role") == "system":
        system_msg = messages[0]
        conversation = messages[1:]

    if len(conversation) < MIN_MESSAGES_TO_COMPRESS:
        return messages

    # Determine how many recent messages to keep
    keep = min(KEEP_RECENT, len(conversation) - 2)
    while keep > 2:
        recent_tokens = count_messages_tokens(conversation[-keep:], model)
        if recent_tokens <= max_tokens * 0.5:
            break
        keep -= 1

    to_compress = conversation[:-keep]
    to_keep = conversation[-keep:]

    if not to_compress:
        return messages

    # Check for cached summaries from session
    existing_summaries = []
    if session_id:
        try:
            from services import session_service
            existing_summaries = session_service.get_summaries(session_id)
        except Exception:
            pass

    # Split into segments and summarize each
    segments = []
    for i in range(0, len(to_compress), SEGMENT_SIZE):
        seg = to_compress[i:i + SEGMENT_SIZE]
        segments.append(seg)

    # Generate summaries for segments that aren't already cached
    cached_node_ids = set()
    cached_texts = []
    for s in existing_summaries:
        cached_node_ids.update(s.get("covers", []))
        cached_texts.append(s.get("content", ""))

    new_summaries = []
    for seg in segments:
        seg_node_ids = [m.get("_node_id", "") for m in seg if m.get("_node_id")]

        # Check if this segment is already summarized
        if seg_node_ids and all(nid in cached_node_ids for nid in seg_node_ids):
            continue  # already cached

        summary_text = await _summarize_segment(seg, model)
        new_summaries.append({"node_ids": seg_node_ids, "text": summary_text})

        # Cache in session
        if session_id and seg_node_ids:
            try:
                from services import session_service
                session_service.add_summary(session_id, seg_node_ids, summary_text)
            except Exception:
                pass

    # Combine all summary texts
    all_summary_texts = cached_texts + [s["text"] for s in new_summaries]

    # If too many summaries, combine into a meta-summary
    if len(all_summary_texts) > 3:
        combined = await _combine_summaries(all_summary_texts, model)
        all_summary_texts = [combined]

    # Build compressed message list
    result = []
    if system_msg:
        result.append(system_msg)

    if all_summary_texts:
        summary_content = "\n---\n".join(all_summary_texts)
        result.append({
            "role": "system",
            "content": f"[Conversation history summary]\n{summary_content}",
        })

    result.extend(to_keep)
    return result
