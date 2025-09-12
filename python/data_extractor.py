import json
import re
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

class DataExtractor:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.extraction_prompt = self._create_extraction_prompt()
        
    def _create_extraction_prompt(self):
        """Создает промпт для извлечения данных из сообщений пользователя"""
        template = """Ты эксперт по анализу сообщений о банкротстве в Казахстане. 
Твоя задача - извлечь структурированные данные из сообщения пользователя.

ПРАВИЛА ИЗВЛЕЧЕНИЯ:

1. СУММЫ ДОЛГОВ:
   - "5 млн", "5 миллионов", "5000000" → 5000000
   - "200к", "200 тысяч", "200000" → 200000
   - "полтора миллиона", "1.5 млн" → 1500000

2. ПРОСРОЧКИ:
   - "не плачу год", "просрочка 12 месяцев" → hasOverdue12Months: true
   - "не плачу 6 месяцев", "просрочка 8 месяцев" → hasOverdue12Months: false
   - "просрочка полтора года" → hasOverdue12Months: true

3. ТРУДОУСТРОЙСТВО:
   - "работаю официально", "белая зарплата" → employmentType: "official"
   - "работаю неофициально", "серая зарплата" → employmentType: "unofficial"  
   - "госслужба", "работаю в госорганах" → employmentType: "government"
   - "пенсионер" → employmentType: "retired"
   - "безработный", "не работаю" → employmentType: "unemployed"
   - "ИП", "предприниматель" → employmentType: "self_employed"
   - "в декрете", "декретный отпуск", "сижу с ребенком", "в декрете с ребенком" → employmentType: "maternity_leave", monthlyIncome: 70000

4. ДОХОДЫ:
   - Извлекай числовые значения доходов
   - "зарплата 200 тысяч" → monthlyIncome: 200000
   - "доход нестабильный" → incomeStability: "unstable"

5. ИМУЩЕСТВО:
   - "есть квартира", "своя недвижимость" → hasProperty: true
   - "есть машина", "автомобиль в собственности" → hasCar: true
   - "ипотека" → hasCollateral: true, collateralType: "mortgage"
   - "автокредит" → hasCar: true, hasCollateral: true, collateralType: "auto_loan"

6. СПЕЦИАЛЬНЫЕ СИТУАЦИИ:
   - "коллекторы звонят" → hasCollectorPressure: true
   - "арестован счет", "заблокировали карту", "ЧСИ арестовал счета", "ЧСИ заблокировал" → hasAccountArrest: true  
   - "удерживают с зарплаты" → hasWageArrest: true
   - "отказ пришел", "отклонили заявление" → previousRejection: true

7. НАМЕРЕНИЯ (intentType):
   - Вопросы "подхожу ли", "могу ли" → "eligibility_check"
   - "как начать", "с чего начать" → "how_to_start"
   - "какие документы" → "documentation"
   - "что будет после", "последствия" → "consequences"
   - Конкретные проблемы → "specific_problem"

СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЯ: {user_message}

КОНТЕКСТ ПРЕДЫДУЩИХ ДАННЫХ: {existing_context}

Верни JSON в формате:
{{
  "extracted_data": {{
    "debtAmount": число_или_null,
    "hasOverdue12Months": true_false_или_null,
    "monthlyIncome": число_или_null,
    "employmentType": "строка_или_null",
    "incomeStability": "stable/unstable/null",
    "hasProperty": true_false_или_null,
    "hasCar": true_false_или_null,
    "hasCollateral": true_false_или_null,
    "collateralType": "строка_или_null",
    "hasCollectorPressure": true_false_или_null,
    "hasAccountArrest": true_false_или_null,
    "hasWageArrest": true_false_или_null,
    "previousRejection": true_false_или_null,
    "creditorsCount": число_или_null
  }},
  "intent": "eligibility_check/how_to_start/documentation/consequences/specific_problem",
  "confidence": {{
    "debtAmount": 0.0_to_1.0,
    "hasOverdue12Months": 0.0_to_1.0,
    "monthlyIncome": 0.0_to_1.0
  }},
  "missing_critical": ["список_недостающих_критичных_полей"],
  "user_situation": "краткое_описание_ситуации_пользователя"
}}

ВАЖНО: Возвращай ТОЛЬКО валидный JSON, без дополнительного текста!"""

        return ChatPromptTemplate.from_template(template)

    def extract_data(self, user_message: str, existing_context: Dict = None) -> Dict[str, Any]:
        """Извлекает данные из сообщения пользователя"""
        try:
            if existing_context is None:
                existing_context = {}

            # Создаем цепочку обработки
            extraction_chain = (
                self.extraction_prompt 
                | self.llm 
                | StrOutputParser()
            )

            # Выполняем извлечение
            result = extraction_chain.invoke({
                "user_message": user_message,
                "existing_context": json.dumps(existing_context, ensure_ascii=False, indent=2)
            })

            # Парсим JSON ответ
            try:
                extracted = json.loads(result)
                return extracted
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {e}")
                print(f"Raw result: {result}")
                return self._create_fallback_extraction(user_message)

        except Exception as e:
            print(f"Error in data extraction: {str(e)}")
            return self._create_fallback_extraction(user_message)

    def _create_fallback_extraction(self, user_message: str) -> Dict[str, Any]:
        """Резервная система извлечения через регулярные выражения"""
        extracted_data = {}
        
        # Простое извлечение сумм
        amount_patterns = [
            r'(\d+)\s*(?:млн|миллион)', 
            r'(\d+)\s*(?:к|тысяч)',
            r'(\d+)\s*(?:тенге)?'
        ]
        
        for pattern in amount_patterns:
            match = re.search(pattern, user_message.lower())
            if match:
                amount = int(match.group(1))
                if 'млн' in match.group(0) or 'миллион' in match.group(0):
                    amount *= 1000000
                elif 'к' in match.group(0) or 'тысяч' in match.group(0):
                    amount *= 1000
                extracted_data['debtAmount'] = amount
                break

        # Простой анализ намерений
        intent = "eligibility_check"
        if any(word in user_message.lower() for word in ['как начать', 'с чего начать']):
            intent = "how_to_start"
        elif any(word in user_message.lower() for word in ['документы', 'справки']):
            intent = "documentation"

        return {
            "extracted_data": extracted_data,
            "intent": intent,
            "confidence": {"debtAmount": 0.3},
            "missing_critical": ["hasOverdue12Months", "monthlyIncome"],
            "user_situation": "Fallback extraction used"
        }

    def merge_context(self, existing_context: Dict, new_extraction: Dict) -> Dict:
        """Объединяет существующий контекст с новыми данными"""
        merged = existing_context.copy()
        
        # Обновляем только те поля, которые были извлечены с достаточной уверенностью
        extracted = new_extraction.get('extracted_data', {})
        confidence = new_extraction.get('confidence', {})
        
        for key, value in extracted.items():
            if value is not None:
                # Обновляем если уверенность > 0.5 или поля еще нет
                conf = confidence.get(key, 0.8)
                if conf > 0.5 or key not in merged:
                    merged[key] = value
        
        return merged