"""Wrapper around YandexGPT chat models."""
import logging
from typing import Any, Dict, List, Optional, Tuple, cast

from langchain.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain.chat_models.base import BaseChatModel
from langchain.llms.utils import enforce_stop_tokens
from langchain.llms.yandex import _BaseYandexGPT
from langchain_core.schema import (
    AIMessage,
    BaseMessage,
    ChatGeneration,
    ChatResult,
    HumanMessage,
    SystemMessage,
)

logger = logging.getLogger(__name__)


def _parse_message(role: str, text: str) -> Dict:
    return {"role": role, "text": text}


def _parse_chat_history(history: List[BaseMessage]) -> Tuple[List[Dict[str, str]], str]:
    """Parse a sequence of messages into history.

    Returns:
        A tuple of a list of parsed messages and an instruction message for the model.
    """
    chat_history = []
    instruction = ""
    for message in history:
        content = cast(str, message.content)
        if isinstance(message, HumanMessage):
            chat_history.append(_parse_message("user", content))
        if isinstance(message, AIMessage):
            chat_history.append(_parse_message("assistant", content))
        if isinstance(message, SystemMessage):
            instruction = content
    return chat_history, instruction


class ChatYandexGPT(_BaseYandexGPT, BaseChatModel):
    """Wrapper around YandexGPT large language models.

    There are two authentication options for the service account
    with the ``ai.languageModels.user`` role:
        - You can specify the token in a constructor parameter `iam_token`
        or in an environment variable `YC_IAM_TOKEN`.
        - You can specify the key in a constructor parameter `api_key`
        or in an environment variable `YC_API_KEY`.

    Example:
        .. code-block:: python

            from langchain.chat_models import ChatYandexGPT
            chat_model = ChatYandexGPT(iam_token="t1.9eu...")

    """

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate next turn in the conversation.
        Args:
            messages: The history of the conversation as a list of messages.
            stop: The list of stop words (optional).
            run_manager: The CallbackManager for LLM run, it's not used at the moment.

        Returns:
            The ChatResult that contains outputs generated by the model.

        Raises:
            ValueError: if the last message in the list is not from human.
        """
        try:
            import grpc
            from google.protobuf.wrappers_pb2 import DoubleValue, Int64Value
            from yandex.cloud.ai.llm.v1alpha.llm_pb2 import GenerationOptions, Message
            from yandex.cloud.ai.llm.v1alpha.llm_service_pb2 import ChatRequest
            from yandex.cloud.ai.llm.v1alpha.llm_service_pb2_grpc import (
                TextGenerationServiceStub,
            )
        except ImportError as e:
            raise ImportError(
                "Please install YandexCloud SDK" " with `pip install yandexcloud`."
            ) from e
        if not messages:
            raise ValueError(
                "You should provide at least one message to start the chat!"
            )
        message_history, instruction = _parse_chat_history(messages)
        channel_credentials = grpc.ssl_channel_credentials()
        channel = grpc.secure_channel(self.url, channel_credentials)
        request = ChatRequest(
            model=self.model_name,
            generation_options=GenerationOptions(
                temperature=DoubleValue(value=self.temperature),
                max_tokens=Int64Value(value=self.max_tokens),
            ),
            instruction_text=instruction,
            messages=[Message(**message) for message in message_history],
        )
        stub = TextGenerationServiceStub(channel)
        if self.iam_token:
            metadata = (("authorization", f"Bearer {self.iam_token}"),)
        else:
            metadata = (("authorization", f"Api-Key {self.api_key}"),)
        res = stub.Chat(request, metadata=metadata)
        text = list(res)[0].message.text
        text = text if stop is None else enforce_stop_tokens(text, stop)
        message = AIMessage(content=text)
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise NotImplementedError(
            """YandexGPT doesn't support async requests at the moment."""
        )
