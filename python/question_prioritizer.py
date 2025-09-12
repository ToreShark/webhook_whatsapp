from typing import Dict, Optional, List, Any

class QuestionPrioritizer:
    """Определяет следующий вопрос для пользователя на основе контекста и намерений"""
    
    def __init__(self):
        self.question_templates = {
            # Обязательные вопросы для принятия решения
            "debt_amount": {
                "question": "Какая у вас общая сумма задолженности?",
                "field": "debtAmount",
                "priority": 1,
                "required_for": ["eligibility_check", "how_to_start"]
            },
            "overdue_check": {
                "question": "Есть ли у вас просрочки по кредитам более 12 месяцев?",
                "field": "hasOverdue12Months", 
                "priority": 2,
                "required_for": ["eligibility_check", "how_to_start"]
            },
            "monthly_income": {
                "question": "Какой у вас ежемесячный доход?",
                "field": "monthlyIncome",
                "priority": 3,
                "required_for": ["eligibility_check"]
            },
            "employment_type": {
                "question": "Вы работаете официально или неофициально? (госслужба/частная компания/ИП/пенсионер)",
                "field": "employmentType", 
                "priority": 4,
                "required_for": ["eligibility_check", "how_to_start"]
            },
            
            # Уточняющие вопросы
            "property_check": {
                "question": "Есть ли у вас недвижимость в собственности (квартира, дом, доля)?",
                "field": "hasProperty",
                "priority": 5,
                "required_for": ["eligibility_check", "how_to_start"]
            },
            "car_check": {
                "question": "Есть ли у вас автомобиль в собственности?",
                "field": "hasCar",
                "priority": 6,
                "required_for": ["eligibility_check"]
            },
            "collateral_check": {
                "question": "Есть ли у вас залоговое имущество (ипотека, автокредит)?",
                "field": "hasCollateral",
                "priority": 7,
                "required_for": ["how_to_start"]
            },
            "creditors_count": {
                "question": "Сколько у вас кредиторов (банков, МФО)?",
                "field": "creditorsCount",
                "priority": 8,
                "required_for": ["how_to_start"]
            }
        }
        
        # Минимальные наборы полей для разных намерений
        self.required_fields = {
            "eligibility_check": ["debtAmount", "hasOverdue12Months", "monthlyIncome"],
            "how_to_start": ["debtAmount", "hasOverdue12Months", "employmentType", "hasProperty"],
            "documentation": ["employmentType"],
            "consequences": ["hasProperty", "hasCar"],
            "specific_problem": []  # Зависит от проблемы
        }

    def get_next_question(self, context: Dict[str, Any], intent: str) -> Optional[Dict[str, str]]:
        """
        Определяет следующий вопрос для пользователя
        
        Returns:
            Dict с вопросом или None если достаточно информации
        """
        
        # Получаем недостающие критичные поля
        missing_fields = self._get_missing_critical_fields(context, intent)
        
        if not missing_fields:
            return None  # Достаточно информации
        
        # Находим вопрос с наивысшим приоритетом среди недостающих
        best_question = None
        best_priority = float('inf')
        
        for question_key, question_data in self.question_templates.items():
            field = question_data["field"]
            priority = question_data["priority"]
            required_for = question_data.get("required_for", [])
            
            # Проверяем что поле отсутствует и нужно для этого намерения
            if (field in missing_fields and 
                (not required_for or intent in required_for) and
                priority < best_priority):
                
                best_question = question_data
                best_priority = priority
        
        return best_question

    def _get_missing_critical_fields(self, context: Dict[str, Any], intent: str) -> List[str]:
        """Возвращает список критично недостающих полей для данного намерения"""
        
        required = self.required_fields.get(intent, [])
        missing = []
        
        for field in required:
            if field not in context or context[field] is None:
                missing.append(field)
        
        return missing

    def has_sufficient_info(self, context: Dict[str, Any], intent: str) -> bool:
        """Проверяет, достаточно ли информации для ответа"""
        missing = self._get_missing_critical_fields(context, intent)
        return len(missing) == 0

    def get_priority_by_intent(self, intent: str, user_message: str) -> List[str]:
        """
        Возвращает приоритетный порядок вопросов для данного намерения
        с учетом содержания сообщения пользователя
        """
        
        # Базовый приоритет по намерению
        base_priority = {
            "eligibility_check": ["debtAmount", "hasOverdue12Months", "monthlyIncome", "employmentType"],
            "how_to_start": ["debtAmount", "hasOverdue12Months", "employmentType", "hasProperty"],
            "documentation": ["employmentType", "hasProperty", "hasCollateral"],
            "consequences": ["hasProperty", "hasCar", "monthlyIncome"],
            "specific_problem": ["debtAmount", "hasOverdue12Months"]
        }
        
        priority_list = base_priority.get(intent, ["debtAmount", "hasOverdue12Months"])
        
        # Умная корректировка на основе содержания сообщения
        message_lower = user_message.lower()
        
        # Если упоминает доходы - поднимаем приоритет доходов
        if any(word in message_lower for word in ['зарплата', 'доход', 'работа', 'пенсия']):
            if "monthlyIncome" in priority_list:
                priority_list.remove("monthlyIncome")
                priority_list.insert(1, "monthlyIncome")
            if "employmentType" in priority_list:
                priority_list.remove("employmentType") 
                priority_list.insert(0, "employmentType")
        
        # Если упоминает имущество - поднимаем приоритет имущества
        if any(word in message_lower for word in ['квартира', 'дом', 'машина', 'недвижимость']):
            for field in ["hasProperty", "hasCar"]:
                if field in priority_list:
                    priority_list.remove(field)
                    priority_list.insert(1, field)
        
        # Если упоминает просрочки/коллекторы - поднимаем приоритет просрочек
        if any(word in message_lower for word in ['просрочка', 'коллектор', 'не плачу', 'задержка']):
            if "hasOverdue12Months" in priority_list:
                priority_list.remove("hasOverdue12Months")
                priority_list.insert(0, "hasOverdue12Months")
        
        return priority_list

    def analyze_completion_status(self, context: Dict[str, Any], intent: str) -> Dict[str, Any]:
        """
        Анализирует статус сбора информации
        
        Returns:
            Dict с информацией о готовности к ответу
        """
        
        missing_critical = self._get_missing_critical_fields(context, intent)
        has_sufficient = len(missing_critical) == 0
        
        # Считаем процент заполненности
        required = self.required_fields.get(intent, [])
        filled = len(required) - len(missing_critical)
        completion_percentage = (filled / len(required)) * 100 if required else 100
        
        return {
            "has_sufficient_info": has_sufficient,
            "missing_critical": missing_critical,
            "completion_percentage": completion_percentage,
            "required_total": len(required),
            "filled_count": filled,
            "next_phase": "complete" if has_sufficient else "collecting"
        }

    def should_ask_followup_questions(self, context: Dict[str, Any], intent: str) -> bool:
        """Определяет, нужны ли дополнительные уточняющие вопросы"""
        
        # Если это проверка подходящости и есть особые ситуации
        if intent == "eligibility_check":
            debt_amount = context.get("debtAmount", 0)
            
            # Для больших долгов спрашиваем про имущество
            if debt_amount and debt_amount > 10000000:  # > 10 млн
                if context.get("hasProperty") is None:
                    return True
            
            # Если госслужащий - важно знать про арест зарплаты
            if context.get("employmentType") == "government":
                if context.get("hasWageArrest") is None:
                    return True
        
        return False