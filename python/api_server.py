from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
from query import process_query
import json
import os

app = FastAPI(title="RAG API for WhatsApp Bot")

class ChatRequest(BaseModel):
    whatsapp_id: str
    message: str
    context: Optional[Dict[str, Any]] = {}
    session_state: Optional[str] = "initial"

class ChatResponse(BaseModel):
    response: str
    questions: Optional[List[str]] = []
    session_state: str
    context_updates: Dict[str, Any] = {}
    offer_products: bool = False
    product_links: Optional[Dict[str, str]] = {}

class QuestionTemplate:
    def __init__(self):
        self.templates = {
            "debt_amount": {
                "question": "Для точного ответа мне нужно уточнить: какая у вас общая сумма долга?",
                "key": "debtAmount",
                "validation": "number"
            },
            "income_amount": {
                "question": "Какой у вас ежемесячный доход?",
                "key": "incomeAmount", 
                "validation": "number"
            },
            "income_stability": {
                "question": "Ваш доход стабильный или нерегулярный?",
                "key": "incomeStable",
                "validation": "boolean"
            },
            "has_overdue": {
                "question": "У вас есть просрочки по кредитам более 12 месяцев?",
                "key": "hasOverdue12Months",
                "validation": "boolean"
            },
            "has_property": {
                "question": "У вас есть недвижимость или автомобиль в собственности?",
                "key": "hasProperty",
                "validation": "boolean"
            },
            "employment_type": {
                "question": "Вы официально трудоустроены или работаете неофициально?",
                "key": "employmentType",
                "validation": "string"
            }
        }
    
    def get_next_questions(self, context: Dict, user_message: str) -> List[str]:
        """Определяет какие вопросы задать на основе контекста"""
        questions = []
        answers = context.get('answersReceived', {})
        
        # Анализируем сообщение пользователя
        message_lower = user_message.lower()
        
        # Если пользователь упомянул работу/доход
        if any(word in message_lower for word in ['работа', 'доход', 'зарплата', 'официально']):
            if 'incomeAmount' not in answers:
                questions.append(self.templates['income_amount']['question'])
            if 'incomeStable' not in answers:
                questions.append(self.templates['income_stability']['question'])
        
        # Если упомянул долги/кредиты
        if any(word in message_lower for word in ['долг', 'кредит', 'займ', 'банкротство']):
            if 'debtAmount' not in answers:
                questions.append(self.templates['debt_amount']['question'])
            if 'hasOverdue12Months' not in answers:
                questions.append(self.templates['has_overdue']['question'])
        
        # Если спрашивает "что делать" или "как быть"
        if any(word in message_lower for word in ['что делать', 'как быть', 'помогите']):
            # Проверяем минимальный набор данных
            if 'debtAmount' not in answers:
                questions.append(self.templates['debt_amount']['question'])
            elif 'incomeAmount' not in answers:
                questions.append(self.templates['income_amount']['question'])
        
        return questions[:2]  # Максимум 2 вопроса за раз

question_templates = QuestionTemplate()

def should_offer_products(message: str, context: Dict) -> bool:
    """Определяет, нужно ли предложить продукты"""
    keywords = ['как', 'процедура', 'сколько времени', 'пошагово', 'инструкция', 'самостоятельно']
    return any(keyword in message.lower() for keyword in keywords)

def get_product_links(context: Dict) -> Dict[str, str]:
    """Возвращает ссылки на продукты"""
    return {
        "consultation": "https://your-site.kz/consultation",
        "course": "https://your-site.kz/bankruptcy-course", 
        "textbook": "https://your-site.kz/bankruptcy-textbook"
    }

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Получаем уточняющие вопросы
        questions = question_templates.get_next_questions(
            request.context, 
            request.message
        )
        
        # Если есть уточняющие вопросы и мы еще не собрали всю информацию
        if questions and request.session_state in ['initial', 'collecting_info']:
            return ChatResponse(
                response=questions[0],  # Задаем первый вопрос
                questions=questions,
                session_state='collecting_info',
                context_updates={'questionsAsked': questions},
                offer_products=False
            )
        
        # Если информации достаточно, обрабатываем через RAG
        rag_response = process_query(request.message)
        
        # Проверяем, нужно ли предложить продукты
        offer_products = should_offer_products(request.message, request.context)
        product_links = get_product_links(request.context) if offer_products else {}
        
        # Формируем ответ
        response_text = rag_response
        
        if offer_products:
            response_text += "\n\nДля более детальной консультации рекомендую:"
            response_text += "\n• Записаться на бесплатную консультацию с адвокатом Мухтаровым Тореханом"
            response_text += "\n• Приобрести пошаговый курс по банкротству"
            response_text += "\n• Изучить учебник по процедуре банкротства"
            response_text += "\n\nЧто вас интересует больше?"
        
        return ChatResponse(
            response=response_text,
            questions=[],
            session_state='offering_product' if offer_products else 'answered',
            context_updates={},
            offer_products=offer_products,
            product_links=product_links
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "RAG API"}

@app.get("/")
async def root():
    return {"message": "RAG API for WhatsApp Bankruptcy Bot"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)