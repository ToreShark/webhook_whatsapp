from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
from query import query
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RAG API for WhatsApp Bot")

class ChatRequest(BaseModel):
    whatsapp_id: str
    message: str
    context: Optional[Dict[str, Any]] = {}
    session_state: Optional[str] = "active"

class ChatResponse(BaseModel):
    response: str
    session_state: str = "active"
    context_updates: Dict[str, Any] = {}
    next_question: Optional[str] = None
    completion_status: Optional[str] = None

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint для обработки сообщений от WhatsApp
    """
    try:
        logger.info(f"Received message from {request.whatsapp_id}: {request.message}")
        
        # Обрабатываем сообщение через RAG с локальными документами
        rag_response = query(request.message)
        
        # Формируем ответ
        response = ChatResponse(
            response=rag_response,
            session_state="active",
            context_updates={},
            next_question=None,
            completion_status=None
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