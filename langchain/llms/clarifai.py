"""Wrapper around Clarifai's APIs."""
import logging
from typing import Any, Dict, List, Optional

from pydantic import Extra, root_validator

from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import LLM
from langchain.llms.utils import enforce_stop_tokens
from langchain.utils import get_from_dict_or_env

logger = logging.getLogger(__name__)


class Clarifai(LLM):
    """Wrapper around Clarifai's large language models.

    To use, you should have an account on the Clarifai platform, the ``clarifai`` python package installed, and the
    environment variable ``CLARIFAI_PAT_KEY`` set with your PAT key, or pass it as a named parameter to the constructor.

    Example:
        .. code-block:: python

            from langchain.llms import Clarifai
            clarifai_llm = Clarifai(clarifai_pat_key=CLARIFAI_PAT_KEY, user_id=USER_ID, app_id=APP_ID, model_id=MODEL_ID)
    """

    stub: Any  #: :meta private:
    metadata: Any
    userDataObject: Any

    model_id: Optional[str] = None
    """Model id to use."""

    model_version_id: Optional[str] = None
    """Model version id to use."""

    app_id: Optional[str] = None
    """Clarifai application id to use."""

    user_id: Optional[str] = None
    """Clarifai user id to use."""

    clarifai_pat_key: Optional[str] = None

    api_base: str = "https://api.clarifai.com"

    stop: Optional[List[str]] = None

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that we have all required info to access Clarifai platform and python package exists in environment."""
        values["clarifai_pat_key"] = get_from_dict_or_env(
            values, "clarifai_pat_key", "CLARIFAI_PAT_KEY"
        )
        user_id = values.get("user_id")
        app_id = values.get("app_id")
        model_id = values.get("model_id")

        if values["clarifai_pat_key"] is None:
            raise ValueError("Please provide a clarifai_pat_key.")
        if user_id is None:
            raise ValueError("Please provide a user_id.")
        if app_id is None:
            raise ValueError("Please provide a app_id.")
        if model_id is None:
            raise ValueError("Please provide a model_id.")

        try:
            from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
            from clarifai_grpc.grpc.api import (
                resources_pb2,
                service_pb2,
                service_pb2_grpc,
            )
            from clarifai_grpc.grpc.api.status import status_code_pb2
        except ImportError:
            raise ImportError(
                "Could not import cohere python package. "
                "Please install it with `pip install clarifai`."
            )
        return values

    @property
    def _default_params(self) -> Dict[str, Any]:
        """Get the default parameters for calling Cohere API."""
        return {}

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Get the identifying parameters."""
        return {**{"model_id": self.model_id}}

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "clarifai"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> str:
        """Call out to Clarfai's PostModelOutputs endpoint.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            The string generated by the model.

        Example:
            .. code-block:: python

                response = clarifai_llm("Tell me a joke.")
        """

        try:
            from clarifai.auth.helper import ClarifaiAuthHelper
            from clarifai.client import create_stub
            from clarifai_grpc.grpc.api import (
                resources_pb2,
                service_pb2,
            )
            from clarifai_grpc.grpc.api.status import status_code_pb2
        except ImportError:
            raise ImportError(
                "Could not import clarifai python package. "
                "Please install it with `pip install clarifai`."
            )

        auth = ClarifaiAuthHelper(
            user_id=self.user_id,
            app_id=self.app_id,
            pat=self.clarifai_pat_key,
            base=self.api_base,
        )
        self.userDataObject = auth.get_user_app_id_proto()
        self.stub = create_stub(auth)

        params = self._default_params
        if self.stop is not None and stop is not None:
            raise ValueError("`stop` found in both the input and default params.")
        elif self.stop is not None:
            params["stop_sequences"] = self.stop
        else:
            params["stop_sequences"] = stop

        post_model_outputs_request = service_pb2.PostModelOutputsRequest(
            user_app_id=self.userDataObject,  # The userDataObject is created in the overview and is required when using a PAT
            model_id=self.model_id,
            version_id=self.model_version_id,  # This is optional. Defaults to the latest model version
            inputs=[
                resources_pb2.Input(
                    data=resources_pb2.Data(text=resources_pb2.Text(raw=prompt))
                )
            ],
        )
        post_model_outputs_response = self.stub.PostModelOutputs(
            post_model_outputs_request
        )

        if post_model_outputs_response.status.code != status_code_pb2.SUCCESS:
            logger.error(post_model_outputs_response.status)
            raise Exception(
                "Post model outputs failed, status: "
                + post_model_outputs_response.status.description
            )

        text = post_model_outputs_response.outputs[0].data.text.raw

        # In order to make this consistent with other endpoints, we strip them.
        if stop is not None or self.stop is not None:
            text = enforce_stop_tokens(text, params["stop_sequences"])
        return text
