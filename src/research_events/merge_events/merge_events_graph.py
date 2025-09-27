from typing import Literal, TypedDict

from langgraph.graph import START, StateGraph
from langgraph.graph.state import Command
from langgraph.pregel.main import asyncio
from src.llm_service import model_for_structured
from src.research_events.merge_events.utils import ensure_categories_with_events
from src.state import CategoriesWithEvents


class InputMergeEventsState(TypedDict):
    """The complete state for the event merging sub-graph."""

    existing_events: CategoriesWithEvents
    raw_extracted_events: str


class MergeEventsState(InputMergeEventsState):
    categorized_events: CategoriesWithEvents
    final_events: CategoriesWithEvents


class OutputMergeEventsState(MergeEventsState):
    final_events: CategoriesWithEvents  # includes the existing events + the events from the new events


async def categorize_events(
    state: MergeEventsState,
) -> Command[Literal["combine_new_and_original_events"]]:
    raw_extracted_events = state.get("raw_extracted_events", "")
    print("raw_extracted_events", raw_extracted_events)
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
        events=raw_extracted_events
    )

    structured_llm = model_for_structured.with_structured_output(CategoriesWithEvents)

    response = await structured_llm.ainvoke(categorize_events_prompt)
    return Command(
        goto="combine_new_and_original_events",
        update={"categorized_events": response},
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

    existing_events_raw = state.get(
        "existing_events",
        CategoriesWithEvents(early="", personal="", career="", legacy=""),
    )
    new_events_raw = state.get(
        "categorized_events",
        CategoriesWithEvents(early="", personal="", career="", legacy=""),
    )

    # Convert to proper Pydantic models if they're dicts
    existing_events = ensure_categories_with_events(existing_events_raw)
    new_events = ensure_categories_with_events(new_events_raw)

    if not new_events:
        print("No new events found. Keeping existing events.")
        return Command(goto="__end__", update={"final_events": existing_events})

    merge_tasks = []
    categories = CategoriesWithEvents.model_fields.keys()

    for category in categories:
        # Now you can safely use getattr since they're guaranteed to be Pydantic models
        existing_text = getattr(existing_events, category, "").strip()
        new_text = getattr(new_events, category, "").strip()

        if not (existing_text or new_text):
            continue  # nothing to merge in this category

        existing_display = existing_text if existing_text else "No events"
        new_display = new_text if new_text else "No events"

        prompt = MERGE_EVENTS_TEMPLATE.format(
            original=existing_display,
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
            final_merged_dict[category] = getattr(existing_events, category, "")

    final_merged_output = CategoriesWithEvents(**final_merged_dict)
    return Command(goto="__end__", update={"final_events": final_merged_output})


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
