from typing import Any, Optional

from pydantic import BaseModel, Field

from langchain_core.runnables import RunnableConfig

import os


class Configuration(BaseModel):
    """Main configuration class for the Deep Research agent."""

    # General Configuration
    max_structured_output_retries: int = Field(
        default=1,
    )

    research_model: str = Field(
        default="google_genai:gemini-2.5-flash-lite",
        # default="openai:gpt-4o-mini"
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
