import logging
import re
from typing import List, Optional

from pydantic import BaseModel, Field

from langchain.callbacks.manager import (
    AsyncCallbackManagerForRetrieverRun,
    CallbackManagerForRetrieverRun,
)
from langchain.chains import LLMChain
from langchain.chains.prompt_selector import ConditionalPromptSelector
from langchain.document_loaders import AsyncHtmlLoader
from langchain.document_transformers import Html2TextTransformer
from langchain.llms import LlamaCpp
from langchain.llms.base import BaseLLM
from langchain.output_parsers.pydantic import PydanticOutputParser
from langchain.prompts import BasePromptTemplate, PromptTemplate
from langchain.schema import BaseRetriever, Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.utilities import GoogleSearchAPIWrapper
from langchain.vectorstores.base import VectorStore

logger = logging.getLogger(__name__)


class SearchQueries(BaseModel):
    """Search queries to run to research for the user's goal."""

    queries: List[str] = Field(
        ..., description="List of search queries to look up on Google"
    )


DEFAULT_LLAMA_SEARCH_PROMPT = PromptTemplate(
    input_variables=["question"],
    template="""<<SYS>> \n You are an assistant tasked with improving Google search 
    results. \n <</SYS>> \n\n [INST] Generate FIVE Google search queries that 
    are similar to this question. The output should be a numbered list of questions 
    and each should have a question mark at the end: \n\n {question} [/INST]""",
)

DEFAULT_SEARCH_PROMPT = PromptTemplate(
    input_variables=["question"],
    template="""You are an assistant tasked with improving Google search 
    results. Generate FIVE Google search queries that are similar to
    this question. The output should be a numbered list of questions and each
    should have a question mark at the end: {question}""",
)


class LineList(BaseModel):
    """List of questions."""

    lines: List[str] = Field(description="Questions")


class QuestionListOutputParser(PydanticOutputParser):
    """Output parser for a list of numbered questions."""

    def __init__(self) -> None:
        super().__init__(pydantic_object=LineList)

    def parse(self, text: str) -> LineList:
        lines = re.findall(r"\d+\..*?\n", text)
        return LineList(lines=lines)


class WebResearchRetriever(BaseRetriever):
    # Inputs
    vectorstore: VectorStore = Field(
        ..., description="Vector store for storing web pages"
    )
    llm_chain: LLMChain
    search: GoogleSearchAPIWrapper = Field(..., description="Google Search API Wrapper")
    max_splits_per_doc: int = Field(100, description="Maximum splits per document")
    num_search_results: int = Field(1, description="Number of pages per Google search")
    text_splitter: RecursiveCharacterTextSplitter = Field(
        RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=50),
        description="Text splitter for splitting web pages into chunks",
    )
    urls: List[str] = Field(
        default_factory=list, description="Current URLs being processed"
    )
    url_database: List[str] = Field(
        default_factory=list, description="List of processed URLs"
    )

    @classmethod
    def from_llm(
        cls,
        vectorstore: VectorStore,
        llm: BaseLLM,
        search: GoogleSearchAPIWrapper,
        prompt: Optional[BasePromptTemplate] = None,
        max_splits_per_doc: int = 100,
        num_search_results: int = 1,
        text_splitter: RecursiveCharacterTextSplitter = RecursiveCharacterTextSplitter(
            chunk_size=1500, chunk_overlap=50
        ),
    ) -> "WebResearchRetriever":
        """Initialize from llm using default template.

        Args:
            vectorstore: Vector store for storing web pages
            llm: llm for search question generation
            search: GoogleSearchAPIWrapper
            prompt: prompt to generating search questions
            max_splits_per_doc: Maximum splits per document to keep
            num_search_results: Number of pages per Google search
            text_splitter: Text splitter for splitting web pages into chunks

        Returns:
            WebResearchRetriever
        """

        if not prompt:
            QUESTION_PROMPT_SELECTOR = ConditionalPromptSelector(
                default_prompt=DEFAULT_SEARCH_PROMPT,
                conditionals=[
                    (lambda llm: isinstance(llm, LlamaCpp), DEFAULT_LLAMA_SEARCH_PROMPT)
                ],
            )
            prompt = QUESTION_PROMPT_SELECTOR.get_prompt(llm)

        # Use chat model prompt
        llm_chain = LLMChain(
            llm=llm,
            prompt=prompt,
            output_parser=QuestionListOutputParser(),
        )

        return cls(
            vectorstore=vectorstore,
            llm_chain=llm_chain,
            search=search,
            max_splits_per_doc=max_splits_per_doc,
            num_search_results=num_search_results,
            text_splitter=text_splitter,
        )

    def search_tool(self, query: str, num_search_results: int = 1) -> List[dict]:
        """Returns num_serch_results pages per Google search."""
        try:
            result = self.search.results(query, num_search_results)
        except Exception as e:
            raise Exception(f"Error: {str(e)}")
        return result

    def get_urls(self) -> List[str]:
        """Return the list of URLs fetched during the most recent query."""
        return self.urls

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> List[Document]:
        """Search Google for documents related to the query input.

        Args:
            query: user query

        Returns:
            Relevant documents from all various urls.
        """

        # Get search questions
        logger.info("Generating questions for Google Search ...")
        result = self.llm_chain({"question": query})
        logger.info(f"Questions for Google Search (raw): {result}")
        questions = getattr(result["text"], "lines", [])
        logger.info(f"Questions for Google Search: {questions}")

        # Get urls
        logger.info("Searching for relevat urls ...")
        urls_to_look = []
        for query in questions:
            # Google search
            search_results = self.search_tool(query, self.num_search_results)
            logger.info("Searching for relevat urls ...")
            logger.info(f"Search results: {search_results}")
            for res in search_results:
                urls_to_look.append(res["link"])

        # Relevant urls
        urls = set(urls_to_look)
        self.urls = list(urls)

        # Check for any new urls that we have not processed
        new_urls = list(urls.difference(self.url_database))

        logger.info(f"New URLs to load: {new_urls}")
        # Load, split, and add new urls to vectorstore
        if new_urls:
            loader = AsyncHtmlLoader(new_urls)
            html2text = Html2TextTransformer()
            logger.info("Grabbing most relevant splits from urls ...")
            filtered_splits = []
            text_splitter = self.text_splitter
            for doc in html2text.transform_documents(loader.load()):
                doc_splits = text_splitter.split_documents([doc])
                # Proect against very large documents
                if len(doc_splits) > self.max_splits_per_doc:
                    logger.info(
                        f"{doc.metadata} has too many splits ({len(doc_splits)}), "
                        f"keeping only the first {self.max_splits_per_doc}"
                    )
                    doc_splits = doc_splits[: self.max_splits_per_doc]
                filtered_splits.extend(doc_splits)
            self.vectorstore.add_documents(filtered_splits)
            self.url_database.extend(new_urls)

        # Search for relevant splits
        docs = []
        for query in questions:
            docs.extend(self.vectorstore.similarity_search(query))

        # Get unique docs
        unique_documents_dict = {
            (doc.page_content, tuple(sorted(doc.metadata.items()))): doc for doc in docs
        }
        unique_documents = list(unique_documents_dict.values())
        return unique_documents

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: AsyncCallbackManagerForRetrieverRun,
    ) -> List[Document]:
        raise NotImplementedError
