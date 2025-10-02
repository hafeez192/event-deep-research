from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel


def get_llm(model_name: str, **kwargs: Any) -> BaseChatModel:
    """Get LLM service."""
    return init_chat_model(temperature=0, model=model_name, **kwargs)


# model_for_tools = get_llm("ollama:gpt-oss:20b")
model_for_tools = get_llm("ollama:qwen3:14b")
model_for_structured = get_llm("ollama:mistral-nemo:latest")
