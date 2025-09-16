# backend/chatbot/graph.py
from typing import Optional

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.graph import START, StateGraph
from typing_extensions import TypedDict


load_dotenv()


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


# Initialize the LLM
llm = init_chat_model("google_genai:gemini-2.5-flash-lite")


def person_supervisor(state: PersonState):
    return {"person_state": state}


# Build the graph
graph_builder = StateGraph(PersonState)

graph_builder.add_node("person_supervisor", person_supervisor)
graph_builder.add_edge(START, "person_supervisor")

graph = graph_builder.compile()
