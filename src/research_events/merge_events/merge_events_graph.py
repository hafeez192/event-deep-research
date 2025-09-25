from typing import Literal
from uuid import uuid4

from langgraph.graph import START, StateGraph
from langgraph.types import Command
from src.llm_service import model_for_structured
from src.state import InputMergeEventsState, MatchEventsState, MergeEventsState

# Simplify original events
# extract just the name and id to match with the new events
# then merge the new events with the original events
# return the merged events


async def match_events(
    state: MergeEventsState,
) -> Command[Literal["combine_information"]]:
    original_events = state.get("original_events", [])
    url_events_summarized = state.get("url_events_summarized", [])

    simplified_original_events = [
        {"name": event["name"], "id": event["id"]} for event in original_events
    ]

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
        "id": "some_event_id",
        "status": "new", # or updated
        "description": "<description>", # This includes just the new information or a mix of both the new and the original information
        "location": "<location>",
        "date": {{ "year": <year>, "note": "<note>" }},
      }}
    ]

    <critical rules>
    DO NOT PUT THE SAME INFORMATION TWICE IN MULTIPLE EVENTS.
    INCLUDE ALL THE INFORMATION FROM THE NEW EVENTS
    </critical rules>
    """

    prompt = merge_events_prompt.format(
        original_events=simplified_original_events,
        url_events_summarized=url_events_summarized,
    )

    structured_llm = model_for_structured.with_structured_output(MatchEventsState)

    response = await structured_llm.ainvoke(prompt)

    return Command(
        goto="combine_information",
        update={"matched_events": response.matched_events},
    )


async def combine_information(
    state: MergeEventsState,
) -> Command[Literal["finalize_merged_events"]]:
    matched_events = state.get("matched_events", [])
    original_events = state.get("original_events", [])

    events_to_update = []
    new_events = []
    for matched_event in matched_events:
        if matched_event.status == "updated":
            print("matched_event", matched_event)
            original_event = next(
                (e for e in original_events if e["id"] == matched_event.id), None
            )
            if original_event:
                original_event["description"] = (
                    original_event["description"] + matched_event.description
                )
                events_to_update.append(original_event)

        if matched_event.status == "new":
            new_events.append(matched_event)

    print("events_to_update", len(events_to_update))
    print("events_to_update", events_to_update)
    prompt = """ 
    <Task>
    You will combine the new information with the description of the event. Your output must be a single, valid JSON array.    
    </Task>

    <Original Events>
    {original_events}
    </Original Events>

    <Output Format Example: JSON Array>
    [
      {{
        "id": "some_event_id",
        "description": "<description>", # This includes now both the new and the original information
        "location": "<location>",
        "date": {{ "year": <year>, "note": "<note>" }},
      }}
    ]
    """

    prompt = prompt.format(original_events=events_to_update)

    structured_llm = model_for_structured.with_structured_output(MatchEventsState)

    response = await structured_llm.ainvoke(prompt)
    combined_events = response.matched_events

    new_and_updated_events = combined_events + new_events

    return Command(
        goto="finalize_merged_events",
        update={"matched_events": new_and_updated_events},
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
    matched_events = state.get("matched_events", [])
    original_events = state.get(
        "original_events", []
    )  # We now need the original list of objects

    if not matched_events:
        # If the LLM returned nothing, the final list is just the original list.
        return Command(goto="__end__", update={"merged_events": original_events})

    # --- The New Merge Logic ---

    # 1. Create a dictionary of the LLM's updated events for quick look-up.
    #    The key is the event ID.
    updated_events_map = {
        event.id: event
        for event in matched_events
        if event.status == "updated" and event.id is not None
    }

    # 2. Separate the brand new events and assign them a unique ID.
    new_events = []
    for event in matched_events:
        if event.status == "new":
            event.id = str(uuid4())
            new_events.append(event)

    # 3. Build the final list by iterating through the original events.
    final_merged_list = []
    for original_event in original_events:
        # If this event's ID is in our map, it means the LLM updated it.
        # So, we append the *updated version*.
        print("original_event", original_event)
        if original_event["id"] in updated_events_map:
            final_merged_list.append(updated_events_map[original_event["id"]])
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
merge_events_graph_builder.add_node("combine_information", combine_information)
merge_events_graph_builder.add_node("finalize_merged_events", finalize_merged_events)
merge_events_graph_builder.add_edge(START, "match_events")
merge_events_graph = merge_events_graph_builder.compile()
