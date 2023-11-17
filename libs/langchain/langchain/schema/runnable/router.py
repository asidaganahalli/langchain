from __future__ import annotations

from typing import (
    Any,
    AsyncIterator,
    Callable,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Union,
    cast,
)

from typing_extensions import TypedDict

from langchain_core.runnable.base import (
    Input,
    Output,
    Runnable,
    RunnableSerializable,
    coerce_to_runnable,
)
from langchain_core.runnable.config import (
    RunnableConfig,
    get_config_list,
    get_executor_for_config,
)
from langchain_core.runnable.utils import (
    ConfigurableFieldSpec,
    gather_with_concurrency,
    get_unique_config_specs,
)


class RouterInput(TypedDict):
    """A Router input.

    Attributes:
        key: The key to route on.
        input: The input to pass to the selected runnable.
    """

    key: str
    input: Any


class RouterRunnable(RunnableSerializable[RouterInput, Output]):
    """
    A runnable that routes to a set of runnables based on Input['key'].
    Returns the output of the selected runnable.
    """

    runnables: Mapping[str, Runnable[Any, Output]]

    @property
    def config_specs(self) -> Sequence[ConfigurableFieldSpec]:
        return get_unique_config_specs(
            spec for step in self.runnables.values() for spec in step.config_specs
        )

    def __init__(
        self,
        runnables: Mapping[str, Union[Runnable[Any, Output], Callable[[Any], Output]]],
    ) -> None:
        super().__init__(
            runnables={key: coerce_to_runnable(r) for key, r in runnables.items()}
        )

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def is_lc_serializable(cls) -> bool:
        """Return whether this class is serializable."""
        return True

    @classmethod
    def get_lc_namespace(cls) -> List[str]:
        return cls.__module__.split(".")[:-1]

    def invoke(
        self, input: RouterInput, config: Optional[RunnableConfig] = None
    ) -> Output:
        key = input["key"]
        actual_input = input["input"]
        if key not in self.runnables:
            raise ValueError(f"No runnable associated with key '{key}'")

        runnable = self.runnables[key]
        return runnable.invoke(actual_input, config)

    async def ainvoke(
        self,
        input: RouterInput,
        config: Optional[RunnableConfig] = None,
        **kwargs: Optional[Any],
    ) -> Output:
        key = input["key"]
        actual_input = input["input"]
        if key not in self.runnables:
            raise ValueError(f"No runnable associated with key '{key}'")

        runnable = self.runnables[key]
        return await runnable.ainvoke(actual_input, config)

    def batch(
        self,
        inputs: List[RouterInput],
        config: Optional[Union[RunnableConfig, List[RunnableConfig]]] = None,
        *,
        return_exceptions: bool = False,
        **kwargs: Optional[Any],
    ) -> List[Output]:
        if not inputs:
            return []

        keys = [input["key"] for input in inputs]
        actual_inputs = [input["input"] for input in inputs]
        if any(key not in self.runnables for key in keys):
            raise ValueError("One or more keys do not have a corresponding runnable")

        def invoke(
            runnable: Runnable, input: Input, config: RunnableConfig
        ) -> Union[Output, Exception]:
            if return_exceptions:
                try:
                    return runnable.invoke(input, config, **kwargs)
                except Exception as e:
                    return e
            else:
                return runnable.invoke(input, config, **kwargs)

        runnables = [self.runnables[key] for key in keys]
        configs = get_config_list(config, len(inputs))
        with get_executor_for_config(configs[0]) as executor:
            return cast(
                List[Output],
                list(executor.map(invoke, runnables, actual_inputs, configs)),
            )

    async def abatch(
        self,
        inputs: List[RouterInput],
        config: Optional[Union[RunnableConfig, List[RunnableConfig]]] = None,
        *,
        return_exceptions: bool = False,
        **kwargs: Optional[Any],
    ) -> List[Output]:
        if not inputs:
            return []

        keys = [input["key"] for input in inputs]
        actual_inputs = [input["input"] for input in inputs]
        if any(key not in self.runnables for key in keys):
            raise ValueError("One or more keys do not have a corresponding runnable")

        async def ainvoke(
            runnable: Runnable, input: Input, config: RunnableConfig
        ) -> Union[Output, Exception]:
            if return_exceptions:
                try:
                    return await runnable.ainvoke(input, config, **kwargs)
                except Exception as e:
                    return e
            else:
                return await runnable.ainvoke(input, config, **kwargs)

        runnables = [self.runnables[key] for key in keys]
        configs = get_config_list(config, len(inputs))
        return await gather_with_concurrency(
            configs[0].get("max_concurrency"),
            *(
                ainvoke(runnable, input, config)
                for runnable, input, config in zip(runnables, actual_inputs, configs)
            ),
        )

    def stream(
        self,
        input: RouterInput,
        config: Optional[RunnableConfig] = None,
        **kwargs: Optional[Any],
    ) -> Iterator[Output]:
        key = input["key"]
        actual_input = input["input"]
        if key not in self.runnables:
            raise ValueError(f"No runnable associated with key '{key}'")

        runnable = self.runnables[key]
        yield from runnable.stream(actual_input, config)

    async def astream(
        self,
        input: RouterInput,
        config: Optional[RunnableConfig] = None,
        **kwargs: Optional[Any],
    ) -> AsyncIterator[Output]:
        key = input["key"]
        actual_input = input["input"]
        if key not in self.runnables:
            raise ValueError(f"No runnable associated with key '{key}'")

        runnable = self.runnables[key]
        async for output in runnable.astream(actual_input, config):
            yield output
