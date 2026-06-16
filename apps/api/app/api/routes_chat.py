"""聊天 API：普通问答 + SSE 流式输出。"""

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])

# 流式分片大小（字符）
_STREAM_CHUNK_SIZE = 6


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
        result = await chat_service.chat(
            req.platform, req.conversation_id, req.user_id, req.message, session, req.user_name
        )
        answer: str = result["answer"]
        # 分片输出（真实 token 级流式依赖 LLM stream，此处先按字符分片）
        for i in range(0, len(answer), _STREAM_CHUNK_SIZE):
            piece = answer[i : i + _STREAM_CHUNK_SIZE]
            yield f"event: token\ndata: {json.dumps({'content': piece}, ensure_ascii=False)}\n\n"
        yield (
            "event: references\ndata: "
            f"{json.dumps({'references': result['references']}, ensure_ascii=False)}\n\n"
        )
        yield (
            "event: done\ndata: "
            f"{json.dumps({'success': True, 'refused': result['refused']}, ensure_ascii=False)}\n\n"
        )

    return StreamingResponse(event_generator(), media_type="text/event-stream")
