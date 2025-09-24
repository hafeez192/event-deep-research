"""Defines the Pydantic models and TypedDicts for the research agent graph.
This file serves as the schema for data structures, agent tools, and state management.
"""

import operator
from typing import Annotated, List, Literal, TypedDict

from langchain_core.messages import MessageLikeRepresentation
from pydantic import BaseModel, Field

################################################################################
# Section 1: Core Data Models
# - Defines the structure of the primary research output: the chronological timeline.
################################################################################


class ChronologyDate(BaseModel):
    """A structured representation of a date for a chronological event."""

    year: int | None = Field(None, description="The year of the event.")
    note: str | None = Field(
        None, description="Adds extra information to the date (month, day, range...)."
    )


class ChronologyEventInput(BaseModel):
    """Represents a single event, typically used for initial data extraction before an ID is assigned."""

    name: str = Field(description="A short, title-like name for the event.")
    description: str = Field(description="A concise description of the event.")
    date: ChronologyDate = Field(..., description="The structured date of the event.")
    location: str | None = Field(
        None, description="The geographical location where the event occurred."
    )


class ChronologyEvent(ChronologyEventInput):
    """The final, canonical event model with a unique identifier."""

    id: str = Field(
        description="The id of the event in lowercase and underscores. Ex: 'word1_word2'"
    )


class ChronologyInput(BaseModel):
    """A list of newly extracted events from a research source."""

    events: list[ChronologyEventInput]


class Chronology(BaseModel):
    """A complete chronological timeline with finalized (ID'd) events."""

    events: list[ChronologyEvent]


################################################################################
# Section 2: Agent Tools
# - Pydantic models that define the tools available to the LLM agents.
################################################################################


class ResearchEventsTool(BaseModel):
    """Finds a list of authoritative biography URLs for a given person.
    This should be the very first tool you call in the research process to gather a list of
    high-quality sources (like Wikipedia, Britannica) before you can start extracting events.
    """

    pass  # No arguments needed


class FinishResearchTool(BaseModel):
    """Concludes the research process.
    Call this tool ONLY when you have a comprehensive timeline of the person's life,
    including key events like birth, death, major achievements, and significant personal
    milestones, and you are confident that no major gaps remain.
    """

    pass


################################################################################
# Section 3: Graph State Definitions
# - TypedDicts and models that define the "memory" for the agent graphs.
################################################################################


def override_reducer(current_value, new_value):
    """Reducer function that allows a new value to completely replace the old one."""
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    return operator.add(current_value, new_value)


# --- Main Supervisor Graph State ---


class SupervisorStateInput(TypedDict):
    """The initial input to start the main research graph."""

    person_to_research: str


class SupervisorState(SupervisorStateInput):
    """The complete state for the main supervisor graph."""

    events: List[ChronologyEvent]
    messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    messages_summary: str
    tool_call_iterations: int = 0


# --- Event Merging Sub-Graph State ---


class InputMergeEventsState(TypedDict):
    """The initial input for the sub-graph that merges new events."""

    url_events_summarized: str
    original_events: list[ChronologyEvent]


class MatchedEvent(BaseModel):
    """Intermediate model for tracking new vs. updated events during a merge."""

    id: str
    status: Literal["updated", "new"]
    name: str
    description: str
    date: str
    location: str


class MatchEventsState(BaseModel):
    """Represents the output of the event matching step."""

    matched_events: list[MatchedEvent]


class MergeEventsState(InputMergeEventsState):
    """The complete state for the event merging sub-graph."""

    matched_events: list[MatchedEvent]
    merged_events: list[ChronologyEvent]
