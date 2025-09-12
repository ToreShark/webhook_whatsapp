from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
from langchain_openai import ChatOpenAI
from data_extractor import DataExtractor
from question_prioritizer import QuestionPrioritizer
from query import process_query, init_vectorstore
import os

app = FastAPI(title="Interactive RAG API for WhatsApp Bot")

# Initialize components
llm = None
data_extractor = None
question_prioritizer = None

def init_components():
    """Initialize LLM and other components"""
    global llm, data_extractor, question_prioritizer
    if llm is None:
        llm = ChatOpenAI()
        data_extractor = DataExtractor(llm)
        question_prioritizer = QuestionPrioritizer()
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
                # Формируем ответ с благодарностью за предоставленную информацию
                response_parts = []
                
                # Благодарим за новую информацию если что-то было извлечено
                extracted_data = extraction_result.get("extracted_data", {})
                new_info = [k for k, v in extracted_data.items() if v is not None]
                
                if new_info:
                    response_parts.append("Спасибо за информацию!")
                
                # Добавляем следующий вопрос
                response_parts.append(next_question_data["question"])
                
                response = " ".join(response_parts)
                
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
            "prioritizer_initialized": question_prioritizer is not None
        }
    }

@app.get("/")
async def root():
    return {"message": "Interactive RAG API for WhatsApp Bankruptcy Bot with Smart Dialogue"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)