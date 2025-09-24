import operator
from typing import Annotated, List, TypedDict

from langchain_core.messages import MessageLikeRepresentation
from pydantic import BaseModel, Field


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


def override_reducer(current_value, new_value):
    """Reducer function that allows overriding values in state."""
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)


class SupervisorStateInput(TypedDict):
    person_to_research: str


class ChronologyDate(BaseModel):
    """A structured representation of a date for a chronological event."""

    year: int | None = Field(None, description="The year of the event.")
    note: str | None = Field(
        None,
        description="Adds extra information to the date (month, day, range...)",
    )


class ChronologyEventInput(BaseModel):
    """Represents a single, significant event in a chronological timeline."""

    name: str = Field(
        description="A short, title-like name for the event (e.g., 'Publication of Novel X', 'Moved to Paris').",
    )
    description: str = Field(
        description="A concise description of the event, containing the key details from the research.",
    )
    date: ChronologyDate = Field(..., description="The structured date of the event.")
    location: str | None = Field(
        None,
        description="The geographical location where the event occurred, if mentioned.",
    )


class ChronologyInput(BaseModel):
    """A complete chronological list of events extracted from research notes."""

    events: list[ChronologyEventInput] = Field(
        description="A comprehensive list of all chronological events found in the research.",
    )


class ChronologyEvent(ChronologyEventInput):
    """Represents a single, significant event in a chronological timeline."""

    id: str = Field(
        description="The id of the event in lowercase and underscores. Ex: 'word1_word2'",
    )


class Chronology(BaseModel):
    """A complete chronological list of events extracted from research notes."""

    events: list[ChronologyEvent] = Field(
        description="A comprehensive list of all chronological events found in the research.",
    )


class SupervisorState(SupervisorStateInput):
    events: List[ChronologyEvent]
    messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    messages_summary: str
    tool_call_iterations: int = 0
