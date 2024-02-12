import json
from typing import Any, Dict, List, Mapping, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.llms import LLM
from langchain_core.pydantic_v1 import Extra, root_validator
from langchain_core.utils import get_from_dict_or_env

from langchain_community.llms.utils import enforce_stop_tokens

# key: task
# value: key in the output dictionary
VALID_TASKS_DICT = {
    "translation": "translation_text",
    "summarization": "summary_text",
    "conversational": "generated_text",
    "text-generation": "generated_text",
    "text2text-generation": "generated_text",
}


class HuggingFaceHub(LLM):
    """HuggingFaceHub  models.

    To use, you should have the ``huggingface_hub`` python package installed, and the
    environment variable ``HUGGINGFACEHUB_API_TOKEN`` set with your API token, or pass
    it as a named parameter to the constructor.

    Supports `text-generation`, `text2text-generation`, `conversational`, `translation`,
     and `summarization`.

    Example:
        .. code-block:: python

            from langchain_community.llms import HuggingFaceHub
            hf = HuggingFaceHub(repo_id="gpt2", huggingfacehub_api_token="my-api-key")
    """

    client: Any  #: :meta private:
    repo_id: Optional[str] = None
    """Model name to use. 
    If not provided, the default model for the chosen task will be used."""
    task: Optional[str] = None
    """Task to call the model with.
    Should be a task that returns `generated_text`, `summary_text`, 
    or `translation_text`."""
    model_kwargs: Optional[dict] = None
    """Keyword arguments to pass to the model."""

    huggingfacehub_api_token: Optional[str] = None

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key and python package exists in environment."""
        huggingfacehub_api_token = get_from_dict_or_env(
            values, "huggingfacehub_api_token", "HUGGINGFACEHUB_API_TOKEN"
        )
        try:
            from huggingface_hub import HfApi, InferenceClient

            repo_id = values["repo_id"]
            client = InferenceClient(
                model=repo_id,
                token=huggingfacehub_api_token,
            )
            if not values["task"]:
                if not repo_id:
                    raise ValueError(
                        "Must specify either `repo_id` or `task`, or both."
                    )
                # Use the recommended task for the chosen model
                model_info = HfApi(token=huggingfacehub_api_token).model_info(
                    repo_id=repo_id
                )
                values["task"] = model_info.pipeline_tag
            if values["task"] not in VALID_TASKS_DICT:
                raise ValueError(
                    f"Got invalid task {values['task']}, "
                    f"currently only {VALID_TASKS_DICT.keys()} are supported"
                )
            values["client"] = client
        except ImportError:
            raise ValueError(
                "Could not import huggingface_hub python package. "
                "Please install it with `pip install huggingface_hub`."
            )
        return values

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        _model_kwargs = self.model_kwargs or {}
        return {
            **{"repo_id": self.repo_id, "task": self.task},
            **{"model_kwargs": _model_kwargs},
        }

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "huggingface_hub"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call out to HuggingFace Hub's inference endpoint.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            The string generated by the model.

        Example:
            .. code-block:: python

                response = hf("Tell me a joke.")
        """
        _model_kwargs = self.model_kwargs or {}
        parameters = {"return_full_text": False, **_model_kwargs, **kwargs, "return_full_text": False}

        response = self.client.post(
            json={"inputs": prompt, "parameters": parameters}, task=self.task
        )
        response = json.loads(response.decode())
        if "error" in response:
            raise ValueError(f"Error raised by inference API: {response['error']}")

        response_key = VALID_TASKS_DICT[self.task]  # type: ignore
        if isinstance(response, list):
            text = response[0][response_key]
        else:
            text = response[response_key]

        if stop is not None:
            # This is a bit hacky, but I can't figure out a better way to enforce
            # stop tokens when making calls to huggingface_hub.
            text = enforce_stop_tokens(text, stop)
        return text
