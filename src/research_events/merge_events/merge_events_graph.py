from typing import Literal, TypedDict

from langgraph.graph import START, StateGraph
from langgraph.graph.state import Command
from langgraph.pregel.main import asyncio
from src.llm_service import model_for_structured
from src.research_events.merge_events.utils import ensure_categories_with_events

from state import CategoriesWithEvents


class InputMergeEventsState(TypedDict):
    """The complete state for the event merging sub-graph."""

    original_events: CategoriesWithEvents
    events_extracted_from_url: str


class MergeEventsState(InputMergeEventsState):
    extracted_events_in_categories: CategoriesWithEvents
    merged_events: CategoriesWithEvents


class OutputMergeEventsState(MergeEventsState):
    merged_events: CategoriesWithEvents  # includes the origianl events + the events from the new events


async def categorize_events(
    state: MergeEventsState,
) -> Command[Literal["combine_new_and_original_events"]]:
    events_extracted_from_url = state.get("events_extracted_from_url", "")
    print("events_extracted_from_url", events_extracted_from_url)
    categorize_events_prompt = """
    You are a helpful assistant that will categorize the events into the 4 categories.

    <Events>
    {events}
    </Events>
    
    <Categories>
    early: Covers childhood, upbringing, family, education, and early influences that shaped the author.
    personal: Focuses on relationships, friendships, family life, places of residence, and notable personal traits or beliefs.
    career: Details their professional journey: first steps into writing, major publications, collaborations, recurring themes, style, and significant milestones.
    legacy: Explains how their work was received, awards or recognition, cultural/literary impact, influence on other authors, and how they are remembered today.
    </Categories>


    <Rules>
    INCLUDE ALL THE INFORMATION FROM THE EVENTS, do not abbreviate or omit any information.
    </Rules>
    """
    categorize_events_prompt = categorize_events_prompt.format(
        events=events_extracted_from_url
    )

    structured_llm = model_for_structured.with_structured_output(CategoriesWithEvents)

    response = await structured_llm.ainvoke(categorize_events_prompt)
    return Command(
        goto="combine_new_and_original_events",
        update={"extracted_events_in_categories": response},
    )


MERGE_EVENTS_TEMPLATE = """You are a helpful assistant that will merge two lists of events: 
the original events (which must always remain) and new events (which may contain extra details). 
The new events should only be treated as additions if they provide relevant new information. 
The final output must preserve the original events and seamlessly add the new ones if applicable.

<Rules>
- Always include the original events exactly, do not omit or alter them.
- Add new events only if they are not duplicates, combining details if they overlap.
- Format the final list as bullet points, one event per line (e.g., "- Event details.").
- Keep the list clean, concise, and without commentary.
</Rules>

<Events>
Original events:
{original}

New events:
{new}
</Events>

<Output>
Return only the merged list of events as bullet points, nothing else.
</Output>"""


async def combine_new_and_original_events(state: MergeEventsState) -> Command:
    """Merge original and new events for each category using an LLM."""
    print("Combining new and original events...")

    original_events_raw = state.get(
        "original_events",
        CategoriesWithEvents(early="", personal="", career="", legacy=""),
    )
    new_events_raw = state.get(
        "extracted_events_in_categories",
        CategoriesWithEvents(early="", personal="", career="", legacy=""),
    )

    # Convert to proper Pydantic models if they're dicts
    original_events = ensure_categories_with_events(original_events_raw)
    new_events = ensure_categories_with_events(new_events_raw)

    if not new_events:
        print("No new events found. Keeping original events.")
        return Command(goto="__end__", update={"merged_events": original_events})

    merge_tasks = []
    categories = CategoriesWithEvents.model_fields.keys()

    for category in categories:
        # Now you can safely use getattr since they're guaranteed to be Pydantic models
        original_text = getattr(original_events, category, "").strip()
        new_text = getattr(new_events, category, "").strip()

        if not (original_text or new_text):
            continue  # nothing to merge in this category

        original_display = original_text if original_text else "No events"
        new_display = new_text if new_text else "No events"

        prompt = MERGE_EVENTS_TEMPLATE.format(
            original=original_display,
            new=new_display,
        )
        merge_tasks.append((category, model_for_structured.ainvoke(prompt)))

    final_merged_dict = {}
    if merge_tasks:
        categories, tasks = zip(*merge_tasks)
        responses = await asyncio.gather(*tasks)
        final_merged_dict = {
            cat: resp.content for cat, resp in zip(categories, responses)
        }

    # Ensure all categories are included
    for category in CategoriesWithEvents.model_fields.keys():
        if category not in final_merged_dict:
            final_merged_dict[category] = getattr(original_events, category, "")

    final_merged_output = CategoriesWithEvents(**final_merged_dict)
    return Command(goto="__end__", update={"merged_events": final_merged_output})


merge_events_graph_builder = StateGraph(
    MergeEventsState,
    input_schema=InputMergeEventsState,
)

merge_events_graph_builder.add_node("categorize_events", categorize_events)
merge_events_graph_builder.add_node(
    "combine_new_and_original_events", combine_new_and_original_events
)
merge_events_graph_builder.add_edge(START, "categorize_events")

merge_events_app = merge_events_graph_builder.compile()
