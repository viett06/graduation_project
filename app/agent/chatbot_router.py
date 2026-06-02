from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from app.api.deps import get_db
from app.core.security.dependencies import get_current_active_user
from app.schemas.chatbotConversationSchema import (
    ChatbotMessageResponse,
    ChatbotPromptRequest,
    ChatbotPromptResponse,
)
from app.service.chatbotConversationService import ChatbotConversationService
from sqlalchemy.orm import Session

from app.agent.chatbot_service import run_agent, stream_agent_answer

router = APIRouter()

@router.post("", response_model=ChatbotPromptResponse, status_code=200)
async def prompt_chatbot_api(
        req: ChatbotPromptRequest,
        session: Session = Depends(get_db),
        current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    user_id = current_user.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token.")
    if not req.prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt is required.")

    return await run_agent(
        req.prompt,
        session,
        user_id=user_id,
    )


@router.post("/public", response_model=ChatbotPromptResponse, status_code=200)
async def prompt_public_chatbot_api(
        req: ChatbotPromptRequest,
        session: Session = Depends(get_db),
):
    if not req.prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt is required.")

    return await run_agent(
        req.prompt,
        session,
        user_id=None,
        use_context=False,
    )


@router.post("/stream", status_code=200)
async def prompt_chatbot_stream_api(
        req: ChatbotPromptRequest,
        session: Session = Depends(get_db),
        current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    user_id = current_user.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token.")
    if not req.prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt is required.")

    return StreamingResponse(
        stream_agent_answer(
            req.prompt,
            session,
            user_id=user_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/public/stream", status_code=200)
async def prompt_public_chatbot_stream_api(
        req: ChatbotPromptRequest,
        session: Session = Depends(get_db),
):
    if not req.prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt is required.")

    return StreamingResponse(
        stream_agent_answer(
            req.prompt,
            session,
            user_id=None,
            use_context=False,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/messages", response_model=list[ChatbotMessageResponse])
async def list_chatbot_messages(
        limit: int = 20,
        session: Session = Depends(get_db),
        current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    user_id = current_user.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token.")

    return ChatbotConversationService(session).get_current_user_messages(
        user_id=user_id,
        limit=limit,
    )
