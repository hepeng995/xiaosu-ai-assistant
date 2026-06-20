"""聊天 API：普通问答 + SSE 流式输出。"""

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])

@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, session: AsyncSession = Depends(get_db)) -> ChatResponse:
    """普通聊天：一次性返回 answer + references。"""
    result = await chat_service.chat(
        req.platform, req.conversation_id, req.user_id, req.message, session, req.user_name
    )
    return ChatResponse(**result)


@router.post("/stream")
async def chat_stream(
    req: ChatRequest, session: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """SSE 流式聊天：依次发送 token / references / done 事件。"""

    async def event_generator():
        async for item in chat_service.stream_chat(
            req.platform, req.conversation_id, req.user_id, req.message, session, req.user_name
        ):
            yield (
                f"event: {item['event']}\n"
                f"data: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")
