from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from langchain_core.runnables import RunnableConfig

import os


class SearchAPI(Enum):
    """Enumeration of available search API providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    TAVILY = "tavily"
    NONE = "none"


class Configuration(BaseModel):
    """Main configuration class for the Deep Research agent."""

    # General Configuration
    max_structured_output_retries: int = Field(
        default=1,
    )

    research_model: str = Field(
        # default="google_genai:gemini-2.5-flash-lite",
        # default="openai:gpt-4o-mini"
        default="ollama:gpt-oss:latest",
    )
    research_model_max_tokens: int = Field(
        default=1000,
    )
    max_researcher_iterations: int = Field(
        default=10,
    )
    max_concurrent_research_units: int = Field(
        default=1,
    )
    search_api: SearchAPI = Field(
        default=SearchAPI.TAVILY,
    )
    compression_model: str = Field(
        default="ollama:llama3.1:latest",  # Errors with gpt-oss and structured output
    )
    compression_model_max_tokens: int = Field(
        default=8192,
    )

    max_react_tool_calls: int = Field(
        default=5,
    )

    max_content_length: int = Field(
        default=50000,
    )

    summarization_model: str = Field(
        default="ollama:gpt-oss:latest",
    )
    summarization_model_max_tokens: int = Field(
        default=2048,
    )

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = config.get("configurable", {}) if config else {}
        field_names = list(cls.model_fields.keys())
        values: dict[str, Any] = {
            field_name: os.environ.get(field_name.upper(), configurable.get(field_name))
            for field_name in field_names
        }
        return cls(**{k: v for k, v in values.items() if v is not None})
