from typing import Literal, TypedDict

from langgraph.graph import START, StateGraph
from langgraph.graph.state import Command, RunnableConfig
from langgraph.pregel.main import asyncio
from src.configuration import Configuration
from src.llm_service import create_structured_model
from src.research_events.merge_events.prompts import (
    MERGE_EVENTS_TEMPLATE,
    categorize_events_prompt,
)
from src.research_events.merge_events.utils import ensure_categories_with_events
from src.services.event_service import EventService
from src.state import CategoriesWithEvents


class InputMergeEventsState(TypedDict):
    """The complete state for the event merging sub-graph."""

    existing_events: CategoriesWithEvents
    extracted_events: str


class MergeEventsState(InputMergeEventsState):
    extracted_events_categorized: CategoriesWithEvents
    chunked_events: list[str]  # for split chunks
    chunked_events_categorized: list[CategoriesWithEvents]  # for results per chunk


class OutputMergeEventsState(TypedDict):
    existing_events: CategoriesWithEvents  # includes the existing events + the events from the new events


async def split_events(
    state: MergeEventsState,
) -> Command[Literal["categorize_chunk"]]:
    extracted_events = state.get("extracted_events", "")

    chunks = EventService.split_events_into_chunks(extracted_events)

    return Command(
        goto="categorize_chunk",
        update={"chunked_events": chunks, "chunked_events_categorized": []},
    )


async def categorize_chunk(
    state: MergeEventsState,
    config: RunnableConfig,
) -> Command[Literal["categorize_chunk", "merge_categorizations"]]:
    chunks = state.get("chunked_events", [])
    done = state.get("chunked_events_categorized", [])

    if len(done) >= len(chunks):
        # all chunks done → move to merge
        return Command(goto="merge_categorizations")

    # take next chunk
    next_chunk = chunks[len(done)]
    prompt = categorize_events_prompt.format(events=next_chunk)

    structured_llm = create_structured_model(
        config=config, class_name=CategoriesWithEvents
    )
    response = await structured_llm.ainvoke(prompt)

    return Command(
        goto="categorize_chunk",  # loop until all chunks processed
        update={"chunked_events_categorized": done + [response]},
    )


async def merge_categorizations(
    state: MergeEventsState,
) -> Command[Literal["combine_new_and_original_events"]]:
    results = state.get("chunked_events_categorized", [])

    merged = EventService.merge_categorized_events(results)

    return Command(
        goto="combine_new_and_original_events",
        update={"extracted_events_categorized": merged},
    )


async def combine_new_and_original_events(
    state: MergeEventsState, config: RunnableConfig
) -> Command:
    """Merge original and new events for each category using an LLM."""
    print("Combining new and original events...")

    existing_events_raw = state.get(
        "existing_events",
        CategoriesWithEvents(early="", personal="", career="", legacy=""),
    )
    new_events_raw = state.get(
        "extracted_events_categorized",
        CategoriesWithEvents(early="", personal="", career="", legacy=""),
    )

    # Convert to proper Pydantic models if they're dicts
    existing_events = ensure_categories_with_events(existing_events_raw)
    new_events = ensure_categories_with_events(new_events_raw)

    if not new_events:
        print("No new events found. Keeping existing events.")
        return Command(goto="__end__", update={"existing_events": existing_events})

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
        merge_tasks.append(
            (category, create_structured_model(config=config).ainvoke(prompt))
        )

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
    return Command(goto="__end__", update={"existing_events": final_merged_output})


merge_events_graph_builder = StateGraph(
    MergeEventsState, input_schema=InputMergeEventsState, config_schema=Configuration
)

merge_events_graph_builder.add_node(
    "combine_new_and_original_events", combine_new_and_original_events
)
merge_events_graph_builder.add_node("split_events", split_events)
merge_events_graph_builder.add_node("categorize_chunk", categorize_chunk)
merge_events_graph_builder.add_node("merge_categorizations", merge_categorizations)

merge_events_graph_builder.add_edge(START, "split_events")

def get_langfuse_handler():
    from langfuse.langchain import CallbackHandler
    return CallbackHandler()

merge_events_app = merge_events_graph_builder.compile().with_config(
    {"callbacks": [get_langfuse_handler()]}
)
