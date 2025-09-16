import operator
from typing import Annotated, Optional
from langchain_core.messages import MessageLikeRepresentation
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


###################
# Structured Outputs
###################
class ConductResearch(BaseModel):
    """Call this tool to research a specific person."""

    research_person: str = Field(
        description="The person to research. Should be a single person, and should be described in high detail (at least a paragraph).",
    )


class ResearchComplete(BaseModel):
    """Call this tool to indicate that the research is complete."""


class ChronologyDate(TypedDict):
    year: int
    month: int
    day: Optional[int]


class ChronologyEvent(TypedDict):
    name: str
    description: str
    date: ChronologyDate
    location: Optional[str]


class PersonState(TypedDict):
    name: str
    description: str
    chronology: list[ChronologyEvent]


class SupervisorStateInput(TypedDict):
    person_to_research: str


def override_reducer(current_value, new_value):
    """Reducer function that allows overriding values in state."""
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)


class SupervisorState(SupervisorStateInput):
    research_iterations: int = 0
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
