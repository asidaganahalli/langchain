"""Chain that implements the ReAct paper from https://arxiv.org/pdf/2210.03629.pdf."""
import re
from typing import Any, List, Optional, Tuple

from pydantic import BaseModel

from langchain.agents.agent import Agent
from langchain.agents.react.prompt import PROMPT
from langchain.agents.tools import Tool
from langchain.chains.llm import LLMChain
from langchain.docstore.base import Docstore
from langchain.docstore.document import Document
from langchain.llms.base import LLM


class ReActDocstoreAgent(Agent, BaseModel):
    """Agent for the ReAct chin."""

    i: int = 1

    @classmethod
    def from_llm_and_tools(
        cls, llm: LLM, tools: List[Tool], **kwargs: Any
    ) -> "ReActDocstoreAgent":
        """Construct an agent from an LLM and tools."""
        if len(tools) != 2:
            raise ValueError(f"Exactly two tools must be specified, but got {tools}")
        tool_names = {tool.name for tool in tools}
        if tool_names != {"Lookup", "Search"}:
            raise ValueError(
                f"Tool names should be Lookup and Search, got {tool_names}"
            )

        llm_chain = LLMChain(llm=llm, prompt=PROMPT)
        return cls(llm_chain=llm_chain, tools=tools, **kwargs)

    def _fix_text(self, text: str) -> str:
        return text + f"\nAction {self.i}:"

    def _extract_tool_and_input(self, text: str) -> Optional[Tuple[str, str]]:
        action_prefix = f"Action {self.i}: "
        if not text.split("\n")[-1].startswith(action_prefix):
            return None
        self.i += 1
        action_block = text.split("\n")[-1]

        action_str = action_block[len(action_prefix) :]
        # Parse out the action and the directive.
        re_matches = re.search(r"(.*?)\[(.*?)\]", action_str)
        if re_matches is None:
            raise ValueError(f"Could not parse action directive: {action_str}")
        return re_matches.group(1), re_matches.group(2)

    @property
    def finish_tool_name(self) -> str:
        """Name of the tool of when to finish the chain."""
        return "Finish"

    @property
    def observation_prefix(self) -> str:
        """Prefix to append the observation with."""
        return f"Observation {self.i - 1}: "

    @property
    def _stop(self) -> List[str]:
        return [f"\nObservation {self.i}: "]

    @property
    def llm_prefix(self) -> str:
        """Prefix to append the LLM call with."""
        return f"Thought {self.i}:"


class DocstoreExplorer:
    """Class to assist with exploration of a document store."""

    def __init__(self, docstore: Docstore):
        """Initialize with a docstore, and set initial document to None."""
        self.docstore = docstore
        self.document: Optional[Document] = None

    def search(self, term: str) -> str:
        """Search for a term in the docstore, and if found save."""
        result = self.docstore.search(term)
        if isinstance(result, Document):
            self.document = result
            return self.document.summary
        else:
            self.document = None
            return result

    def lookup(self, term: str) -> str:
        """Lookup a term in document (if saved)."""
        if self.document is None:
            raise ValueError("Cannot lookup without a successful search first")
        return self.document.lookup(term)


class ReActChain(ReActDocstoreAgent):
    """Chain that implements the ReAct paper.

    Example:
        .. code-block:: python

            from langchain import ReActChain, OpenAI
            react = ReAct(llm=OpenAI())
    """

    def __init__(self, llm: LLM, docstore: Docstore, **kwargs: Any):
        """Initialize with the LLM and a docstore."""
        docstore_explorer = DocstoreExplorer(docstore)
        tools = [
            Tool(name="Search", func=docstore_explorer.search),
            Tool(name="Lookup", func=docstore_explorer.lookup),
        ]
        llm_chain = LLMChain(llm=llm, prompt=PROMPT)
        super().__init__(llm_chain=llm_chain, tools=tools, **kwargs)
