from __future__ import annotations

from typing import Any, Dict, List

from pydantic import root_validator

from langchain.schema import BaseOutputParser


class CombiningOutputParser(BaseOutputParser):
    """Class to combine multiple output parsers into one."""

    parsers: List[BaseOutputParser]

    @root_validator()
    def validate_parsers(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the parsers."""
        parsers = values["parsers"]
        if len(parsers) < 2:
            raise ValueError("Must have at least two parsers")
        for parser in parsers:
            if parser._type == "combining":
                raise ValueError("Cannot nest combining parsers")
            if parser._type == "list":
                raise ValueError("Cannot comine list parsers")
        return values

    @property
    def _type(self) -> str:
        """Return the type key."""
        return "combining"

    def get_format_instructions(self) -> str:
        """Instructions on how the LLM output should be formatted."""

        initial = f"For your first output: {self.parsers[0].get_format_instructions()}"
        subsequent = "\n".join(
            [
                f"Complete that output fully. Then produce another output, separated by two newline characters: {p.get_format_instructions()}"
                for p in self.parsers[1:]
            ]
        )
        return f"{initial}\n{subsequent}"

    def parse(self, text: str) -> Dict[str, Any]:
        """Parse the output of an LLM call."""
        texts = text.split("\n\n")
        output = dict()
        for i, parser in enumerate(self.parsers):
            output.update(parser.parse(texts[i].strip()))
        return output
