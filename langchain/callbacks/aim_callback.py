import os
import tempfile
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import AgentAction, AgentFinish, LLMResult

from aim import Run, Text
from aim.ext.resource.configs import DEFAULT_SYSTEM_TRACKING_INT


def import_spacy() -> Any:
    try:
        import spacy  # noqa: F401
    except ImportError:
        raise ImportError(
            "To use the aim callback manager you need to have the `spacy` package installed."
            "Please install it with `pip install spacy`"
        )
    return spacy


def import_textstat() -> Any:
    try:
        import textstat  # noqa: F401
    except ImportError:
        raise ImportError(
            "To use the aim callback manager you need to have the `textstat` package installed."
            "Please install it with `pip install textstat`"
        )
    return textstat


class BaseMetadataCallbackHandler:
    """This class handles the metadata and associated function states for callbacks.

    Attributes:
        step (int): The current step.
        starts (int): The number of times the start method has been called.
        ends (int): The number of times the end method has been called.
        errors (int): The number of times the error method has been called.
        text_ctr (int): The number of times the text method has been called.
        ignore_llm_ (bool): Whether to ignore llm callbacks.
        ignore_chain_ (bool): Whether to ignore chain callbacks.
        ignore_agent_ (bool): Whether to ignore agent callbacks.
        always_verbose_ (bool): Whether to always be verbose.
        chain_starts (int): The number of times the chain start method has been called.
        chain_ends (int): The number of times the chain end method has been called.
        llm_starts (int): The number of times the llm start method has been called.
        llm_ends (int): The number of times the llm end method has been called.
        llm_streams (int): The number of times the text method has been called.
        tool_starts (int): The number of times the tool start method has been called.
        tool_ends (int): The number of times the tool end method has been called.
        agent_ends (int): The number of times the agent end method has been called.
        on_llm_start_records (list): A list of records of the on_llm_start method.
        on_llm_token_records (list): A list of records of the on_llm_token method.
        on_llm_end_records (list): A list of records of the on_llm_end method.
        on_chain_start_records (list): A list of records of the on_chain_start method.
        on_chain_end_records (list): A list of records of the on_chain_end method.
        on_tool_start_records (list): A list of records of the on_tool_start method.
        on_tool_end_records (list): A list of records of the on_tool_end method.
        on_agent_finish_records (list): A list of records of the on_agent_end method.
    """

    def __init__(self) -> None:
        self.step = 0

        self.starts = 0
        self.ends = 0
        self.errors = 0
        self.text_ctr = 0

        self.ignore_llm_ = False
        self.ignore_chain_ = False
        self.ignore_agent_ = False
        self.always_verbose_ = False

        self.chain_starts = 0
        self.chain_ends = 0

        self.llm_starts = 0
        self.llm_ends = 0
        self.llm_streams = 0

        self.tool_starts = 0
        self.tool_ends = 0

        self.agent_ends = 0

        self.on_llm_start_records: list = []
        self.on_llm_token_records: list = []
        self.on_llm_end_records: list = []

        self.on_chain_start_records: list = []
        self.on_chain_end_records: list = []

        self.on_tool_start_records: list = []
        self.on_tool_end_records: list = []

        self.on_text_records: list = []
        self.on_agent_finish_records: list = []
        self.on_agent_action_records: list = []

    @property
    def always_verbose(self) -> bool:
        """Whether to call verbose callbacks even if verbose is False."""
        return self.always_verbose_

    @property
    def ignore_llm(self) -> bool:
        """Whether to ignore LLM callbacks."""
        return self.ignore_llm_

    @property
    def ignore_chain(self) -> bool:
        """Whether to ignore chain callbacks."""
        return self.ignore_chain_

    @property
    def ignore_agent(self) -> bool:
        """Whether to ignore agent callbacks."""
        return self.ignore_agent_

    def get_custom_callback_meta(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "starts": self.starts,
            "ends": self.ends,
            "errors": self.errors,
            "text_ctr": self.text_ctr,
            "chain_starts": self.chain_starts,
            "chain_ends": self.chain_ends,
            "llm_starts": self.llm_starts,
            "llm_ends": self.llm_ends,
            "llm_streams": self.llm_streams,
            "tool_starts": self.tool_starts,
            "tool_ends": self.tool_ends,
            "agent_ends": self.agent_ends,
        }

    def reset_callback_meta(self) -> None:
        """Reset the callback metadata."""
        self.step = 0

        self.starts = 0
        self.ends = 0
        self.errors = 0
        self.text_ctr = 0

        self.ignore_llm_ = False
        self.ignore_chain_ = False
        self.ignore_agent_ = False
        self.always_verbose_ = False

        self.chain_starts = 0
        self.chain_ends = 0

        self.llm_starts = 0
        self.llm_ends = 0
        self.llm_streams = 0

        self.tool_starts = 0
        self.tool_ends = 0

        self.agent_ends = 0

        self.on_llm_start_records = []
        self.on_llm_token_records = []
        self.on_llm_end_records = []

        self.on_chain_start_records = []
        self.on_chain_end_records = []

        self.on_tool_start_records = []
        self.on_tool_end_records = []

        self.on_text_records = []
        self.on_agent_finish_records = []
        self.on_agent_action_records = []
        return None


