import operator
from typing import Annotated, List

from langchain_core.messages import MessageLikeRepresentation
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


###################
# Structured Outputs
###################
class ConductResearch(BaseModel):
    """Call this tool to research a specific person."""

    research_person: str = Field(
        description="The person to research. Just it's name and basic biographical information like birth date, death date, and location.",
    )


class ResearchComplete(BaseModel):
    """Call this tool to indicate that the research is complete."""


# class PersonState(TypedDict):
#     name: str
#     description: str
#     chronology: list[ChronologyEvent]


class SupervisorStateInput(TypedDict):
    person_to_research: str


class Summary(BaseModel):
    """Research summary with key findings."""

    summary: str
    key_excerpts: str


def override_reducer(current_value, new_value):
    """Reducer function that allows overriding values in state."""
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)


class ResearcherState(TypedDict):
    """Defines the structure of the agent's state."""

    messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    historical_figure: str
    retrieved_documents: List[dict]  # Each dict: {"source": str, "content": str}
    tool_call_iterations: int


class SupervisorState(SupervisorStateInput):
    research_iterations: int = 0
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]


# class ResearcherState(TypedDict):
#     """State for individual researchers conducting research."""

#     researcher_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
#     think_content: str
#     historical_figure: str
#     tool_call_iterations: int = 0
#     tool_calls: List[ToolCall]
#     person_to_research: str
#     compressed_research: str
#     raw_notes: str


class ChronologyDate(BaseModel):
    """A structured representation of a date for a chronological event."""

    year: int | None = Field(None, description="The year of the event.")
    note: str | None = Field(
        None,
        description="Adds extra information to the date (month, day, range...)",
    )


class ChronologyEvent(BaseModel):
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


class Chronology(BaseModel):
    """A complete chronological list of events extracted from research notes."""

    events: list[ChronologyEvent] = Field(
        description="A comprehensive list of all chronological events found in the research.",
    )


class ResearcherOutputState(TypedDict):
    """Output state for individual researchers conducting research."""

    compressed_research: list[ChronologyEvent]
