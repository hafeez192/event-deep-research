import operator
from typing import Annotated, Dict, List, TypedDict

from langchain_core.messages import MessageLikeRepresentation
from langchain_core.pydantic_v1 import BaseModel, Field


class UrlFinderTool(BaseModel):
    """Finds a list of authoritative biography URLs for a given person.
    This should be the very first tool you call in the research process to gather a list of
    high-quality sources (like Wikipedia, Britannica) before you can start extracting events.
    """

    pass  # No arguments needed


class UrlCrawlerTool(BaseModel):
    """Extracts structured biographical events from a single URL.
    Use this tool after `UrlFinderTool` has provided a list of sources. This is the primary
    tool for populating the initial timeline with new events. You should call this for each
    promising URL you find.
    """

    url: str = Field(
        description="The single, most promising URL to crawl for new events."
    )


class FurtherEventResearchTool(BaseModel):
    """Deepens the research on a single, *existing* event to find missing details like
    specific dates, locations, or context. Use this tool when you already have a baseline
    of events from `UrlCrawlerTool` but they are incomplete. Do NOT use this to find new events.
    """

    event_name: str = Field(
        description="The exact name of the event from the timeline that needs more detail. For example, 'Marriage to June Mansfield'."
    )


class FinishResearchTool(BaseModel):
    """Concludes the research process.
    Call this tool ONLY when you have a comprehensive timeline of the person's life,
    including key events like birth, death, major achievements, and significant personal
    milestones, and you are confident that no major gaps remain.
    """

    pass


def override_reducer(current_value, new_value):
    """Reducer function that allows overriding values in state."""
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)


class SupervisorStateInput(TypedDict):
    person_to_research: str


class SupervisorState(SupervisorStateInput):
    events: List[Dict]
    messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    messages_summary: str
    tool_call_iterations: int = 0
