from fastapi import APIRouter

from graph.builder import run_agent
from memory.sqlite_memory import SQLiteChatMemory
from schemas.chat import ChatRequest, ChatResponse, HistoryResponse, MessageItem

router = APIRouter(tags=["chat"])
memory = SQLiteChatMemory()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    result = await run_agent(
        user_message=request.message,
        session_id=request.session_id or request.conversation_id,
        memory=memory,
    )
    return ChatResponse(**result)


@router.get("/chat/{session_id}/history", response_model=HistoryResponse)
async def get_history(session_id: str) -> HistoryResponse:
    messages = await memory.get_messages(session_id)
    conversation_summary = await memory.get_summary(session_id)
    return HistoryResponse(
        session_id=session_id,
        conversation_id=session_id,
        messages=[MessageItem(role=item["role"], content=item["content"]) for item in messages],
        conversation_summary=conversation_summary,
    )


@router.delete("/chat/{session_id}", status_code=204)
async def clear_history(session_id: str) -> None:
    await memory.clear(session_id)
