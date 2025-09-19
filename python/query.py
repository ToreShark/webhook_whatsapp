
import os
from dotenv import load_dotenv
from operator import itemgetter
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from utils import format_qa_pair, format_qa_pairs
import json
import re

from colorama import Fore
import warnings

warnings.filterwarnings("ignore")

load_dotenv()

# LLM
llm = ChatOpenAI()

# Load documents from local docs folder
docs_path = "docs"
loader = DirectoryLoader(
    docs_path,
    glob="*.txt",
    loader_cls=TextLoader,
    loader_kwargs={'encoding': 'utf-8'}
)
docs = loader.load()

print(f"{Fore.GREEN}Loaded {len(docs)} documents from {docs_path}{Fore.RESET}")

# Split
text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=300, 
    chunk_overlap=50)
splits = text_splitter.split_documents(docs)

# Index and load embeddings
vectorstore = Chroma.from_documents(documents=splits, 
                                    embedding=OpenAIEmbeddings())

# Create the vector store
retriever = vectorstore.as_retriever()

# CHAT LOGIC SYSTEM

def process_chat_message(whatsapp_id, message, context):
    """Обрабатывает сообщение от пользователя и возвращает ответ"""

    print(f"{Fore.CYAN}=== PROCESSING MESSAGE FROM {whatsapp_id} ==={Fore.RESET}")
    print(f"{Fore.YELLOW}Message: {message}{Fore.RESET}")
    print(f"{Fore.YELLOW}Context: {context}{Fore.RESET}")

    # 1. Обработка приветствий
    greetings = ['здравствуй', 'привет', 'добрый день', 'добрый вечер', 'доброе утро', 'здорово', 'hi', 'hello', 'хочу на консультацию', 'консультация']
    if any(greeting in message.lower() for greeting in greetings):
        updated_context = {"question_step": 2, "answers": []}  # Следующий шаг будет 2
        greeting_response = "Здравствуйте! Я помогу вам разобраться с вопросами банкротства. Можете уточнить примерную сумму долга?"
        return {
            "response": greeting_response,
            "session_state": "collecting_info",
            "context_updates": updated_context,
            "next_question": "Можете уточнить примерную сумму долга?",
            "completion_status": "collecting"
        }

    # 2. Проверка на ИП в любом ответе
    if any(ip_word in message.lower() for ip_word in ['ип', 'индивидуальный предприниматель', 'ип статус', 'предприниматель']):
        ip_response = "К сожалению, если у вас есть статус ИП (индивидуального предпринимателя), банкротство как физическое лицо недоступно. Рекомендую обратиться к адвокату Мухтарову Торехану для консультации по вашим вариантам."
        return {
            "response": ip_response,
            "session_state": "answered",
            "context_updates": context,
            "next_question": None,
            "completion_status": "complete"
        }

    # 3. Последовательный сбор ответов
    updated_context = context.copy()
    current_step = updated_context.get('question_step', 1)
    answers = updated_context.get('answers', [])

    # Сохраняем ответ пользователя (кроме первого раза)
    if current_step >= 2:  # Сохраняем ответы начиная со 2-го шага
        answers.append(message)
        updated_context['answers'] = answers

    # Определяем следующий вопрос
    questions = [
        "Можете уточнить примерную сумму долга?",
        "Как давно не платите по долгам? Сколько месяцев?",
        "Расскажите о вашей работе и доходах.",
        "Есть ли у вас недвижимость или имущество?"
    ]

    if current_step >= 2 and current_step <= 5:  # Шаги 2,3,4,5 для вопросов 2,3,4
        # Задаем следующий вопрос
        next_question = questions[current_step - 2]  # Индекс массива: 0,1,2,3
        updated_context['question_step'] = current_step + 1

        return {
            "response": next_question,
            "session_state": "collecting_info",
            "context_updates": updated_context,
            "next_question": next_question,
            "completion_status": "collecting"
        }

    # 4. Все вопросы заданы - анализируем через LLM, потом RAG
    if len(answers) >= 4:
        # ЭТАП 1: LLM анализирует ответы пользователя
        analyzed_data = analyze_client_answers(answers)

        if analyzed_data and analyzed_data.get('special_status') == 'IP':
            # Если обнаружен ИП статус - блокируем банкротство
            ip_response = "К сожалению, если у вас есть статус ИП (индивидуального предпринимателя), банкротство как физическое лицо недоступно. Рекомендую обратиться к адвокату Мухтарову Торехану для консультации по вашим вариантам."
            return {
                "response": ip_response,
                "session_state": "answered",
                "context_updates": updated_context,
                "next_question": None,
                "completion_status": "complete"
            }

        # ЭТАП 2: Формируем структурированный запрос для RAG
        if analyzed_data:
            client_data = f"""
КОНСУЛЬТАЦИЯ ПО БАНКРОТСТВУ - СТРУКТУРИРОВАННЫЕ ДАННЫЕ:

ПРОАНАЛИЗИРОВАННЫЕ ПАРАМЕТРЫ КЛИЕНТА:
- Сумма долга: {analyzed_data.get('debt_amount', 0)} тенге
- Срок просрочки: {analyzed_data.get('overdue_months', 'не указан')} месяцев
- Наличие дохода: {'есть' if analyzed_data.get('has_income') else 'нет'}
- Наличие имущества: {'есть' if analyzed_data.get('has_property') else 'нет'}

АНАЛИЗ LLM: {analyzed_data.get('analysis', 'анализ недоступен')}

ОРИГИНАЛЬНЫЕ ОТВЕТЫ КЛИЕНТА:
1. Сумма долга: {answers[0]}
2. Срок просрочки: {answers[1]}
3. Работа и доходы: {answers[2]}
4. Недвижимость и имущество: {answers[3]}

Определи правильный тип банкротства и создай развернутую консультацию согласно документации.
"""
        else:
            # Если анализ не удался, используем сырые данные
            client_data = f"""
КОНСУЛЬТАЦИЯ ПО БАНКРОТСТВУ:

ОТВЕТЫ КЛИЕНТА:
1. Сумма долга: {answers[0]}
2. Срок просрочки: {answers[1]}
3. Работа и доходы: {answers[2]}
4. Недвижимость и имущество: {answers[3]}

Проанализируй ответы клиента, определи подходящий тип банкротства и создай развернутую консультацию согласно документации.
"""

        # ЭТАП 3: Получаем полный ответ из RAG системы
        rag_response = query(client_data)

        return {
            "response": rag_response,
            "session_state": "answered",
            "context_updates": updated_context,
            "next_question": None,
            "completion_status": "complete"
        }

    # Если что-то пошло не так
    return {
        "response": "Произошла ошибка в обработке запроса. Попробуйте начать сначала.",
        "session_state": "error",
        "context_updates": {},
        "next_question": None,
        "completion_status": "error"
    }


