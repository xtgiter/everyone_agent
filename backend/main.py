import json

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from config import settings
from services.llm_service import get_available_models, stream_chat_completion
from services.agent_service import run_agent
from services.context_service import count_messages_tokens
from services import session_service
import tools  # noqa: F401  — registers all tools on import
from tools.registry import tool_registry

app = FastAPI(title="Everyone Agent", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Fields that OpenAI-compatible APIs accept on message objects
_LLM_ALLOWED_FIELDS = {"role", "content", "name", "tool_calls", "tool_call_id"}


def _sanitize_for_llm(messages: list[dict]) -> list[dict]:
    """Strip non-standard fields (e.g. toolCalls, _node_id) so the LLM API doesn't reject them."""
    cleaned = []
    for msg in messages:
        clean = {k: v for k, v in msg.items() if k in _LLM_ALLOWED_FIELDS and v is not None}
        if "role" in clean:
            cleaned.append(clean)
    return cleaned


class Message(BaseModel):
    role: str
    content: str
    toolCalls: list | None = None


class ChatRequest(BaseModel):
    messages: list[Message]
    model: str | None = None
    session_id: str | None = None


class SessionSaveRequest(BaseModel):
    messages: list[dict]  # raw dicts to preserve toolCalls
    mode: str | None = None


class SessionCreateRequest(BaseModel):
    mode: str = "agent"


class RenameRequest(BaseModel):
    title: str


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/models")
async def models():
    model_list = await get_available_models()
    return {"models": model_list}


@app.get("/api/tools")
async def list_tools():
    return {"tools": tool_registry.list_tools()}


@app.get("/api/context-config")
async def context_config():
    return {"max_context_tokens": settings.MAX_CONTEXT_TOKENS}


class CountTokensRequest(BaseModel):
    messages: list[dict]


@app.post("/api/count-tokens")
async def count_tokens(req: CountTokensRequest):
    from services.agent_service import _load_system_prompt
    # Include system prompt in token count, matching what the agent actually sends
    system_msg = {"role": "system", "content": _load_system_prompt()}
    full_messages = [system_msg] + req.messages
    tokens = count_messages_tokens(full_messages, settings.LLM_MODEL or "gpt-3.5-turbo")
    return {"tokens": tokens, "max_tokens": settings.MAX_CONTEXT_TOKENS}


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    messages = _sanitize_for_llm([m.model_dump() for m in req.messages])

    async def event_generator():
        try:
            async for chunk in stream_chat_completion(messages, req.model):
                if await request.is_disconnected():
                    break
                yield {"data": chunk}
        except Exception as e:
            yield {"data": json.dumps({"error": str(e), "done": True})}

    return EventSourceResponse(event_generator())


@app.post("/api/agent")
async def agent(req: ChatRequest, request: Request):
    """Agent endpoint: supports tool calling via ReAct loop."""
    messages = _sanitize_for_llm([m.model_dump() for m in req.messages])

    async def event_generator():
        try:
            async for chunk in run_agent(messages, req.model, session_id=req.session_id or ""):
                if await request.is_disconnected():
                    break
                yield {"data": chunk}
        except Exception as e:
            yield {"data": json.dumps({"type": "error", "content": str(e), "done": True})}

    return EventSourceResponse(event_generator())


# ── Session Management ──

@app.post("/api/sessions")
async def create_session(req: SessionCreateRequest = SessionCreateRequest()):
    session = session_service.create_session(mode=req.mode)
    return session


@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": session_service.list_sessions()}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    session = session_service.get_session(session_id)
    if session is None:
        return {"error": "Session not found"}
    return session


@app.put("/api/sessions/{session_id}")
async def save_session(session_id: str, req: SessionSaveRequest):
    session = session_service.update_session(session_id, req.messages, req.mode)
    if session is None:
        return {"error": "Session not found"}
    return session


@app.put("/api/sessions/{session_id}/rename")
async def rename_session(session_id: str, req: RenameRequest):
    session = session_service.rename_session(session_id, req.title)
    if session is None:
        return {"error": "Session not found"}
    return {"id": session["id"], "title": session["title"]}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    ok = session_service.delete_session(session_id)
    return {"deleted": ok}


# ── Tree operations ──

class SwitchBranchRequest(BaseModel):
    node_id: str


@app.post("/api/sessions/{session_id}/switch-branch")
async def switch_branch(session_id: str, req: SwitchBranchRequest):
    """Switch to a different branch by selecting a node."""
    result = session_service.switch_branch(session_id, req.node_id)
    if result is None:
        return {"error": "Session or node not found"}
    return result


@app.post("/api/sessions/{session_id}/backtrack")
async def backtrack(session_id: str, req: SwitchBranchRequest):
    """Go back to a specific point in the conversation."""
    result = session_service.backtrack(session_id, req.node_id)
    if result is None:
        return {"error": "Session or node not found"}
    return result


@app.post("/api/sessions/{session_id}/compact")
async def compact_session(session_id: str):
    """Compact JSONL file by removing redundant meta lines."""
    session_service.compact_session(session_id)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=True,
    )