class AimCallbackHandler(BaseMetadataCallbackHandler, BaseCallbackHandler):
    """Callback Handler that logs to Weights and Biases.

    Parameters:
        job_type (str): The type of job.
        project (str): The project to log to.
        entity (str): The entity to log to.
        tags (list): The tags to log.
        group (str): The group to log to.
        name (str): The name of the run.
        notes (str): The notes to log.
        complexity_metrics (bool): Whether to log complexity metrics.
        stream_logs (bool): Whether to stream callback actions to W&B


        repo (:obj:`str`, optional): Aim repository path or Repo object to which Run object is bound.
            If skipped, default Repo is used.
        experiment_name (:obj:`str`, optional): Sets Run's `experiment` property. 'default' if not specified.
            Can be used later to query runs/sequences.
        system_tracking_interval (:obj:`int`, optional): Sets the tracking interval in seconds for system usage
            metrics (CPU, Memory, etc.). Set to `None` to disable system metrics tracking.
        log_system_params (:obj:`bool`, optional): Enable/Disable logging of system params such as installed packages,
            git info, environment variables, etc.

    This handler will utilize the associated callback method called and formats
    the input of each callback function with metadata regarding the state of LLM run,
    and adds the response to the list of records for both the {method}_records and
    action. It then logs the response using the run.log() method to Weights and Biases.
    """

    def __init__(
        self,
        job_type: Optional[str] = None,
        project: Optional[str] = "langchain_callback_demo",
        entity: Optional[str] = None,
        tags: Optional[Sequence] = None,
        group: Optional[str] = None,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        complexity_metrics: bool = False,
        stream_logs: bool = False,
        repo: Optional[str] = None,
        experiment_name: Optional[str] = None,
        system_tracking_interval: Optional[int] = DEFAULT_SYSTEM_TRACKING_INT,
        log_system_params: bool = True,
    ) -> None:
        """Initialize callback handler."""

        import_textstat()
        spacy = import_spacy()
        super().__init__()

        self.job_type = job_type
        self.project = project
        self.entity = entity
        self.tags = tags
        self.group = group
        self.name = name
        self.notes = notes
        self.complexity_metrics = complexity_metrics
        self.stream_logs = stream_logs

        self.repo = repo
        self.experiment_name = experiment_name
        self.system_tracking_interval = system_tracking_interval
        self.log_system_params = log_system_params
        self._run = None
        self._run_hash = None

        self.temp_dir = tempfile.TemporaryDirectory()
        self.setup(
            {
                "job_type": self.job_type,
                "project": self.project,
                "entity": self.entity,
                "tags": self.tags,
                "group": self.group,
                "name": self.name,
                "notes": self.notes,
            }
        )

        self.callback_columns: list = []
        self.action_records: list = []
        try:
            spacy.load("en_core_web_sm")
        except Exception:
            os.system("python -m spacy download en_core_web_sm")
        self.nlp = spacy.load("en_core_web_sm")

    @property
    def experiment(self) -> Run:
        if self._run is not None:
            return self._run

    def setup(self, args=None):
        if not self._run:
            if self._run_hash:
                self._run = Run(
                    self._run_hash,
                    repo=self.repo,
                    system_tracking_interval=self.system_tracking_interval,
                )
            else:
                self._run = Run(
                    repo=self.repo,
                    experiment=self.experiment_name,
                    system_tracking_interval=self.system_tracking_interval,
                    log_system_params=self.log_system_params,
                )
                self._run_hash = self._run.hash

        if args:
            for key, value in args.items():
                self._run.set(key, value, strict=False)

    @classmethod
    def _flatten_dict(
        cls, nested_dict: Dict[str, Any], parent_key: str = "", sep: str = "_"
    ) -> Iterable[Tuple[str, Any]]:
        """
        Generator that yields flattened items from a nested dictionary for a flat dict.

        Parameters:
            nested_dict (dict): The nested dictionary to flatten.
            parent_key (str): The prefix to prepend to the keys of the flattened dict.
            sep (str): The separator to use between the parent key and the key of the
                flattened dictionary.

        Yields:
            (str, any): A key-value pair from the flattened dictionary.
        """
        for key, value in nested_dict.items():
            new_key = parent_key + sep + key if parent_key else key
            if isinstance(value, dict):
                yield from AimCallbackHandler._flatten_dict(value, new_key, sep)
            else:
                yield new_key, value

    @classmethod
    def flatten_dict(
        cls, nested_dict: Dict[str, Any], parent_key: str = "", sep: str = "_"
    ) -> Dict[str, Any]:
        """Flattens a nested dictionary into a flat dictionary.

        Parameters:
            nested_dict (dict): The nested dictionary to flatten.
            parent_key (str): The prefix to prepend to the keys of the flattened dict.
            sep (str): The separator to use between the parent key and the key of the
                flattened dictionary.

        Returns:
            (dict): A flat dictionary.

        """
        flat_dict = {
            k: v
            for k, v in AimCallbackHandler._flatten_dict(nested_dict, parent_key, sep)
        }
        return flat_dict

    @classmethod
    def get_text_stats(
        cls,
        text: str,
        complexity_metrics: bool = True,
    ) -> dict:
        """Analyze text using textstat and spacy.

        Parameters:
            text (str): The text to analyze.
            complexity_metrics (bool): Whether to compute complexity metrics.

        Returns:
            (dict): A dictionary containing the complexity metrics.
        """
        textstat = import_textstat()
        if complexity_metrics:
            return {
                "flesch_reading_ease": textstat.flesch_reading_ease(text),
                "flesch_kincaid_grade": textstat.flesch_kincaid_grade(text),
                "smog_index": textstat.smog_index(text),
                "coleman_liau_index": textstat.coleman_liau_index(text),
                "automated_readability_index": textstat.automated_readability_index(
                    text
                ),
                "dale_chall_readability_score": textstat.dale_chall_readability_score(
                    text
                ),
                "difficult_words": textstat.difficult_words(text),
                "linsear_write_formula": textstat.linsear_write_formula(text),
                "gunning_fog": textstat.gunning_fog(text),
                "text_standard": textstat.text_standard(text),
                "fernandez_huerta": textstat.fernandez_huerta(text),
                "szigriszt_pazos": textstat.szigriszt_pazos(text),
                "gutierrez_polini": textstat.gutierrez_polini(text),
                "crawford": textstat.crawford(text),
                "gulpease_index": textstat.gulpease_index(text),
                "osman": textstat.osman(text),
            }
        return {}

    def _init_resp(self) -> Dict:
        return {k: None for k in self.callback_columns}

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Run when LLM starts."""
        self.step += 1
        self.llm_starts += 1
        self.starts += 1

        resp = self._init_resp()
        resp.update({"action": "on_llm_start"})
        resp.update(AimCallbackHandler.flatten_dict(serialized))
        resp.update(self.get_custom_callback_meta())

        for prompt in prompts:
            prompt_resp = deepcopy(resp)
            prompt_resp["prompts"] = prompt

            self._run.track(
                Text(prompt_resp["prompts"]),
                name=prompt_resp["action"],
                context=prompt_resp,
            )

            self.on_llm_start_records.append(prompt_resp)
            self.action_records.append(prompt_resp)
            if self.stream_logs:
                self.run.log(prompt_resp)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run when LLM ends running."""
        self.step += 1
        self.llm_ends += 1
        self.ends += 1

        resp = self._init_resp()
        resp.update({"action": "on_llm_end"})
        resp.update(AimCallbackHandler.flatten_dict(response.llm_output or {}))
        resp.update(self.get_custom_callback_meta())

        for generations in response.generations:
            for generation in generations:
                generation_resp = deepcopy(resp)
                generation_resp.update(
                    AimCallbackHandler.flatten_dict(generation.dict())
                )
                generation_resp.update(
                    AimCallbackHandler.get_text_stats(
                        generation.text,
                        self.complexity_metrics,
                    )
                )

                self._run.track(
                    Text(generation_resp["text"]),
                    name=generation_resp["action"],
                    context=generation_resp,
                )

                self.on_llm_end_records.append(generation_resp)
                self.action_records.append(generation_resp)
                if self.stream_logs:
                    self.run.log(generation_resp)

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Run when LLM generates a new token."""
        self.step += 1
        self.llm_streams += 1

        resp = self._init_resp()
        resp.update({"action": "on_llm_new_token", "token": token})
        resp.update(self.get_custom_callback_meta())

        self.on_llm_token_records.append(resp)
        self.action_records.append(resp)
        if self.stream_logs:
            self.run.log(resp)

    def on_llm_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Run when LLM errors."""
        self.step += 1
        self.errors += 1

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Run when chain starts running."""
        self.step += 1
        self.chain_starts += 1
        self.starts += 1

        resp = self._init_resp()
        resp.update({"action": "on_chain_start"})
        resp.update(AimCallbackHandler.flatten_dict(serialized))
        resp.update(self.get_custom_callback_meta())

        chain_input = inputs["input"]

        if isinstance(chain_input, str):
            input_resp = deepcopy(resp)
            input_resp["input"] = chain_input

            self._run.track(
                Text(input_resp["input"]), name=input_resp["action"], context=input_resp
            )

            self.on_chain_start_records.append(input_resp)
            self.action_records.append(input_resp)
            if self.stream_logs:
                self.run.log(input_resp)
        elif isinstance(chain_input, list):
            for inp in chain_input:
                input_resp = deepcopy(resp)
                input_resp.update(inp)

                self._run.track(
                    Text(input_resp["input"]),
                    name=input_resp["action"],
                    context=input_resp,
                )

                self.on_chain_start_records.append(input_resp)
                self.action_records.append(input_resp)
                if self.stream_logs:
                    self.run.log(input_resp)
        else:
            raise ValueError("Unexpected data format provided!")

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Run when chain ends running."""
        self.step += 1
        self.chain_ends += 1
        self.ends += 1

        resp = self._init_resp()
        resp.update({"action": "on_chain_end", "outputs": outputs["output"]})
        resp.update(self.get_custom_callback_meta())

        self._run.track(Text(resp["outputs"]), name=resp["action"], context=resp)

        self.on_chain_end_records.append(resp)
        self.action_records.append(resp)
        if self.stream_logs:
            self.run.log(resp)

    def on_chain_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Run when chain errors."""
        self.step += 1
        self.errors += 1

    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        """Run when tool starts running."""
        self.step += 1
        self.tool_starts += 1
        self.starts += 1

        resp = self._init_resp()
        resp.update({"action": "on_tool_start", "input_str": input_str})
        resp.update(AimCallbackHandler.flatten_dict(serialized))
        resp.update(self.get_custom_callback_meta())

        self._run.track(Text(resp["input_str"]), name=resp["action"], context=resp)

        self.on_tool_start_records.append(resp)
        self.action_records.append(resp)
        if self.stream_logs:
            self.run.log(resp)

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Run when tool ends running."""
        self.step += 1
        self.tool_ends += 1
        self.ends += 1

        resp = self._init_resp()
        resp.update({"action": "on_tool_end", "output": output})
        resp.update(self.get_custom_callback_meta())

        self._run.track(Text(resp["output"]), name=resp["action"], context=resp)

        self.on_tool_end_records.append(resp)
        self.action_records.append(resp)
        if self.stream_logs:
            self.run.log(resp)

    def on_tool_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Run when tool errors."""
        self.step += 1
        self.errors += 1

    def on_text(self, text: str, **kwargs: Any) -> None:
        """
        Run when agent is ending.
        """
        self.step += 1
        self.text_ctr += 1

        resp = self._init_resp()
        resp.update({"action": "on_text", "text": text})
        resp.update(self.get_custom_callback_meta())

        self.on_text_records.append(resp)
        self.action_records.append(resp)
        if self.stream_logs:
            self.run.log(resp)

    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> None:
        """Run when agent ends running."""
        self.step += 1
        self.agent_ends += 1
        self.ends += 1

        resp = self._init_resp()
        resp.update(
            {
                "action": "on_agent_finish",
                "output": finish.return_values["output"],
                "log": finish.log,
            }
        )
        resp.update(self.get_custom_callback_meta())

        self._run.track(Text(resp["output"]), name=resp["action"], context=resp)

        self.on_agent_finish_records.append(resp)
        self.action_records.append(resp)
        if self.stream_logs:
            self.run.log(resp)

    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> Any:
        """Run on agent action."""
        self.step += 1
        self.tool_starts += 1
        self.starts += 1

        resp = self._init_resp()
        resp.update(
            {
                "action": "on_agent_action",
                "tool": action.tool,
                "tool_input": action.tool_input,
                "log": action.log,
            }
        )
        resp.update(self.get_custom_callback_meta())

        self._run.track(Text(resp["tool_input"]), name=resp["action"], context=resp)

        self.on_agent_action_records.append(resp)
        self.action_records.append(resp)
        if self.stream_logs:
            self.run.log(resp)

    def flush_tracker(
        self,
        langchain_asset: Any = None,
        reset: bool = True,
        finish: bool = False,
        job_type: Optional[str] = None,
        project: Optional[str] = None,
        entity: Optional[str] = None,
        tags: Optional[Sequence] = None,
        group: Optional[str] = None,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        complexity_metrics: Optional[bool] = None,
        repo: Optional[str] = None,
        experiment_name: Optional[str] = None,
        system_tracking_interval: Optional[int] = DEFAULT_SYSTEM_TRACKING_INT,
        log_system_params: bool = True,
    ) -> None:
        """Flush the tracker and reset the session.

        Args:
            langchain_asset: The langchain asset to save.
            reset: Whether to reset the session.
            finish: Whether to finish the run.
            job_type: The job type.
            project: The project.
            entity: The entity.
            tags: The tags.
            group: The group.
            name: The name.
            notes: The notes.
            complexity_metrics: Whether to compute complexity metrics.

            Returns:
                None
        """

        if langchain_asset:
            try:
                for key, value in langchain_asset.dict().items():
                    self._run.set(key, value, strict=False)
            except Exception:
                pass

        if finish or reset:
            self._run.close()
            self.temp_dir.cleanup()
            self.reset_callback_meta()
        if reset:
            self.__init__(  # type: ignore
                job_type=job_type if job_type else self.job_type,
                project=project if project else self.project,
                entity=entity if entity else self.entity,
                tags=tags if tags else self.tags,
                group=group if group else self.group,
                name=name if name else self.name,
                notes=notes if notes else self.notes,
                complexity_metrics=complexity_metrics
                if complexity_metrics
                else self.complexity_metrics,
                repo=repo if repo else self.repo,
                experiment_name=experiment_name
                if experiment_name
                else self.experiment_name,
                system_tracking_interval=system_tracking_interval
                if system_tracking_interval
                else self.system_tracking_interval,
                log_system_params=log_system_params
                if log_system_params
                else self.log_system_params,
            )