def analyze_client_answers(answers):
    """Анализирует ответы клиента по ключевым параметрам перед RAG"""

    analysis_prompt = ChatPromptTemplate.from_template("""
Проанализируй ответы клиента и извлеки ключевые параметры для банкротства.

ОТВЕТЫ КЛИЕНТА:
1. Сумма долга: {answer1}
2. Срок просрочки: {answer2}
3. Работа и доходы: {answer3}
4. Недвижимость и имущество: {answer4}

ЗАДАЧА: Извлеки и структурируй информацию по ключевым параметрам.

КЛЮЧЕВЫЕ ПРОВЕРКИ:
- Сумма долга: Извлеки точную сумму в тенге (ищи числа + "млн", "тысяч", "тенге")
- Имущество: Проверь упоминания - дарственная, договор дарения, квартира, дом, недвижимость = ЕСТЬ ИМУЩЕСТВО
- Доходы: ИП, предприниматель, самозанятый = ОСОБЫЙ СТАТУС
- Просрочка: Извлеки количество месяцев

ВЕРНИ ТОЛЬКО JSON:
{{
  "debt_amount": число_в_тенге,
  "overdue_months": число_месяцев,
  "has_property": true/false,
  "has_income": true/false,
  "special_status": "IP" если упомянут ИП или null,
  "analysis": "краткое обоснование решений"
}}

ПРИМЕРЫ:
- "6 780 000 тенге" → debt_amount: 6780000
- "дарственную оставили" → has_property: true
- "не работаю пока" → has_income: false
- "есть ИП" → special_status: "IP"
""")

    try:
        analysis_chain = analysis_prompt | llm | StrOutputParser()
        result = analysis_chain.invoke({
            "answer1": answers[0],
            "answer2": answers[1],
            "answer3": answers[2],
            "answer4": answers[3]
        })

        # Парсим JSON
        try:
            analyzed_data = json.loads(result)
            print(f"{Fore.MAGENTA}=== LLM ANALYSIS RESULT ==={Fore.RESET}")
            print(f"{Fore.WHITE}{analyzed_data}{Fore.RESET}")
            return analyzed_data
        except:
            # Если не JSON, ищем JSON в тексте
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                analyzed_data = json.loads(json_match.group())
                print(f"{Fore.MAGENTA}=== LLM ANALYSIS RESULT (EXTRACTED) ==={Fore.RESET}")
                print(f"{Fore.WHITE}{analyzed_data}{Fore.RESET}")
                return analyzed_data
            else:
                print(f"{Fore.RED}Failed to parse LLM analysis: {result}{Fore.RESET}")
                return None

    except Exception as e:
        print(f"{Fore.RED}Error in LLM analysis: {e}{Fore.RESET}")
        return None


