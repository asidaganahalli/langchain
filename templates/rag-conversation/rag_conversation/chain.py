import os
from operator import itemgetter
from typing import List, Tuple

from langchain.schema import AIMessage, HumanMessage, format_document
from langchain_community.chat_models import ChatCohere, ChatOpenAI
from langchain_community.embeddings import CohereEmbeddings, OpenAIEmbeddings
from langchain_community.vectorstores import Pinecone
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.prompts.prompt import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.runnables import (
    RunnableBranch,
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
)

if os.environ.get("PINECONE_API_KEY", None) is None:
    raise Exception("Missing `PINECONE_API_KEY` environment variable.")

if os.environ.get("PINECONE_ENVIRONMENT", None) is None:
    raise Exception("Missing `PINECONE_ENVIRONMENT` environment variable.")

PINECONE_INDEX_NAME = os.environ.get("PINECONE_INDEX", "langchain-test")

EMBEDDING_TYPE = os.environ.get("EMBEDDING_TYPE", "OpenAI")

if EMBEDDING_TYPE == "OpenAI":
    if os.environ.get("OPENAI_API_KEY", None) is None:
        raise Exception("Missing `OPENAI_API_KEY` environment variable.")
    embeddings = OpenAIEmbeddings()
    chat_model = ChatOpenAI
elif EMBEDDING_TYPE == "Cohere":
    if os.environ.get("COHERE_API_KEY", None) is None:
        raise Exception("Missing `COHERE_API_KEY` environment variable.")
    cohere_embed_model = "embed-english-v3.0"
    embeddings = CohereEmbeddings(model=cohere_embed_model)
    chat_model = ChatCohere
else:
    raise Exception("Invalid `EMBEDDING_TYPE` environment variable.")

### Ingest code - you may need to run this the first time
# # Load
# from langchain_community.document_loaders import WebBaseLoader
# loader = WebBaseLoader("https://lilianweng.github.io/posts/2023-06-23-agent/")
# data = loader.load()

# # Split
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)
# all_splits = text_splitter.split_documents(data)

# # Add to vectorDB
# vectorstore = Pinecone.from_documents(
#     documents=all_splits, embedding=embeddings, index_name=PINECONE_INDEX_NAME
# )
# retriever = vectorstore.as_retriever()

vectorstore = Pinecone.from_existing_index(PINECONE_INDEX_NAME, embeddings)
retriever = vectorstore.as_retriever()

# Condense a chat history and follow-up question into a standalone question
_template = """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question, in its original language.
Chat History:
{chat_history}
Follow Up Input: {question}
Standalone question:"""  # noqa: E501
CONDENSE_QUESTION_PROMPT = PromptTemplate.from_template(_template)

# RAG answer synthesis prompt
template = """Answer the question based only on the following context:
<context>
{context}
</context>"""
ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", template),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{question}"),
    ]
)

# Conversational Retrieval Chain
DEFAULT_DOCUMENT_PROMPT = PromptTemplate.from_template(template="{page_content}")


def _combine_documents(
    docs, document_prompt=DEFAULT_DOCUMENT_PROMPT, document_separator="\n\n"
):
    doc_strings = [format_document(doc, document_prompt) for doc in docs]
    return document_separator.join(doc_strings)


def _format_chat_history(chat_history: List[Tuple[str, str]]) -> List:
    buffer = []
    for human, ai in chat_history:
        buffer.append(HumanMessage(content=human))
        buffer.append(AIMessage(content=ai))
    return buffer


# User input
class ChatHistory(BaseModel):
    chat_history: List[Tuple[str, str]] = Field(..., extra={"widget": {"type": "chat"}})
    question: str


_search_query = RunnableBranch(
    # If input includes chat_history, we condense it with the follow-up question
    (
        RunnableLambda(lambda x: bool(x.get("chat_history"))).with_config(
            run_name="HasChatHistoryCheck"
        ),  # Condense follow-up question and chat into a standalone_question
        RunnablePassthrough.assign(
            chat_history=lambda x: _format_chat_history(x["chat_history"])
        )
        | CONDENSE_QUESTION_PROMPT
        | chat_model(temperature=0)
        | StrOutputParser(),
    ),
    # Else, we have no chat history, so just pass through the question
    RunnableLambda(itemgetter("question")),
)

_inputs = RunnableParallel(
    {
        "question": lambda x: x["question"],
        "chat_history": lambda x: _format_chat_history(x["chat_history"]),
        "context": _search_query | retriever | _combine_documents,
    }
).with_types(input_type=ChatHistory)

chain = _inputs | ANSWER_PROMPT | chat_model() | StrOutputParser()
