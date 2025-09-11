# Project : Retrieval Q&A (FAISS vector store)

---

> A basic RAG Q&A example with retrievalQA to collect information and respond to user queries using an  internet datasource.
Built on top of Facebook AI Similarity Search (FAISS). This project leverages FAISS's capabilities for efficient similarity search.


## Libraries:

- **OpenAI** : [OpenAI](https://python.langchain.com/docs/integrations/platforms/openai) is a Python library that provides a simple interface to the OpenAI API. It also provides a command-line interface (CLI) for interacting with the API.

- **python-dotenv** : [python-dotenv](https://pypi.org/project/python-dotenv/) is a Python library that loads environment variables from a .env file. It is used to load the OpenAI API key from the .env file.

- **colorama** : [python-dotenv](https://pypi.org/project/colorama/) is a Python library to produce colored terminal text and outputs

- **FAISS** : [faiss](https://python.langchain.com/v0.2/docs/integrations/vectorstores/faiss/) : Vector Store Facebook AI for similarity search

**Docs** 
- FAISS, vectostore: https://python.langchain.com/v0.2/docs/integrations/vectorstores/faiss/
- RetrievalQA: https://api.python.langchain.com/en/latest/chains/langchain.chains.retrieval_qa.base.RetrievalQA.html

## **Install Python** 

- A [Quick Guide for Installing](https://github.com/PackeTsar/Install-Python/blob/master/README.md#install-python-) Python on Common Operating Systems
- Download the latest version of [Python 3.12](https://www.python.org/downloads/)

## Create a virtual environment :

(Windows)
```
python -m venv env
```

(MacOS)
```
python3 -m venv env
```

## Activate the virtual environment :

```
source env/bin/activate
```

## Installation:
(Windows)
```
pip install -r requirements.txt
```

(MacOS)

```
pip3 install -r requirements.txt
```

## [get an API key](https://platform.openai.com/account/api-keys)

.env file

OPENAI_API_KEY=sk-brHeh...A39v5iXsM2

`export OPENAI_API_KEY='sk-brHeh...A39v5iXsM2'`


## Run the script:

(Windows)
```
python main.py
```

(MacOS)
```
python3 main.py
```
