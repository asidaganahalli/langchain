"""Test Anthropic API wrapper."""
from typing import List

from langchain_core.callbacks import (
    CallbackManager,
)
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from langchain_community.chat_models.gpt_router import ChatGPTRouter, GPTRouterModel
from tests.unit_tests.callbacks.fake_callback_handler import FakeCallbackHandler


def test_gpt_router_call() -> None:
    """Test valid call to GPTRouter."""
    anthropic_claude = GPTRouterModel(
        name="claude-instant-1.2", provider_name="anthropic"
    )
    chat = ChatGPTRouter(models_priority_list=[anthropic_claude])
    message = HumanMessage(content="Hello")
    response = chat([message])
    assert isinstance(response, AIMessage)
    assert isinstance(response.content, str)


def test_gpt_router_generate() -> None:
    """Test generate method of GPTRouter."""
    anthropic_claude = GPTRouterModel(
        name="claude-instant-1.2", provider_name="anthropic"
    )
    chat = ChatGPTRouter(models_priority_list=[anthropic_claude])
    chat_messages: List[List[BaseMessage]] = [
        [HumanMessage(content="How many toes do dogs have?")]
    ]
    messages_copy = [messages.copy() for messages in chat_messages]
    result: LLMResult = chat.generate(chat_messages)
    assert isinstance(result, LLMResult)
    for response in result.generations[0]:
        assert isinstance(response, ChatGeneration)
        assert isinstance(response.text, str)
        assert response.text == response.message.content
    assert chat_messages == messages_copy


def test_gpt_router_streaming() -> None:
    """Test streaming tokens from GPTRouter."""
    anthropic_claude = GPTRouterModel(
        name="claude-instant-1.2", provider_name="anthropic"
    )
    chat = ChatGPTRouter(models_priority_list=[anthropic_claude], streaming=True)
    message = HumanMessage(content="Hello")
    response = chat([message])
    assert isinstance(response, AIMessage)
    assert isinstance(response.content, str)


def test_gpt_router_streaming_callback() -> None:
    """Test that streaming correctly invokes on_llm_new_token callback."""
    callback_handler = FakeCallbackHandler()
    callback_manager = CallbackManager([callback_handler])
    anthropic_claude = GPTRouterModel(
        name="claude-instant-1.2", provider_name="anthropic"
    )
    chat = ChatGPTRouter(
        models_priority_list=[anthropic_claude],
        streaming=True,
        callback_manager=callback_manager,
        verbose=True,
    )
    message = HumanMessage(content="Write me a sentence with 10 words.")
    chat([message])
    assert callback_handler.llm_streams > 1
