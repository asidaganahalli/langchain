"""Module to test base parser implementations."""
from typing import Iterable, List

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.output_parsers import (
    BaseGenerationOutputParser,
    BaseTransformOutputParser,
)
from langchain_core.output_parsers.base import T
from langchain_core.outputs import ChatGeneration, Generation
from tests.unit_tests.fake.chat_model import GenericFakeChatModel


def test_base_generation_parser() -> None:
    """Test Base Generation Output Parser."""

    class StrInvertCase(BaseGenerationOutputParser[str]):
        """An example parser that inverts the case of the characters in the message."""

        def parse_result(
            self, result: List[Generation], *, partial: bool = False
        ) -> str:
            """Parse a list of model Generations into a specific format.

            Args:
                result: A list of Generations to be parsed. The Generations are assumed
                    to be different candidate outputs for a single model input.
                    Many parsers assume that only a single generation is passed it in.
                    We will assert for that
                partial: Whether to allow partial results. This is used for parsers
                         that support streaming
            """
            if len(result) != 1:
                raise NotImplementedError(
                    "This output parser can only be used with a single generation."
                )
            generation = result[0]
            if not isinstance(generation, ChatGeneration):
                # Say that this one only works with chat generations
                raise OutputParserException(
                    "This output parser can only be used with a chat generation."
                )
            message = generation.message
            result = ""

            for char in message.content:
                # Invert the case of the characters
                if char.isupper():
                    result += char.lower()
                else:
                    result += char.upper()

            return result

    model = GenericFakeChatModel(messages=iter([AIMessage(content="hEllo")]))
    chain = model | StrInvertCase()
    assert chain.invoke("") == "HeLLO"


def test_base_transform_output_parser() -> None:
    """Test base transform output parser."""

    class StrInvertCase(BaseTransformOutputParser[str]):
        """An example parser that inverts the case of the characters in the message."""

        def parse(self, text: str) -> T:
            """Parse a single string into a specific format."""
            raise NotImplementedError()

        def parse_result(
            self, result: List[Generation], *, partial: bool = False
        ) -> str:
            """Parse a list of model Generations into a specific format.

            Args:
                result: A list of Generations to be parsed. The Generations are assumed
                    to be different candidate outputs for a single model input.
                    Many parsers assume that only a single generation is passed it in.
                    We will assert for that
                partial: Whether to allow partial results. This is used for parsers
                         that support streaming
            """
            if len(result) != 1:
                raise NotImplementedError(
                    "This output parser can only be used with a single generation."
                )
            generation = result[0]
            if not isinstance(generation, ChatGeneration):
                # Say that this one only works with chat generations
                raise OutputParserException(
                    "This output parser can only be used with a chat generation."
                )
            message = generation.message
            return message.content.swapcase()

    model = GenericFakeChatModel(messages=iter([AIMessage(content="hello world")]))
    chain = model | StrInvertCase()
    # inputs to models are ignored, response is hard-coded in model definition
    chunks = [chunk for chunk in chain.stream("")]
    assert chunks == ["HELLO", " ", "WORLD"]
