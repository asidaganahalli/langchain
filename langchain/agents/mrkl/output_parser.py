import re
from typing import Union

from langchain.agents.agent import AgentOutputParser
from langchain.agents.mrkl.prompt import FORMAT_INSTRUCTIONS
from langchain.schema import AgentAction, AgentFinish, OutputParserException

FINAL_ANSWER_ACTION = "Final Answer:"


class MRKLOutputParser(AgentOutputParser):
    def get_format_instructions(self) -> str:
        return FORMAT_INSTRUCTIONS

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        if FINAL_ANSWER_ACTION in text:
            return AgentFinish(
                {"output": text.split(FINAL_ANSWER_ACTION)[-1].strip()}, text
            )
        # \s matches against tab/newline/whitespace
        regex = (
            r"Action\s*\d*\s*:[\s]*(.*?)[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)"
        )
        match = re.search(regex, text, re.DOTALL)
        if not match:
            if not re.search(r"Action\s*\d*\s*:[\s]*(.*?)", text, re.DOTALL):
                raise OutputParserException(
                    f"Could not parse LLM output: `{text}`",
                    observation="Invalid Format: Missing 'Action:' after 'Thought:'",
                    llm_output=text,
                    send_to_llm=True,
                )
            elif not re.search(
                r"[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)", text, re.DOTALL
            ):
                raise OutputParserException(
                    f"Could not parse LLM output: `{text}`",
                    observation="Invalid Format:"
                    " Missing 'Action Input:' after 'Action:'",
                    llm_output=text,
                    send_to_llm=True,
                )
            else:
                raise OutputParserException(f"Could not parse LLM output: `{text}`")
        action = match.group(1).strip()
        action_input = match.group(2)

        output = action_input.strip(" ")
        # ensure if its a well formed SQL query we don't remove any trailing " chars
        if action_input.startswith('SELECT ') is False:
            output = output.strip('"')

        return AgentAction(action, output, text)

    @property
    def _type(self) -> str:
        return "mrkl"