# 1. DECOMPOSITION - COMMENTED OUT
# template = """You are a helpful assistant trained to generates multiple sub-questions related to an input question. \n
# The goal is to break down the input into a set of sub-problems / sub-questions that can be answered in isolation. \n
# Generate multiple search queries related to: {question} \n
# Output (3 queries):"""
# prompt_decomposition = ChatPromptTemplate.from_template(template)


def generate_sub_questions(query):
    """ generate sub questions based on user query"""
    # Commented out auto-generation of subquestions
    # pass 
    # # Chain
    # generate_queries_decomposition = (
    #     prompt_decomposition 
    #     | llm 
    #     | StrOutputParser()
    #     | (lambda x: x.split("\n"))
    # ) 

    # # Run
    # sub_questions = generate_queries_decomposition.invoke({"question": query})
    # questions_str = "\n".join(sub_questions)
    # print(Fore.MAGENTA + "=====  SUBQUESTIONS: =====" + Fore.RESET)
    # print(Fore.WHITE + questions_str + Fore.RESET + "\n")
    # return sub_questions
    
    # Return the original query as a single question without decomposition
    return [query] 
      

# 2. ANSWER SUBQUESTIONS RECURSIVELY 
template = """Here is the question you need to answer:

\n --- \n {sub_question} \n --- \n

Here is any available background question + answer pairs:

\n --- \n {q_a_pairs} \n --- \n

Here is additional context relevant to the question: 

\n --- \n {context} \n --- \n

Use the above context and any background question + answer pairs to answer the question: \n {sub_question}
"""
prompt_qa = ChatPromptTemplate.from_template(template)


def generate_qa_pairs(sub_questions):
    """ ask the LLM to generate a pair of question and answer based on the original user query """
    q_a_pairs = ""

    for sub_question in sub_questions:
        # chain
        generate_qa = (
            {"context": itemgetter("sub_question") | retriever, "sub_question": itemgetter("sub_question"), "q_a_pairs": itemgetter("q_a_pairs")}
            | prompt_qa 
            | llm 
            | StrOutputParser()
        )
        answer = generate_qa.invoke({"sub_question": sub_question, "q_a_pairs": q_a_pairs})
        q_a_pair = format_qa_pair(sub_question, answer)
        q_a_pairs = q_a_pairs + "\n --- \n" + q_a_pair 
        

# 3. ANSWER INDIVIDUALY

# RAG prompt - local version in Russian
prompt_rag = ChatPromptTemplate.from_template("""Ты эксперт-консультант по банкротству в Казахстане. Используй предоставленный контекст для ответа на вопрос пользователя. Если не знаешь ответ, просто скажи, что не знаешь. Отвечай на русском языке четко и по делу.

ВАЖНО: Вместо фраз "обратитесь к специалисту" всегда рекомендуй "обратиться к адвокату Мухтарову Торехану".

Вопрос: {question}
Контекст: {context}
Ответ:""")


def retrieve_and_rag(prompt_rag, sub_questions):
    """RAG on each sub-question"""
    rag_results = []
    for sub_question in sub_questions:
        retrieved_docs = retriever.get_relevant_documents(sub_question)

        answer_chain = (
            prompt_rag
            | llm
            | StrOutputParser()
        )
        answer = answer_chain.invoke({"question": sub_question, "context": retrieved_docs})
        rag_results.append(answer)
    
    return rag_results, sub_questions
    
# SUMMARIZE AND ANSWER 

# Prompt for final answer synthesis
template = """Используй следующие пары вопрос-ответ для создания итогового ответа на русском языке:

{context}

На основе этой информации ответь на вопрос: {question}

Отвечай как эксперт по банкротству в Казахстане на русском языке.

ВАЖНО: Вместо общих фраз "обратитесь к специалисту" или "обратитесь к юристу" ВСЕГДА рекомендуй конкретно: "Рекомендую обратиться к адвокату Мухтарову Торехану для профессиональной консультации по вашей ситуации"."""

prompt = ChatPromptTemplate.from_template(template)


# Query
def query(user_query):
    print(f"{Fore.CYAN}=== QUERY FUNCTION CALLED ==={Fore.RESET}")
    print(f"{Fore.YELLOW}User query: {user_query[:200]}...{Fore.RESET}")

    # generate optimized answer for a given query using the improved subqueries
    sub_questions = generate_sub_questions(user_query)
    generate_qa_pairs(sub_questions)
    answers, questions = retrieve_and_rag(prompt_rag, sub_questions)
    context = format_qa_pairs(questions, answers)

    print(f"{Fore.GREEN}Retrieved context length: {len(context)} chars{Fore.RESET}")
    print(f"{Fore.GREEN}Context preview: {context[:300]}...{Fore.RESET}")

    final_rag_chain = (
        prompt
        | llm
        | StrOutputParser()
    )

    result = final_rag_chain.invoke({"question": user_query, "context": context})
    print(f"{Fore.CYAN}=== QUERY RESULT GENERATED ==={Fore.RESET}")
    return result

    
