from typing import Any, Dict, List, Optional, Union

import torch
from transformers import StoppingCriteria, StoppingCriteriaList
from transformers.pipelines import TextGenerationPipeline

from langchain.callbacks.manager import (
    CallbackManagerForLLMRun,
)
from langchain.chat_models.base import BaseChatModel
from langchain.pydantic_v1 import root_validator
from langchain.schema import ChatResult
from langchain.schema.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
)
from langchain.schema.output import ChatGeneration

B_INST, E_INST = "[INST]", "[/INST]"
B_SYS, E_SYS = "<<SYS>>", "<</SYS>>"


class ChatLlama2(BaseChatModel):
    pipeline: TextGenerationPipeline

    @property
    def _llm_type(self) -> str:
        """Return type of chat model."""
        return "llama-2-chat-hf"

    @root_validator(pre=True)
    def validate_environment(cls, values: Dict) -> Dict:
        if (
            not hasattr(values["pipeline"], "task")
            or values["pipeline"].task != "text-generation"
        ):
            raise ValueError("The pipeline task should be 'text-generation'.")

        valid_models = (
            "meta-llama/Llama-2-7b-chat-hf",
            "meta-llama/Llama-2-13b-chat-hf",
            "meta-llama/Llama-2-70b-chat-hf",
        )

        if (
            not hasattr(values["pipeline"], "model")
            or values["pipeline"].model.name_or_path not in valid_models
        ):
            raise ValueError(
                f"The pipeline model name or path should be one of {valid_models}."
            )

        return values

    @staticmethod
    def format_messages_as_text(messages: List[BaseMessage]) -> str:
        """
        Transform List of Chat Messages to text following Meta's prompt guidelines.

        Prompt template with System Message:
        ```
        <s>[INST] <<SYS>>
        {{ system_prompt }}
        <</SYS>>

        {{ user_msg_1 }} [/INST] {{ model_answer_1 }} </s>
        <s>[INST] {{ user_msg_2 }} [/INST]
        ```

        Prompt template without System Message:
        ```
        <s>[INST] {{ user_msg_1 }} [/INST] {{ model_answer_1 }} </s>
        <s>[INST] {{ user_msg_2 }} [/INST] {{ model_answer_2}} </s>
        ```
        """
        prompt = ""

        for i, message in enumerate(messages):
            if isinstance(message, SystemMessage) and i != 0:
                raise ValueError(
                    "SystemMessage can only appear as the first message in the list."
                )
            elif isinstance(message, SystemMessage) and i == 0:
                prompt += f"<s>{B_INST} {B_SYS}\n{message.content}\n{E_SYS}\n\n"
            elif isinstance(message, HumanMessage) and i > 0:
                prompt += f"{message.content} {E_INST} "
            elif isinstance(message, HumanMessage) and i == 0:
                prompt += f"<s>{B_INST} {message.content} {E_INST} "
            elif isinstance(message, AIMessage):
                prompt += f"{message.content} </s><s>{B_INST} "
            elif isinstance(message, ChatMessage) and i == 0:
                prompt += f"<s>{B_INST} {message.role.capitalize()}:\
{message.content} {E_INST} "
            elif isinstance(message, ChatMessage) and i > 0:
                prompt += f"{message.role.capitalize()}: {message.content} {E_INST} "

        return prompt

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        prompt = self.format_messages_as_text(messages)

        # make sure that `return_full_text` is set to False
        # otherwise, pipeline will return prompt + generation
        kwargs["return_full_text"] = False
        kwargs["num_return_sequences"] = 1

        if stop:

            class StoppingCriteriaSub(StoppingCriteria):
                """Subclass of StoppingCriteria to allow for custom stopping criteria"""

                def __init__(
                    self,
                    stops: Optional[List] = None,
                    device: Union[torch.device, str, None] = None,
                ):
                    super().__init__()
                    stops = stops or []
                    if device:
                        self.stops = [stop.to(device) for stop in stops]
                    else:
                        self.stops = stops

                def __call__(
                    self,
                    input_ids: torch.LongTensor,
                    scores: torch.FloatTensor,
                    **kwargs: Dict,
                ) -> bool:
                    for stop_id in self.stops:
                        if (input_ids[0][-torch.numel(stop_id) :] == stop_id).all():
                            return True
                    return False

            stopping_criteria_tokenized = [
                self.pipeline.tokenizer(
                    stopping_criterion, return_tensors="pt", add_special_tokens=False
                )["input_ids"].squeeze()
                for stopping_criterion in stop
            ]

            stopping_criteria = StoppingCriteriaList(
                [
                    StoppingCriteriaSub(
                        stops=stopping_criteria_tokenized,
                        device="cuda:0",
                    )
                ]
            )
        else:
            stopping_criteria = None

        response = self.pipeline(prompt, stopping_criteria=stopping_criteria, **kwargs)[
            0
        ]["generated_text"]
        chat_generation = ChatGeneration(
            message=AIMessage(content=response),
        )
        return ChatResult(generations=[chat_generation])
