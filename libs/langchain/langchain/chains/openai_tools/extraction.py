from typing import List, Optional, Type, Union

from langchain.output_parsers import PydanticToolsParser
from langchain.prompts import ChatPromptTemplate
from langchain.pydantic_v1 import BaseModel
from langchain.schema.language_model import BaseLanguageModel
from langchain.schema.runnable import Runnable
from langchain.utils.openai_functions import convert_pydantic_to_openai_function

_EXTRACTION_TEMPLATE = """Extract and save the relevant entities mentioned \
in the following passage together with their properties.

If a property is not present and is not required in the function parameters, do not include it in the output."""  # noqa: E501


def create_extraction_chain_pydantic(
    pydantic_schemas: Union[List[Type[BaseModel]], Type[BaseModel]],
    llm: BaseLanguageModel,
    system_message: str = _EXTRACTION_TEMPLATE,
) -> Runnable:
    if not isinstance(pydantic_schemas, list):
        pydantic_schemas = [pydantic_schemas]
    prompt = ChatPromptTemplate.from_messages(
        [("system", system_message), ("user", "{input}")]
    )
    functions = [convert_pydantic_to_openai_function(p) for p in pydantic_schemas]
    tools = [{"type": "function", "function": d} for d in functions]
    model = llm.bind(tools=tools)
    chain = prompt | model | PydanticToolsParser(tools=pydantic_schemas)
    return chain
