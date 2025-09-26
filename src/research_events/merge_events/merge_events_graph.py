import asyncio
from typing import Literal, TypedDict

from langgraph.graph import START, StateGraph
from langgraph.graph.state import Command
from pydantic import BaseModel, Field
from src.llm_service import model_for_structured


class CategoriesWithEvents(BaseModel):
    early: str = Field(
        default="",
        description="Covers childhood, upbringing, family, education, and early influences that shaped the author.",
    )
    personal: str = Field(
        default="",
        description="Focuses on relationships, friendships, family life, places of residence, and notable personal traits or beliefs.",
    )
    career: str = Field(
        default="",
        description="Details their professional journey: first steps into writing, major publications, collaborations, recurring themes, style, and significant milestones.",
    )
    legacy: str = Field(
        default="",
        description="Explains how their work was received, awards or recognition, cultural/literary impact, influence on other authors, and how they are remembered today.",
    )


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


MERGE_EVENTS_TEMPLATE = """You are a helpful assistant that will merge two lists of events: original events and new events.
Analyze if any events can be combined or if they are duplicates.
The final output should be a single, clean, consolidated list of all events for the given category.

<Rules>
- Combine the information into a single coherent text.
- Do not omit any details from either the original or new events.
- Format the final list as a single string, with each event on a new line, starting with a bullet point (e.g., '- Event details.').
</Rules>

<Events>
{events_text}
</Events>

<Output>
Provide the merged list of events as a single string with bullet points. Return only the list of events, with no additional commentary.
</Output>"""


async def combine_new_and_original_events(
    state: MergeEventsState,
) -> Command:
    """Combines new and original events for each category, merges them using an LLM,
    and updates the state with a new CategoriesWithEvents object.
    """
    print("Combining new and original events...")

    # FIX 1: Correctly handle Pydantic models and potential None values from state.
    # Create default empty instances if they don't exist.
    original_events = state.get(
        "original_events",
        CategoriesWithEvents(early="", personal="", career="", legacy=""),
    )
    extracted_events_in_categories = state.get(
        "extracted_events_in_categories",
        CategoriesWithEvents(early="", personal="", career="", legacy=""),
    )

    if not extracted_events_in_categories:
        print("Warning: 'extracted_events_in_categories' is missing. Aborting merge.")
        # If there are no new events, the merged events are just the original ones.
        return Command(goto="__end__", update={"merged_events": original_events})

    # IMPROVEMENT (SST): Dynamically get category names from the Pydantic model.
    # This is the single source of truth.
    categories = CategoriesWithEvents.model_fields.keys()
    merge_tasks = []

    for category in categories:
        # FIX 2: Use `getattr` to safely access attributes from the Pydantic models.
        original_text = getattr(original_events, category, "").strip()
        new_text = getattr(extracted_events_in_categories, category, "").strip()

        # Skip the LLM call if there's nothing to merge for this category.
        if not original_text and not new_text:
            continue

        # If one is empty, no need for an LLM to "merge". We can just combine them.
        if not original_text:
            combined_text_for_llm = f"New events:\n{new_text}"
        elif not new_text:
            # If there are no new events for this category, we can just keep the original.
            # However, we'll send it to the LLM to ensure consistent formatting (e.g., bullet points).
            combined_text_for_llm = f"Original events:\n{original_text}"
        else:
            combined_text_for_llm = (
                f"Original events:\n{original_text}\n\nNew events:\n{new_text}"
            )

        prompt = MERGE_EVENTS_TEMPLATE.format(events_text=combined_text_for_llm)

        # Append the category and the awaitable coroutine to the task list.
        merge_tasks.append((category, model_for_structured.ainvoke(prompt)))

    # Run all LLM calls concurrently for efficiency.
    final_merged_dict = {}
    if merge_tasks:
        task_coroutines = [task[1] for task in merge_tasks]
        task_categories = [task[0] for task in merge_tasks]

        responses = await asyncio.gather(*task_coroutines)

        # Map the string results back to their categories in a dictionary.
        for i, response in enumerate(responses):
            category_key = task_categories[i]
            # The model's output content is a string.
            final_merged_dict[category_key] = response.content

    # FIX 3: Convert the final dictionary back into a Pydantic model instance.
    # This ensures the output type matches the state's `merged_events: CategoriesWithEvents`.
    final_merged_output = CategoriesWithEvents(**final_merged_dict)

    print("Finished merging events.")
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
