from typing import Literal
from uuid import uuid4

from langgraph.graph import START, StateGraph
from langgraph.types import Command
from src.llm_service import model_for_structured
from src.state import InputMergeEventsState, MatchEventsState, MergeEventsState


async def match_events(
    state: MergeEventsState,
) -> Command[Literal["finalize_merged_events"]]:
    original_events = state.get("original_events", [])
    url_events_summarized = state.get("url_events_summarized", [])

    """Match the new events with the original events"""
    merge_events_prompt = """
    <Task>
    You will merge a list of <New Events> into a list of <Original Events>. Your output must be a single, valid JSON array.
    </Task>

    <Instructions>
    1.  **Match & Update**: For each new event, find a matching original event based on its real-world meaning (not exact wording). If found, update the event's data with the richer details from the new event. **Keep the original `id`** and add `"status": "updated"`.

    2.  **Add New**: If a new event is unique and has no match in the original list, add it as a new object. Use **`"id": null`** and add `"status": "new"`.

    3.  **Final List**: The final JSON array should only contain entries corresponding to the <New Events>. Discard any original events that were not matched. Merge any duplicate new events into a single entry.
    </Instructions>

    <Original Events>
    {original_events}
    </Original Events>

    <New Events>
    {url_events_summarized}
    </New Events>

    <Output Format Example: JSON Array>
    [
      {{
        "id": "henry_miller_born",
        "status": "updated",
        "name": "Henry Valentine Miller was born",
        "description": "Henry Valentine Miller was born at his family's home, 450 East 85th Street...",
        "date": {{ "year": 1891, "note": "" }},
        "location": "Manhattan, New York City"
      }},
      {{
        "id": "henry_miller_wrote_tropic_of_cancer",
        "status": "new",
        "name": "Henry Miller wrote Tropic of Cancer",
        "description": "In 1934, Henry Miller's novel 'Tropic of Cancer' was published in Paris.",
        "date": {{ "year": 1934, "note": "" }},
        "location": "Paris"
      }}
    ]
    """

    prompt = merge_events_prompt.format(
        original_events=original_events, url_events_summarized=url_events_summarized
    )

    print("merge events pormpt", prompt)

    structured_llm = model_for_structured.with_structured_output(MatchEventsState)

    response = await structured_llm.ainvoke(prompt)

    return Command(
        goto="finalize_merged_events",
        update={"matched_events": response.matched_events},
    )


async def finalize_merged_events(
    state: MergeEventsState,
) -> Command[Literal["__end__"]]:
    """Node 2: Takes the processed events from the LLM and correctly merges them
    with the original events list.

    - Updates events that were matched by the LLM.
    - Keeps original events that were not matched.
    - Appends brand new events found by the LLM.
    """
    llm_processed_events = state.get("llm_processed_events", [])
    original_events = state.get(
        "original_events", []
    )  # We now need the original list of objects

    if not llm_processed_events:
        # If the LLM returned nothing, the final list is just the original list.
        return Command(goto="__end__", update={"merged_events": original_events})

    # --- The New Merge Logic ---

    # 1. Create a dictionary of the LLM's updated events for quick look-up.
    #    The key is the event ID.
    updated_events_map = {
        event.id: event
        for event in llm_processed_events
        if event.status == "updated" and event.id is not None
    }

    # 2. Separate the brand new events and assign them a unique ID.
    new_events = []
    for event in llm_processed_events:
        if event.status == "new":
            event.id = str(uuid4())
            new_events.append(event)

    # 3. Build the final list by iterating through the original events.
    final_merged_list = []
    for original_event in original_events:
        # If this event's ID is in our map, it means the LLM updated it.
        # So, we append the *updated version*.
        if original_event.id in updated_events_map:
            final_merged_list.append(updated_events_map[original_event.id])
        # Otherwise, this event was untouched by the new info, so we keep it as is.
        else:
            final_merged_list.append(original_event)

    # 4. Finally, add the brand new events to the end of the list.
    final_merged_list.extend(new_events)

    return Command(goto="__end__", update={"merged_events": final_merged_list})


merge_events_graph_builder = StateGraph(
    MergeEventsState,
    input_schema=InputMergeEventsState,
)

merge_events_graph_builder.add_node("match_events", match_events)
merge_events_graph_builder.add_node("finalize_merged_events", finalize_merged_events)
merge_events_graph_builder.add_edge(START, "match_events")
merge_events_graph = merge_events_graph_builder.compile()
