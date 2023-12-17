"""ZHIPU AI chat models wrapper."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterator, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import (
    BaseChatModel,
    generate_from_stream,
)
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.pydantic_v1 import BaseModel, Field

logger = logging.getLogger(__name__)


class ref(BaseModel):
    enable: bool = Field(True)
    search_query: str = Field("")


class meta(BaseModel):
    user_info: str = Field("")
    bot_info: str = Field("")
    bot_name: str = Field("")
    user_name: str = Field("User")


class ChatZhipuAI(BaseChatModel):
    """`ZHIPU AI` large language chat models API."""

    zhipuai: Any
    api_key: str = Field()
    model: str = Field("chatglm_turbo")
    temperature: float = Field(0.95)
    top_p: float = Field(0.7)
    request_id: Optional[str] = Field(None)
    streaming: bool = Field(False)
    return_type: str = Field("json_string")
    ref: Optional[ref] = Field(None)
    meta: Optional[meta] = Field(None)

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"model_name": self.model}

    @property
    def _llm_type(self) -> str:
        """Return the type of model."""
        return self.model

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            import zhipuai

            self.zhipuai = zhipuai
            self.zhipuai.api_key = self.api_key
        except ImportError:
            raise RuntimeError(
                "Could not import zhipuai package. Please install it via 'pip install zhipuai'"
            )

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        stream: Optional[bool] = False,
        **kwargs: Any,
    ) -> ChatResult:
        """ """
        prompt = []
        for message in messages:
            if isinstance(message, AIMessage):
                role = "assistant"
            else:  # For both HumanMessage and SystemMessage, role is 'user'
                role = "user"

            prompt.append({"role": role, "content": message.content})

        print("prompt", prompt)

        if not self.streaming:
            response = self.zhipuai.model_api.invoke(
                model=self.model,
                prompt=prompt,
                top_p=self.top_p,
                temperature=self.temperature,
            )
            if response["code"] != 200:
                raise RuntimeError(response)

            content = response["data"]["choices"][0]["content"]
            content = json.loads(content)
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content=content))]
            )

        else:
            stream_iter = self._stream(
                prompt=prompt, stop=stop, run_manager=run_manager, **kwargs
            )
            return generate_from_stream(stream_iter)

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        stream: Optional[bool] = False,
        **kwargs: Any,
    ) -> ChatResult:
        """ """
        print(messages)

        prompt = []
        for message in messages:
            if isinstance(message, AIMessage):
                role = "assistant"
            else:  # For both HumanMessage and SystemMessage, role is 'user'
                role = "user"

            prompt.append({"role": role, "content": message.content})

        print(prompt)

        response = await self.zhipuai.model_api.async_invoke(
            model=self.model,
            prompt=prompt,
            top_p=self.top_p,
            temperature=self.temperature,
        )
        if response["code"] != 200:
            raise RuntimeError(response)

        content = response["data"]["choices"][0]["content"]
        content = json.loads(content)
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=content))]
        )

    def _stream(
        self,
        prompt: List[Dict[str, str]],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        response = self.zhipuai.model_api.sse_invoke(
            model=self.model,
            prompt=prompt,
            top_p=self.top_p,
            temperature=self.temperature,
            incremental=True,
        )

        for r in response.events():
            if r.event == "error":
                raise ValueError(f"Error from Zhipuai api response: {r}")

            data = r.data
            print(data)
            chunk = AIMessageChunk(content=data)
            yield ChatGenerationChunk(message=chunk)
            if run_manager:
                run_manager.on_llm_new_token(chunk.content)
