
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

# INFORMATION EXTRACTION SYSTEM

def extract_info_from_message(message, existing_context=None):
    """Извлекает структурированную информацию из сообщения пользователя"""
    if existing_context is None:
        existing_context = {}
    
    extraction_prompt = ChatPromptTemplate.from_template("""
Извлеки из сообщения пользователя следующую информацию о банкротстве (если есть):

ВАЖНО: Возвращай только JSON без дополнительного текста.

Ищи в сообщении:
- debt_amount: сумма долга в тенге (число без текста, например 5000000)
- overdue_months: срок просрочки в месяцах (число)
- has_income: есть ли официальный доход (true/false/null если не указано)
- has_property: есть ли недвижимость, квартира, дом (true/false/null)
- has_car: есть ли машина, автомобиль (true/false/null)
- employment_type: тип занятости (pension/government/unemployed/self_employed/null)
- intent: что хочет пользователь (bankruptcy_check/procedure_info/consultation/null)

Примеры:
"долг 5 млн" -> {{"debt_amount": 5000000}}
"не плачу год" -> {{"overdue_months": 12}}
"работы нет" -> {{"has_income": false, "employment_type": "unemployed"}}
"есть квартира" -> {{"has_property": true}}

Сообщение пользователя: {message}

JSON:""")
    
    try:
        extraction_chain = extraction_prompt | llm | StrOutputParser()
        result = extraction_chain.invoke({"message": message})
        
        # Пытаемся парсить JSON
        try:
            extracted = json.loads(result)
        except:
            # Если не JSON, ищем JSON в тексте
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                extracted = json.loads(json_match.group())
            else:
                extracted = {}
        
        # Мержим с существующим контекстом
        updated_context = existing_context.copy()
        for key, value in extracted.items():
            if value is not None:
                updated_context[key] = value
        
        return updated_context
    except Exception as e:
        print(f"Error extracting info: {e}")
        return existing_context

def check_missing_info(context):
    """Определяет какая информация еще нужна для банкротства"""
    required_fields = {
        'debt_amount': 'сумму долга',
        'overdue_months': 'срок просрочки', 
        'has_income': 'наличие дохода',
        'has_property': 'наличие недвижимости'
    }
    
    missing = []
    for field, description in required_fields.items():
        if field not in context or context[field] is None:
            missing.append((field, description))
    
    return missing

def generate_contextual_question(missing_info, context):
    """Генерирует естественный вопрос на основе контекста и недостающей информации"""
    if not missing_info:
        return None
    
    field, description = missing_info[0]  # Берем первую недостающую информацию
    
    # Контекстные шаблоны вопросов
    questions = {
        'debt_amount': [
            "Можете уточнить примерную сумму долга?",
            "На какую сумму у вас долги?",
            "Сколько примерно составляет общая сумма задолженности?"
        ],
        'overdue_months': [
            "Как давно не платите по долгам? Сколько месяцев?",
            "Какой срок просрочки по платежам?",
            "Сколько месяцев не вносите платежи?"
        ],
        'has_income': [
            "У вас есть официальный доход сейчас?",
            "Работаете ли вы официально в данный момент?",
            "Есть ли у вас постоянный доход?"
        ],
        'has_property': [
            "Есть ли у вас недвижимость - квартира, дом, дача?",
            "У вас есть собственная недвижимость?",
            "Имеете ли вы в собственности квартиру или дом?"
        ]
    }
    
    if field in questions:
        # Выбираем вопрос в зависимости от контекста
        question_variants = questions[field]
        
        # Добавляем контекстное понимание
        context_intro = ""
        if context.get('debt_amount'):
            if field == 'overdue_months':
                context_intro = f"Понял, долг {format_amount(context['debt_amount'])}. "
        elif context.get('overdue_months'):
            if field == 'has_income':
                context_intro = f"Понятно, {context['overdue_months']} месяцев просрочки. "
        
        return context_intro + question_variants[0]
    
    return "Расскажите подробнее о вашей ситуации."

def format_amount(amount):
    """Форматирует сумму для вывода"""
    if amount >= 1000000:
        return f"{amount/1000000:.1f} млн тенге"
    elif amount >= 1000:
        return f"{amount/1000:.0f} тыс тенге" 
    else:
        return f"{amount} тенге"

def has_sufficient_info(context):
    """Проверяет достаточно ли информации для ответа"""
    required = ['debt_amount', 'overdue_months', 'has_income', 'has_property']
    return all(field in context and context[field] is not None for field in required)


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

# RAG prompt - local version instead of hub
prompt_rag = ChatPromptTemplate.from_template("""You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, just say that you don't know. Use three sentences maximum and keep the answer concise.
Question: {question} 
Context: {context} 
Answer:""")


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

# Prompt
template = """Here is a set of Q+A pairs:

{context}

to use these to synthesize an answer to the question: {question}
"""

prompt = ChatPromptTemplate.from_template(template)


# Query
def query(user_query):
    # generate optimized answer for a given query using the improved subqueries
    sub_questions = generate_sub_questions(user_query)
    generate_qa_pairs(sub_questions)
    answers, questions = retrieve_and_rag(prompt_rag, sub_questions)
    context = format_qa_pairs(questions, answers)

    final_rag_chain = (
        prompt
        | llm
        | StrOutputParser()
    )

    return final_rag_chain.invoke({"question": user_query, "context": context})

    
