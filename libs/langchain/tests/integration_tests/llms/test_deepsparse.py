from deepsparse_llm import DeepSparse
import unittest
import pytest
from langchain.schema import LLMResult


class TestDeepSparse(unittest.TestCase):
    def test_deepsparse_call(self) -> None:
        """Test valid call to DeepSparse."""
        config = {"max_generated_tokens": 5}

        llm = DeepSparse(
            model="zoo:nlg/text_generation/codegen_mono-350m/pytorch/huggingface/bigpython_bigquery_thepile/base-none",
            config=config,
        )

        output = llm("def ")
        self.assertIsInstance(output, str)
        self.assertGreater(len(output), 1)

    def test_deepsparse_streaming(self) -> None:
        """Test valid call to DeepSparse with streaming."""
        config = {"max_generated_tokens": 5}

        llm = DeepSparse(
            model="hf:neuralmagic/mpt-7b-chat-pruned50-quant",
            config=config,
            streaming=True,
        )

        output = " "
        for chunk in llm.stream("Tell me a joke", stop=["'", "\n"]):
            output += chunk

        self.assertIsInstance(output, str)
        self.assertGreater(len(output), 1)


config = {"max_generated_tokens": 5}
llm = DeepSparse(
    model="hf:neuralmagic/mpt-7b-chat-pruned50-quant",
    config=config,
)


class TestAyscDeepSparse(unittest.TestCase):
    @pytest.mark.scheduled
    @pytest.mark.asyncio
    async def test_deepsparse_astream(self) -> None:
        async for token in llm.astream("I'm Pickle Rick"):
            self.assertIsInstance(token, str)

    @pytest.mark.scheduled
    @pytest.mark.asyncio
    async def test_deepsparse_abatch(self) -> None:
        result = await llm.abatch(["I'm Pickle Rick", "I'm not Pickle Rick"])
        for token in result:
            self.assertIsInstance(token, str)

    @pytest.mark.asyncio
    async def test_deepsparse_abatch_tags(self) -> None:
        result = await llm.abatch(
            ["I'm Pickle Rick", "I'm not Pickle Rick"], config={"tags": ["foo"]}
        )
        for token in result:
            self.assertIsInstance(token, str)

    @pytest.mark.scheduled
    @pytest.mark.asyncio
    async def test_deepsparse_ainvoke(self) -> None:
        result = await llm.ainvoke("I'm Pickle Rick", config={"tags": ["foo"]})
        self.assertIsInstance(result, str)
