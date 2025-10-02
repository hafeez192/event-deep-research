from typing import Any, List, Type

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from src.configuration import Configuration
from src.utils import get_api_key_for_model


def get_llm(model_name: str, **kwargs: Any) -> BaseChatModel:
    """Get LLM service."""
    return init_chat_model(temperature=0, model=model_name, **kwargs)


# model_for_tools = get_llm("ollama:gpt-oss:20b")
model_for_tools = get_llm("ollama:gpt-oss:20b")
model_for_structured = get_llm("ollama:mistral-nemo:latest")

configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


# This contains the shared logic. The underscore _ means other files shouldn't use it.
def _build_and_configure_model(
    config: RunnableConfig,
    model_chain: Runnable,
    model_name: str,
    max_tokens: int,
    max_retries: int,
) -> Runnable:
    """Internal helper to apply retry and runtime configuration."""
    model_config = {
        "model": model_name,
        "max_tokens": max_tokens,
        "api_key": get_api_key_for_model(model_name, config),
    }
    return model_chain.with_retry(stop_after_attempt=max_retries).with_config(
        model_config
    )


# --- Public Function 1: For Models WITH Tools ---
def create_tools_model(tools: List[Type[BaseTool]], config: RunnableConfig) -> Runnable:
    """Creates a model configured specifically for tool-calling."""
    configurable = Configuration.from_runnable_config(config)

    # Start the chain by binding the tools
    model_with_tools = configurable_model.bind_tools(tools)

    return _build_and_configure_model(
        config=config,
        model_chain=model_with_tools,
        model_name=configurable.tools_llm_model,
        max_tokens=configurable.tools_llm_max_tokens,
        max_retries=configurable.max_tools_output_retries,
    )


# --- Public Function 2: For Models WITHOUT Tools ---
def create_structured_model(config: RunnableConfig) -> Runnable:
    """Creates a general-purpose chat model with no tools."""
    configurable = Configuration.from_runnable_config(config)

    # The chain is just the base model itself
    base_model = configurable_model

    return _build_and_configure_model(
        config=config,
        model_chain=base_model,
        model_name=configurable.structured_llm_model,
        max_tokens=configurable.structured_llm_max_tokens,
        max_retries=configurable.max_structured_output_retries,
    )
