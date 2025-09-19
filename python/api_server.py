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
        
        # 1. Обработка приветствий
        greetings = ['здравствуй', 'привет', 'добрый день', 'добрый вечер', 'доброе утро', 'здорово', 'hi', 'hello', 'хочу на консультацию', 'консультация']
        if any(greeting in request.message.lower() for greeting in greetings):
            updated_context = {"question_step": 1, "answers": []}
            greeting_response = "Здравствуйте! Я помогу вам разобраться с вопросами банкротства. Можете уточнить примерную сумму долга?"
            response = ChatResponse(
                response=greeting_response,
                session_state="collecting_info",
                context_updates=updated_context,
                next_question="Можете уточнить примерную сумму долга?",
                completion_status="collecting"
            )
            logger.info(f"Sending greeting response to {request.whatsapp_id}")
            return response

        # 2. Проверка на ИП в любом ответе
        if any(ip_word in request.message.lower() for ip_word in ['ип', 'индивидуальный предприниматель', 'ип статус', 'предприниматель']):
            ip_response = "К сожалению, если у вас есть статус ИП (индивидуального предпринимателя), банкротство как физическое лицо недоступно. Рекомендую обратиться к адвокату Мухтарову Торехану для консультации по вашим вариантам."
            response = ChatResponse(
                response=ip_response,
                session_state="answered",
                context_updates=request.context,
                next_question=None,
                completion_status="complete"
            )
            logger.info(f"IP status detected for {request.whatsapp_id}")
            return response

        # 3. Последовательный сбор ответов
        updated_context = request.context.copy()
        current_step = updated_context.get('question_step', 1)
        answers = updated_context.get('answers', [])

        # Сохраняем ответ пользователя
        if current_step > 1:  # Не сохраняем приветствие
            answers.append(request.message)
            updated_context['answers'] = answers

        # Определяем следующий вопрос
        questions = [
            "Можете уточнить примерную сумму долга?",
            "Как давно не платите по долгам? Сколько месяцев?",
            "Расскажите о вашей работе и доходах.",
            "Есть ли у вас недвижимость или имущество?"
        ]

        if current_step <= 4:
            # Задаем следующий вопрос
            next_question = questions[current_step - 1]
            updated_context['question_step'] = current_step + 1

            response = ChatResponse(
                response=next_question,
                session_state="collecting_info",
                context_updates=updated_context,
                next_question=next_question,
                completion_status="collecting"
            )
            logger.info(f"Asking question {current_step} to {request.whatsapp_id}")
            return response

        # 4. Все вопросы заданы - анализируем ответы через RAG
        if len(answers) >= 4:
            # Формируем запрос с полными ответами клиента для RAG системы
            client_data = f"""
Консультация по банкротству для клиента.

ОТВЕТЫ КЛИЕНТА НА ВОПРОСЫ:
1. Сумма долга: {answers[0]}
2. Срок просрочки: {answers[1]}
3. Работа и доходы: {answers[2]}
4. Недвижимость и имущество: {answers[3]}

Проанализируй ответы клиента, определи подходящий тип банкротства и создай развернутую консультацию согласно документации.
"""

            # Получаем полный ответ из RAG системы с анализом документов
            rag_response = query(client_data)
            
            response = ChatResponse(
                response=rag_response,
                session_state="answered",
                context_updates=updated_context,
                next_question=None,
                completion_status="complete"
            )
            return response

        # Если что-то пошло не так
        error_response = ChatResponse(
            response="Произошла ошибка в обработке запроса. Попробуйте начать сначала.",
            session_state="error",
            context_updates={},
            next_question=None,
            completion_status="error"
        )
        return error_response
        
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