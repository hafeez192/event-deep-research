from typing import Literal, TypedDict

from langgraph.graph import START, StateGraph
from langgraph.graph.state import Command
from pydantic import BaseModel, Field
from src.llm_service import model_for_structured


class CategoriesWithEvents(BaseModel):
    early: str = Field(
        description="Covers childhood, upbringing, family, education, and early influences that shaped the author."
    )
    personal: str = Field(
        description="Focuses on relationships, friendships, family life, places of residence, and notable personal traits or beliefs."
    )
    career: str = Field(
        description="Details their professional journey: first steps into writing, major publications, collaborations, recurring themes, style, and significant milestones."
    )
    legacy: str = Field(
        description="Explains how their work was received, awards or recognition, cultural/literary impact, influence on other authors, and how they are remembered today."
    )


class InputMergeEventsState(TypedDict):
    """The complete state for the event merging sub-graph."""

    original_events: CategoriesWithEvents
    # new_events: str


class MergeEventsState(InputMergeEventsState):
    new_events_in_categories: CategoriesWithEvents
    merged_events: CategoriesWithEvents


class OutputMergeEventsState(MergeEventsState):
    merged_events: CategoriesWithEvents  # includes the origianl events + the events from the new events


async def categorize_events(
    state: MergeEventsState,
) -> Command[Literal["combine_new_and_original_events"]]:
    new_events = state.get("new_events", "")

    categorize_events_prompt = """
    You are a helpful assistant that will categorize the new events into the 4 categories.

    <New Events>
    {new_events}
    </New Events>
    
    <Categories>
    early: Covers childhood, upbringing, family, education, and early influences that shaped the author.
    personal: Focuses on relationships, friendships, family life, places of residence, and notable personal traits or beliefs.
    career: Details their professional journey: first steps into writing, major publications, collaborations, recurring themes, style, and significant milestones.
    legacy: Explains how their work was received, awards or recognition, cultural/literary impact, influence on other authors, and how they are remembered today.
    </Categories>


    <Rules>
    INCLUDE ALL THE INFORMATION FROM THE NEW EVENTS, do not abbreviate or omit any information.
    </Rules>
    """
    categorize_events_prompt = categorize_events_prompt.format(new_events=new_events)

    structured_llm = model_for_structured.with_structured_output(CategoriesWithEvents)

    response = await structured_llm.ainvoke(categorize_events_prompt)
    return Command(
        goto="combine_new_and_original_events",
        update={"new_events_in_categories": response},
    )


async def combine_new_and_original_events(
    state: MergeEventsState,
) -> Command[Literal["__end__"]]:
    """Combine the new events with the original events"""
    new_events_in_categories = state.get("new_events_in_categories")
    original_events = state.get("original_events")

    print("original_events", original_events)
    # Create a new CategoriesWithEvents object with merged content
    merged_events = CategoriesWithEvents(
        early="Original events:\n "
        + original_events["early"]
        + "\n"
        + "New events:\n "
        + new_events_in_categories.early,
        personal="Original events:\n "
        + original_events["personal"]
        + "\n"
        + "New events:\n "
        + new_events_in_categories.personal,
        career="Original events:\n "
        + original_events["career"]
        + "\n"
        + "New events:\n "
        + new_events_in_categories.career,
        legacy="Original events:\n "
        + original_events["legacy"]
        + "\n"
        + "New events:\n "
        + new_events_in_categories.legacy,
    )

    merge_events_prompt = """
    You are a helpful assistant that will merge the following lists including the original events and the new events.
    You will analyze if there is any events that can be merged into the same event. 
    At the end jus tone signle list with all the events should prevail. 

   <Events>
   {events}
   </Events>

    <Output>
    Provide the merged list of events. Just return the list of events. No other text.
    </Output>
    """

    final_merged_events = {}
    for key, events in merged_events:
        prompt = merge_events_prompt.format(events=events)
        response = await model_for_structured.ainvoke(prompt)
        final_merged_events[key] = response.content

    return Command(goto="__end__", update={"merged_events": final_merged_events})


merge_events_graph_builder = StateGraph(
    MergeEventsState,
    input_schema=InputMergeEventsState,
)

merge_events_graph_builder.add_node("categorize_events", categorize_events)
merge_events_graph_builder.add_node(
    "combine_new_and_original_events", combine_new_and_original_events
)
merge_events_graph_builder.add_edge(START, "categorize_events")

merge_events_graph = merge_events_graph_builder.compile()
