from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
from query import process_query

app = FastAPI(title="Simple RAG API for WhatsApp Bot")

class SimpleRequest(BaseModel):
    message: str

class SimpleResponse(BaseModel):
    response: str

class ChatRequest(BaseModel):
    whatsapp_id: str
    message: str
    context: Optional[Dict[str, Any]] = {}
    session_state: Optional[str] = "initial"

class ChatResponse(BaseModel):
    response: str
    session_state: str = "answered"
    context_updates: Dict[str, Any] = {}
    questions: list = []
    offer_products: bool = False
    product_links: Dict[str, str] = {}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Простой endpoint для обработки сообщений через RAG
    """
    try:
        # Обрабатываем запрос через существующую систему RAG
        rag_response = process_query(request.message)
        
        # Возвращаем ответ
        return ChatResponse(
            response=rag_response,
            session_state="answered",
            context_updates={},
            questions=[],
            offer_products=False,
            product_links={}
        )
        
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/simple_chat", response_model=SimpleResponse)
async def simple_chat(request: SimpleRequest):
    """
    Упрощенный endpoint для тестирования
    """
    try:
        response = process_query(request.message)
        return SimpleResponse(response=response)
    except Exception as e:
        print(f"Error: {str(e)}")
        return SimpleResponse(response="Извините, произошла ошибка при обработке вашего запроса.")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Simple RAG API"}

@app.get("/")
async def root():
    return {"message": "Simple RAG API for WhatsApp Bankruptcy Bot"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)