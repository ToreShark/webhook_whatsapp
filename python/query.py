import glob
from dotenv import load_dotenv
from operator import itemgetter
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from utils import format_qa_pair, format_qa_pairs

from colorama import Fore
import warnings

warnings.filterwarnings("ignore")

load_dotenv()

# LLM будет инициализирован в функции
llm = None

# Load local documents from docs folder
def load_documents():
    """Load all txt files from docs folder, split them into chunks."""
    all_documents = []
    
    # Load all .txt files from docs folder
    for file_path in glob.glob("./docs/*.txt"):
        loader = TextLoader(file_path)
        documents = loader.load()
        all_documents.extend(documents)
    
    text_splitter = CharacterTextSplitter(chunk_size=2500, chunk_overlap=200)
    return text_splitter.split_documents(all_documents)


# Global variables for vector store
vectorstore = None
retriever = None

def init_vectorstore():
    """Initialize vector store with OpenAI embeddings"""
    global vectorstore, retriever
    if vectorstore is None:
        documents = load_documents()
        vectorstore = Chroma.from_documents(documents=documents, 
                                          embedding=OpenAIEmbeddings())
        retriever = vectorstore.as_retriever()


# 1. DECOMPOSITION
template = """Ты помощник по вопросам банкротства в Казахстане. Разбей сложный вопрос на несколько простых подвопросов.
Цель: разделить входной вопрос на набор подпроблем/подвопросов, которые можно решить по отдельности.
Сгенерируй несколько поисковых запросов, связанных с: {question}
Выведи (3 запроса):"""
prompt_decomposition = ChatPromptTemplate.from_template(template)


def generate_sub_questions(query):
    """generate sub questions based on user query"""
    # Chain
    generate_queries_decomposition = (
        prompt_decomposition 
        | llm 
        | StrOutputParser()
        | (lambda x: x.split("\n"))
    ) 

    # Run
    sub_questions = generate_queries_decomposition.invoke({"question": query})
    # Убрали вывод подвопросов
    return sub_questions 
      

# 2. ANSWER SUBQUESTIONS RECURSIVELY 
template = """Вот вопрос, на который тебе нужно ответить:

\n --- \n {sub_question} \n --- \n

Вот доступные пары вопрос + ответ:

\n --- \n {q_a_pairs} \n --- \n

Вот дополнительный контекст, относящийся к вопросу: 

\n --- \n {context} \n --- \n

Используй приведенный выше контекст и любые пары вопрос + ответ для ответа на вопрос: \n {sub_question}
"""
prompt_qa = ChatPromptTemplate.from_template(template)


def generate_qa_pairs(sub_questions):
    """ask the LLM to generate a pair of question and answer based on the original user query"""
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
    
    return q_a_pairs

# 3. ANSWER INDIVIDUALLY

# Custom RAG prompt for bankruptcy law in Russian
template_rag = """Ты юрист-консультант по банкротству в Казахстане. Отвечай только на русском языке.

Контекст из документов:
{context}

Вопрос: {question}

Дай точный и профессиональный ответ на основе предоставленных документов о банкротстве в Казахстане. 
Если информации недостаточно, так и скажи. Отвечай только на русском языке."""
prompt_rag = ChatPromptTemplate.from_template(template_rag)


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

# Final synthesis prompt for bankruptcy law
template = """Ты юрист-консультант по банкротству в Казахстане. 

Вот набор пар Вопрос+Ответ из документов о банкротстве:

{context}

На основе этой информации дай развернутый, профессиональный ответ на вопрос: {question}

Важно:
- Отвечай только на русском языке
- Используй только информацию из предоставленных документов
- Давай практические советы по банкротству в Казахстане
- Если информации недостаточно, честно об этом скажи"""

prompt = ChatPromptTemplate.from_template(template)


# Query
def query(user_query):
    """Generate optimized answer for a given query using the improved subqueries"""
    
    # Generate sub-questions
    sub_questions = generate_sub_questions(user_query)
    
    # Generate Q&A pairs recursively
    generate_qa_pairs(sub_questions)
    
    # Get individual RAG answers
    answers, questions = retrieve_and_rag(prompt_rag, sub_questions)
    
    # Format the context
    context = format_qa_pairs(questions, answers)

    # Generate final answer
    final_rag_chain = (
        prompt
        | llm
        | StrOutputParser()
    )

    return final_rag_chain.invoke({"question": user_query, "context": context})


def process_query(user_query):
    """Main function to process user query - used by API"""
    global llm
    
    try:
        # Initialize LLM if not already done
        if llm is None:
            llm = ChatOpenAI()
        
        # Initialize vectorstore if not already done
        init_vectorstore()
        
        return query(user_query)
    except Exception as e:
        print(f"Error in process_query: {str(e)}")
        return "Извините, произошла ошибка при обработке вашего запроса. Попробуйте еще раз."