import glob
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

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


# Direct RAG prompt for bankruptcy law in Russian
template_rag = """Ты юрист-консультант по банкротству в Казахстане. Отвечай только на русском языке.

Контекст из документов:
{context}

Вопрос: {question}

Дай точный и профессиональный ответ на основе предоставленных документов о банкротстве в Казахстане. 
Если информации недостаточно, так и скажи. Отвечай только на русском языке.
Структурируй ответ и давай практические рекомендации когда это возможно."""

prompt_rag = ChatPromptTemplate.from_template(template_rag)


def process_query(user_query):
    """Main function to process user query with direct RAG - used by API"""
    global llm
    
    try:
        # Initialize LLM if not already done
        if llm is None:
            llm = ChatOpenAI()
        
        # Initialize vectorstore if not already done
        init_vectorstore()
        
        # Get relevant documents
        retrieved_docs = retriever.get_relevant_documents(user_query)

        # Create RAG chain
        rag_chain = (
            prompt_rag
            | llm
            | StrOutputParser()
        )
        
        # Generate answer directly from retrieved documents
        answer = rag_chain.invoke({
            "question": user_query, 
            "context": retrieved_docs
        })
        
        return answer
        
    except Exception as e:
        print(f"Error in process_query: {str(e)}")
        return "Извините, произошла ошибка при обработке вашего запроса. Попробуйте еще раз."


# Backward compatibility - alias for the old function name
def query(user_query):
    """Backward compatibility function"""
    return process_query(user_query)