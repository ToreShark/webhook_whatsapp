from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from typing import Dict, Any

class DialogueGenerator:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.greeting_prompt = self._create_greeting_prompt()
        self.transition_prompt = self._create_transition_prompt()
    
    def _create_greeting_prompt(self):
        """Промпт для генерации приветствия при первом контакте"""
        template = """Ты опытный юрист-консультант по банкротству в Казахстане. 
К тебе обратился клиент с первым сообщением: "{user_message}"

Твоя задача:
1. Поприветствовать клиента тепло и профессионально
2. Показать, что понимаешь его ситуацию и готов помочь
3. Объяснить, что для качественной консультации нужно задать несколько вопросов
4. Задать первый вопрос: "{first_question}"

Стиль: дружелюбный, профессиональный, эмпатичный
Длина: 2-3 предложения + вопрос
Тон: как живой консультант, а не робот

Отвечай только на русском языке."""

        return ChatPromptTemplate.from_template(template)
    
    def _create_transition_prompt(self):
        """Промпт для генерации естественных переходов между вопросами"""
        template = """Ты юрист-консультант по банкротству. Клиент ответил на твой вопрос: "{user_answer}"

Из ответа ты извлек информацию: {extracted_info}

Теперь нужно задать следующий вопрос: "{next_question}"

Твоя задача:
1. Кратко отреагировать на ответ клиента (показать, что услышал и понял)
2. Плавно перейти к следующему вопросу
3. Если нужно, добавить пояснение зачем этот вопрос важен

НЕ используй шаблонные фразы типа "Спасибо за информацию!"
Говори как живой человек, эмпатично и естественно.
Длина: 1-2 предложения + вопрос
Отвечай только на русском языке.

Примеры хорошего стиля:
- "Понятно, сумма серьезная. Теперь важно выяснить..."
- "Вижу ситуацию. Подскажите еще..."
- "Хорошо, это важная деталь. Теперь..."
"""

        return ChatPromptTemplate.from_template(template)
    
    def generate_greeting(self, user_message: str, first_question: str) -> str:
        """Генерирует приветствие для первого контакта"""
        try:
            greeting_chain = (
                self.greeting_prompt 
                | self.llm 
                | StrOutputParser()
            )
            
            return greeting_chain.invoke({
                "user_message": user_message,
                "first_question": first_question
            })
            
        except Exception as e:
            print(f"Error generating greeting: {str(e)}")
            # Fallback приветствие
            return f"Здравствуйте! Я помогу разобраться с вашей ситуацией по банкротству. Для качественной консультации мне нужно задать несколько вопросов. {first_question}"
    
    def generate_transition(
        self, 
        user_answer: str, 
        extracted_info: Dict[str, Any], 
        next_question: str
    ) -> str:
        """Генерирует естественный переход к следующему вопросу"""
        try:
            # Форматируем извлеченную информацию для промпта
            info_summary = []
            for key, value in extracted_info.items():
                if value is not None:
                    if key == "debtAmount":
                        info_summary.append(f"сумма долга: {value} тенге")
                    elif key == "hasOverdue12Months":
                        info_summary.append(f"просрочки больше 12 мес: {'да' if value else 'нет'}")
                    elif key == "monthlyIncome":
                        info_summary.append(f"доход: {value} тенге")
                    elif key == "employmentType":
                        type_map = {
                            "official": "официальное трудоустройство",
                            "unofficial": "неофициальное трудоустройство", 
                            "government": "государственная служба",
                            "retired": "пенсионер",
                            "unemployed": "безработная",
                            "self_employed": "ИП",
                            "maternity_leave": "в декретном отпуске"
                        }
                        info_summary.append(f"статус: {type_map.get(value, value)}")
            
            info_text = ", ".join(info_summary) if info_summary else "получил ваш ответ"
            
            transition_chain = (
                self.transition_prompt 
                | self.llm 
                | StrOutputParser()
            )
            
            return transition_chain.invoke({
                "user_answer": user_answer,
                "extracted_info": info_text,
                "next_question": next_question
            })
            
        except Exception as e:
            print(f"Error generating transition: {str(e)}")
            # Fallback переход
            return f"Понятно. {next_question}"
    
    def should_use_greeting(self, session_state: str, context: Dict[str, Any]) -> bool:
        """Определяет, нужно ли использовать приветствие"""
        return (
            session_state == "initial" and 
            not context.get("questionsAsked", []) and
            not context.get("answersReceived", {})
        )