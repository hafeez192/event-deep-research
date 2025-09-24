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
    """Node 2: Takes the processed events from the LLM, assigns unique IDs to
    new events, and produces the final merged list.
    """
    matched_events = state.get("matched_events", [])

    if not matched_events:
        # If the LLM returned nothing, we can just end with the original events
        # or an empty list, depending on requirements.
        return Command(
            goto="__end__", update={"merged_events": state.get("original_events", [])}
        )

    final_events = []
    for event in matched_events:
        # The LLM has already done the hard work of merging and structuring.
        # We just need to handle the null IDs.
        if event.id is None and event.status == "new":
            event.id = str(uuid4())
        final_events.append(event)

    # The final, clean list is now ready.
    return Command(goto="__end__", update={"merged_events": final_events})


merge_events_graph_builder = StateGraph(
    MergeEventsState,
    input_schema=InputMergeEventsState,
)

merge_events_graph_builder.add_node("match_events", match_events)
merge_events_graph_builder.add_node("finalize_merged_events", finalize_merged_events)
merge_events_graph_builder.add_edge(START, "match_events")
merge_events_graph = merge_events_graph_builder.compile()
