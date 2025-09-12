from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
from langchain_openai import ChatOpenAI
from data_extractor import DataExtractor
from question_prioritizer import QuestionPrioritizer
from dialogue_generator import DialogueGenerator
from query import process_query, init_vectorstore
import os

app = FastAPI(title="Interactive RAG API for WhatsApp Bot")

# Initialize components
llm = None
data_extractor = None
question_prioritizer = None
dialogue_generator = None

def init_components():
    """Initialize LLM and other components"""
    global llm, data_extractor, question_prioritizer, dialogue_generator
    if llm is None:
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)
        data_extractor = DataExtractor(llm)
        question_prioritizer = QuestionPrioritizer()
        dialogue_generator = DialogueGenerator(llm)
        init_vectorstore()

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
    next_question: Optional[str] = None
    completion_status: Dict[str, Any] = {}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Интерактивный endpoint для диалогового общения с пользователем
    """
    try:
        init_components()
        
        user_message = request.message
        existing_context = request.context or {}
        session_state = request.session_state
        
        # 1. Извлекаем данные из сообщения пользователя
        extraction_result = data_extractor.extract_data(user_message, existing_context)
        
        # 2. Обновляем контекст новыми данными
        updated_context = data_extractor.merge_context(
            existing_context, 
            extraction_result
        )
        
        # 3. Определяем намерение пользователя
        user_intent = extraction_result.get("intent", "eligibility_check")
        updated_context["userIntent"] = user_intent
        
        # 4. Проверяем достаточность информации
        completion_status = question_prioritizer.analyze_completion_status(
            updated_context, 
            user_intent
        )
        
        # Проверяем, не является ли это follow-up вопросом после ответа
        if session_state == "answered" and _is_followup_question(user_message):
            # Пользователь спрашивает "что дальше" после получения ответа
            followup_response = _handle_followup_question(user_message, updated_context)
            
            return ChatResponse(
                response=followup_response["response"],
                session_state="offering_product",
                context_updates=updated_context,
                completion_status={"has_sufficient_info": True, "offering_products": True}
            )
        
        if completion_status["has_sufficient_info"]:
            # У нас достаточно информации - генерируем финальный ответ
            
            # Создаем контекстуальный запрос для RAG
            context_query = f"""
            Пользователь с намерением '{user_intent}' имеет следующую ситуацию:
            - Сумма долга: {updated_context.get('debtAmount', 'не указана')}
            - Просрочка более 12 месяцев: {updated_context.get('hasOverdue12Months', 'не указана')}
            - Ежемесячный доход: {updated_context.get('monthlyIncome', 'не указан')}
            - Тип занятости: {updated_context.get('employmentType', 'не указан')}
            - Недвижимость: {updated_context.get('hasProperty', 'не указана')}
            - Автомобиль: {updated_context.get('hasCar', 'не указан')}
            - Залоговое имущество: {updated_context.get('hasCollateral', 'не указано')}
            
            Исходный вопрос: {user_message}
            """
            
            rag_response = process_query(context_query)
            
            return ChatResponse(
                response=rag_response,
                session_state="answered",
                context_updates=updated_context,
                completion_status=completion_status
            )
        
        else:
            # Нужно задать следующий вопрос
            next_question_data = question_prioritizer.get_next_question(
                updated_context, 
                user_intent
            )
            
            if next_question_data:
                # Проверяем, нужно ли приветствие для первого контакта
                if dialogue_generator.should_use_greeting(session_state, existing_context):
                    # Первый контакт - генерируем приветствие с первым вопросом
                    response = dialogue_generator.generate_greeting(
                        user_message, 
                        next_question_data["question"]
                    )
                else:
                    # Обычный переход - генерируем естественный переход
                    extracted_data = extraction_result.get("extracted_data", {})
                    new_extracted = {k: v for k, v in extracted_data.items() if v is not None}
                    
                    response = dialogue_generator.generate_transition(
                        user_message,
                        new_extracted, 
                        next_question_data["question"]
                    )
                
                return ChatResponse(
                    response=response,
                    session_state="collecting_info",
                    context_updates=updated_context,
                    next_question=next_question_data["question"],
                    completion_status=completion_status
                )
            
            else:
                # Если вопросов больше нет, но информации недостаточно
                return ChatResponse(
                    response="Спасибо за предоставленную информацию! Позвольте мне проанализировать вашу ситуацию...",
                    session_state="answered",
                    context_updates=updated_context,
                    completion_status=completion_status
                )
        
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        return ChatResponse(
            response="Извините, произошла ошибка при обработке вашего сообщения. Попробуйте еще раз.",
            session_state="initial",
            context_updates={},
            completion_status={"has_sufficient_info": False, "error": str(e)}
        )

@app.post("/simple_chat", response_model=SimpleResponse)
async def simple_chat(request: SimpleRequest):
    """
    Упрощенный endpoint для тестирования RAG без диалога
    """
    try:
        init_components()
        response = process_query(request.message)
        return SimpleResponse(response=response)
    except Exception as e:
        print(f"Error: {str(e)}")
        return SimpleResponse(response="Извините, произошла ошибка при обработке вашего запроса.")

@app.post("/extract_data")
async def extract_data_endpoint(request: ChatRequest):
    """
    Endpoint для тестирования извлечения данных
    """
    try:
        init_components()
        
        extraction_result = data_extractor.extract_data(
            request.message, 
            request.context
        )
        
        return {
            "extraction_result": extraction_result,
            "merged_context": data_extractor.merge_context(
                request.context, 
                extraction_result
            )
        }
    except Exception as e:
        print(f"Error in extract_data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/next_question")
async def next_question_endpoint(request: ChatRequest):
    """
    Endpoint для тестирования приоритизации вопросов
    """
    try:
        init_components()
        
        user_intent = request.context.get("userIntent", "eligibility_check")
        
        next_question = question_prioritizer.get_next_question(
            request.context, 
            user_intent
        )
        
        completion_status = question_prioritizer.analyze_completion_status(
            request.context,
            user_intent
        )
        
        return {
            "next_question": next_question,
            "completion_status": completion_status,
            "user_intent": user_intent
        }
    except Exception as e:
        print(f"Error in next_question: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "Interactive RAG API",
        "components": {
            "llm_initialized": llm is not None,
            "extractor_initialized": data_extractor is not None,
            "prioritizer_initialized": question_prioritizer is not None,
            "dialogue_generator_initialized": dialogue_generator is not None
        }
    }

@app.get("/")
async def root():
    return {"message": "Interactive RAG API for WhatsApp Bankruptcy Bot with Smart Dialogue"}

def _is_followup_question(message: str) -> bool:
    """Определяет, является ли сообщение follow-up вопросом после ответа"""
    message_lower = message.lower()
    
    followup_patterns = [
        "что дальше", "что потом", "что после", "после банкротства",
        "что делать дальше", "что делать потом", "что делать после",
        "следующий шаг", "дальнейшие действия", "план действий",
        "куда обращаться", "где получить помощь", "нужна консультация",
        "хочу консультацию", "помогите", "посоветуйте"
    ]
    
    return any(pattern in message_lower for pattern in followup_patterns)

def _handle_followup_question(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Обрабатывает follow-up вопросы и предлагает продукты/услуги"""
    message_lower = message.lower()
    
    # Анализируем контекст пользователя для персонализированного предложения
    debt_amount = context.get('debtAmount', 0)
    employment_type = context.get('employmentType', '')
    has_property = context.get('hasProperty', False)
    
    response_parts = []
    
    if any(word in message_lower for word in ["что дальше", "что потом", "план действий"]):
        response_parts.append("Теперь, когда вы понимаете свою ситуацию с банкротством, рекомендую следующие шаги:")
        
        if debt_amount and debt_amount > 1000000:  # Более 1 млн
            response_parts.append("\n🎯 Учитывая значительную сумму долга, важно действовать по четкому плану.")
        
        response_parts.append("\n📋 Рекомендованный план действий:")
        response_parts.append("1️⃣ Получите персональную консультацию юриста")
        response_parts.append("2️⃣ Изучите процедуру банкротства подробнее") 
        response_parts.append("3️⃣ Подготовьте необходимые документы")
        
    elif any(word in message_lower for word in ["консультация", "помощь", "посоветуйте"]):
        response_parts.append("Я готов помочь вам с дальнейшими шагами!")
        response_parts.append("\n📞 Для персонального плана действий рекомендую:")
        
    else:
        response_parts.append("Отлично! Теперь можно переходить к практическим шагам.")
    
    # Добавляем предложение услуг
    response_parts.append("\n" + "="*40)
    response_parts.append("🎁 СПЕЦИАЛЬНЫЕ ПРЕДЛОЖЕНИЯ:")
    response_parts.append("")
    response_parts.append("✅ БЕСПЛАТНАЯ консультация")
    response_parts.append("   → Персональный разбор вашей ситуации")
    response_parts.append("   → План действий на 30 дней")
    response_parts.append("")
    response_parts.append("📚 Полный курс по банкротству")
    response_parts.append("   → Пошаговые инструкции")
    response_parts.append("   → Образцы документов") 
    response_parts.append("   → Поддержка экспертов")
    response_parts.append("")
    response_parts.append("📖 Учебник по банкротству в Казахстане")
    response_parts.append("   → Все законы и процедуры")
    response_parts.append("   → Реальные кейсы")
    response_parts.append("   → Актуальная информация 2024")
    
    return {
        "response": "".join(response_parts),
        "offer_products": True
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)