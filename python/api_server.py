from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
from query import process_chat_message
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RAG API for WhatsApp Bot")

class ChatRequest(BaseModel):
    whatsapp_id: str
    message: str
    context: Optional[Dict[str, Any]] = {}
    session_state: Optional[str] = "initial"

class ChatResponse(BaseModel):
    response: str
    session_state: str = "initial"  # Changed from "active" to "initial"
    context_updates: Dict[str, Any] = {}
    next_question: Optional[str] = None
    completion_status: Optional[str] = None

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint для обработки сообщений от WhatsApp с интеллектуальным извлечением информации
    """
    try:
        logger.info(f"Received message from {request.whatsapp_id}: {request.message}")

        # Вся логика обработки теперь в query.py
        result = process_chat_message(request.whatsapp_id, request.message, request.context)

        # Конвертируем результат в ChatResponse
        response = ChatResponse(
            response=result["response"],
            session_state=result["session_state"],
            context_updates=result["context_updates"],
            next_question=result["next_question"],
            completion_status=result["completion_status"]
        )

        logger.info(f"Sending response to {request.whatsapp_id}: {response.response[:100]}...")
        return response
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "RAG API"}

@app.get("/")
async def root():
    return {"message": "RAG API for WhatsApp Bankruptcy Bot"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)