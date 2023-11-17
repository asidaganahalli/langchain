from typing import Any, Dict, List, Mapping, Optional

from langchain.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain.llms.base import LLM
from langchain.llms.utils import enforce_stop_tokens
from langchain_core.load.serializable import Serializable
from langchain_core.pydantic_v1 import root_validator
from langchain_core.utils import get_from_dict_or_env


class _BaseYandexGPT(Serializable):
    iam_token: str = ""
    """Yandex Cloud IAM token for service account
    with the `ai.languageModels.user` role"""
    api_key: str = ""
    """Yandex Cloud Api Key for service account
    with the `ai.languageModels.user` role"""
    model_name: str = "general"
    """Model name to use."""
    temperature: float = 0.6
    """What sampling temperature to use.
    Should be a double number between 0 (inclusive) and 1 (inclusive)."""
    max_tokens: int = 7400
    """Sets the maximum limit on the total number of tokens
    used for both the input prompt and the generated response.
    Must be greater than zero and not exceed 7400 tokens."""
    stop: Optional[List[str]] = None
    """Sequences when completion generation will stop."""
    url: str = "llm.api.cloud.yandex.net:443"
    """The url of the API."""

    @property
    def _llm_type(self) -> str:
        return "yandex_gpt"

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that iam token exists in environment."""

        iam_token = get_from_dict_or_env(values, "iam_token", "YC_IAM_TOKEN", "")
        values["iam_token"] = iam_token
        api_key = get_from_dict_or_env(values, "api_key", "YC_API_KEY", "")
        values["api_key"] = api_key
        if api_key == "" and iam_token == "":
            raise ValueError("Either 'YC_API_KEY' or 'YC_IAM_TOKEN' must be provided.")
        return values


class YandexGPT(_BaseYandexGPT, LLM):
    """Yandex large language models.

    To use, you should have the ``yandexcloud`` python package installed.

    There are two authentication options for the service account
    with the ``ai.languageModels.user`` role:
        - You can specify the token in a constructor parameter `iam_token`
        or in an environment variable `YC_IAM_TOKEN`.
        - You can specify the key in a constructor parameter `api_key`
        or in an environment variable `YC_API_KEY`.

    Example:
        .. code-block:: python

            from langchain.llms import YandexGPT
            yandex_gpt = YandexGPT(iam_token="t1.9eu...")
    """

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stop": self.stop,
        }

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call the Yandex GPT model and return the output.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            The string generated by the model.

        Example:
            .. code-block:: python

                response = YandexGPT("Tell me a joke.")
        """
        try:
            import grpc
            from google.protobuf.wrappers_pb2 import DoubleValue, Int64Value
            from yandex.cloud.ai.llm.v1alpha.llm_pb2 import GenerationOptions
            from yandex.cloud.ai.llm.v1alpha.llm_service_pb2 import InstructRequest
            from yandex.cloud.ai.llm.v1alpha.llm_service_pb2_grpc import (
                TextGenerationServiceStub,
            )
        except ImportError as e:
            raise ImportError(
                "Please install YandexCloud SDK" " with `pip install yandexcloud`."
            ) from e
        channel_credentials = grpc.ssl_channel_credentials()
        channel = grpc.secure_channel(self.url, channel_credentials)
        request = InstructRequest(
            model=self.model_name,
            request_text=prompt,
            generation_options=GenerationOptions(
                temperature=DoubleValue(value=self.temperature),
                max_tokens=Int64Value(value=self.max_tokens),
            ),
        )
        stub = TextGenerationServiceStub(channel)
        if self.iam_token:
            metadata = (("authorization", f"Bearer {self.iam_token}"),)
        else:
            metadata = (("authorization", f"Api-Key {self.api_key}"),)
        res = stub.Instruct(request, metadata=metadata)
        text = list(res)[0].alternatives[0].text
        if stop is not None:
            text = enforce_stop_tokens(text, stop)
        return text

    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Async call the Yandex GPT model and return the output.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            The string generated by the model.
        """
        try:
            import asyncio

            import grpc
            from google.protobuf.wrappers_pb2 import DoubleValue, Int64Value
            from yandex.cloud.ai.llm.v1alpha.llm_pb2 import GenerationOptions
            from yandex.cloud.ai.llm.v1alpha.llm_service_pb2 import (
                InstructRequest,
                InstructResponse,
            )
            from yandex.cloud.ai.llm.v1alpha.llm_service_pb2_grpc import (
                TextGenerationAsyncServiceStub,
            )
            from yandex.cloud.operation.operation_service_pb2 import GetOperationRequest
            from yandex.cloud.operation.operation_service_pb2_grpc import (
                OperationServiceStub,
            )
        except ImportError as e:
            raise ImportError(
                "Please install YandexCloud SDK" " with `pip install yandexcloud`."
            ) from e
        operation_api_url = "operation.api.cloud.yandex.net:443"
        channel_credentials = grpc.ssl_channel_credentials()
        async with grpc.aio.secure_channel(self.url, channel_credentials) as channel:
            request = InstructRequest(
                model=self.model_name,
                request_text=prompt,
                generation_options=GenerationOptions(
                    temperature=DoubleValue(value=self.temperature),
                    max_tokens=Int64Value(value=self.max_tokens),
                ),
            )
            stub = TextGenerationAsyncServiceStub(channel)
            if self.iam_token:
                metadata = (("authorization", f"Bearer {self.iam_token}"),)
            else:
                metadata = (("authorization", f"Api-Key {self.api_key}"),)
            operation = await stub.Instruct(request, metadata=metadata)
            async with grpc.aio.secure_channel(
                operation_api_url, channel_credentials
            ) as operation_channel:
                operation_stub = OperationServiceStub(operation_channel)
                while not operation.done:
                    await asyncio.sleep(1)
                    operation_request = GetOperationRequest(operation_id=operation.id)
                    operation = await operation_stub.Get(
                        operation_request, metadata=metadata
                    )

            instruct_response = InstructResponse()
            operation.response.Unpack(instruct_response)
            text = instruct_response.alternatives[0].text
            if stop is not None:
                text = enforce_stop_tokens(text, stop)
            return text
