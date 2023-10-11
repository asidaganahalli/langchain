from typing import Any, Dict, List, Mapping, Optional

from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import LLM
from langchain.llms.utils import enforce_stop_tokens
from langchain.load.serializable import Serializable
from langchain.pydantic_v1 import root_validator
from langchain.utils import get_from_dict_or_env


class BaseYandexGPT(Serializable):
    yc_iam_token: str = ""
    """Yandex Cloud IAM token for service account
    with the `ai.languageModels.user` role"""
    model_name: str = "general"
    """Model name to use."""
    temperature: float = 0.6
    """What sampling temperature to use."""
    max_tokens: int = 7400
    """The maximum number of tokens to generate in the completion."""
    stop: Optional[List[str]] = None
    """Sequences when completion generation will stop."""

    @property
    def _llm_type(self) -> str:
        return "yandex_gpt"

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that iam token exists in environment."""

        yc_iam_token = get_from_dict_or_env(values, "yc_iam_token", "YC_IAM_TOKEN")
        values["yc_iam_token"] = yc_iam_token
        return values


class YandexGPT(BaseYandexGPT, LLM):
    """Yandex large language models.

    To use, you should have the ``yandexcloud`` python package installed, and the
    environment variable ``YC_IAM_TOKEN`` set with IAM token
    for the service account with the ``ai.languageModels.user`` role, or pass
    it as a named parameter ``yc_iam_token`` to the constructor.

    Example:
        .. code-block:: python

            from langchain.llms import YandexGPT
            yandex_gpt = YandexGPT(yc_iam_token="t1.9eu...")
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
            from google.protobuf.wrappers_pb2 import DoubleValue, Int64Value
            from yandex.cloud.ai.llm.v1alpha.llm_pb2 import GenerationOptions
            from yandex.cloud.ai.llm.v1alpha.llm_service_pb2 import (
                InstructRequest,
                InstructResponse,
            )
            from yandex.cloud.ai.llm.v1alpha.llm_service_pb2_grpc import (
                TextGenerationAsyncServiceStub,
            )
            from yandexcloud import SDK
        except ImportError as e:
            raise ImportError(
                "Please install YandexCloud SDK" " with `pip install yandexcloud`."
            ) from e
        sdk = SDK(iam_token=self.yc_iam_token)
        request = InstructRequest(
            model=self.model_name,
            request_text=prompt,
            generation_options=GenerationOptions(
                temperature=DoubleValue(value=self.temperature),
                max_tokens=Int64Value(value=self.max_tokens),
            ),
        )
        operation = sdk.client(TextGenerationAsyncServiceStub).Instruct(request)
        res = sdk.wait_operation_and_get_result(
            operation, response_type=InstructResponse
        )
        text = res.response.alternatives[0].text
        if stop is not None:
            text = enforce_stop_tokens(text, stop)
        return text
