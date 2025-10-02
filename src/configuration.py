import os
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel


class Configuration(BaseModel):
    """Main configuration class for the Deep Research agent."""

    structured_llm_model: str = "ollama:mistral-nemo:latest"

    tools_llm_model: str = "ollama:qwen3:14b"

    structured_llm_max_tokens: int = 4096

    tools_llm_max_tokens: int = 4096

    max_structured_output_retries: int = 3

    max_tools_output_retries: int = 3

    @classmethod
    def from_runnable_config(
        cls, config: RunnableConfig | None = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = config.get("configurable", {}) if config else {}
        field_names = list(cls.model_fields.keys())
        values: dict[str, Any] = {
            field_name: os.environ.get(field_name.upper(), configurable.get(field_name))
            for field_name in field_names
        }
        return cls(**{k: v for k, v in values.items() if v is not None})
