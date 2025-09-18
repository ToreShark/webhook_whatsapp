from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
from query import query, extract_info_from_message, check_missing_info, generate_contextual_question, has_sufficient_info
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
        
        # 1. Извлекаем информацию из сообщения и обновляем контекст
        updated_context = extract_info_from_message(request.message, request.context)
        logger.info(f"Updated context: {updated_context}")
        
        # 2. Проверяем достаточно ли информации для финального ответа
        if has_sufficient_info(updated_context):
            # У нас есть вся необходимая информация - генерируем финальный ответ через RAG
            
            # Создаем контекстуальный запрос для RAG
            context_query = f"""
            ИТОГОВАЯ КОНСУЛЬТАЦИЯ по банкротству для клиента:
            - Сумма долга: {updated_context.get('debt_amount', 'не указана')} тенге
            - Срок просрочки: {updated_context.get('overdue_months', 'не указан')} месяцев
            - Официальный доход: {'есть' if updated_context.get('has_income') else 'нет' if updated_context.get('has_income') is False else 'не указан'}
            - Недвижимость: {'есть' if updated_context.get('has_property') else 'нет' if updated_context.get('has_property') is False else 'не указана'}
            - Автомобиль: {'есть' if updated_context.get('has_car') else 'нет' if updated_context.get('has_car') is False else 'не указан'}

            Создай финальный ответ по структуре из документации:
            1. Краткий анализ и рекомендуемая процедура банкротства
            2. Рекомендация записаться к адвокату Мухтарову Торехану с упоминанием кнопки
            3. Ссылки на учебные материалы
            4. Техническое уведомление о передаче данных и ограничениях бота

            НЕ используй общие фразы про "специалистов" - только конкретно адвоката Мухтарова Торехана.
            """
            
            rag_response = query(context_query)
            
            response = ChatResponse(
                response=rag_response,
                session_state="answered",
                context_updates=updated_context,
                next_question=None,
                completion_status="complete"
            )
        
        else:
            # Нужно задать уточняющий вопрос
            missing_info = check_missing_info(updated_context)
            next_question = generate_contextual_question(missing_info, updated_context)
            
            response = ChatResponse(
                response=next_question,
                session_state="collecting_info",
                context_updates=updated_context,
                next_question=next_question,
                completion_status="collecting"
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