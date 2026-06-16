from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.support_chat_service import SupportChatService

router = APIRouter()
support_chat_service = SupportChatService()

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = Field(default=None, alias="conversation_id")

class ChatResponse(BaseModel):
    reply: str
    conversation_id: str

@router.post("/support-chat")
async def support_chat_endpoint(request: ChatRequest):
    try:
        reply, new_conversation_id = await support_chat_service.get_chat_response(
            request.message, request.conversation_id
        )
        return ChatResponse(reply=reply, conversation_id=new_conversation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
