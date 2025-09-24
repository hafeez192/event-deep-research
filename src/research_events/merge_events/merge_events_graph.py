from typing import Literal, TypedDict
from uuid import uuid4

from langgraph.graph import START, StateGraph
from langgraph.types import Command
from src.llm_service import model_for_structured, model_for_tools
from src.state import Chronology, ChronologyEvent


class InputMergeEventsState(TypedDict):
    url_events_summarized: str
    original_events: list[ChronologyEvent]


class MergeEventsState(InputMergeEventsState):
    matched_events: str
    structured_events: list[ChronologyEvent]
    merged_events: list[ChronologyEvent]


async def match_events(
    state: MergeEventsState,
) -> Command[Literal["structure_events"]]:
    original_events = state.get("original_events", [])
    url_events_summarized = state.get("url_events_summarized", [])

    """Match the new events with the original events"""
    merge_events_prompt = """
    <Task>
    You will be given a list of original events and a list of new events. You must match the new events with the original events.
    Or add a new event if it can't be found on the original events.
    </Task>

    <Original Events>
    {original_events}
    </Original Events>

    <New Events>
    {url_events_summarized}
    </New Events>

    <Rules>
    KEEP THE ID FROM THE ORIGINAL EVENTS IF EXISTS.
    If there's a new event that is not in the original events, you must add it to the list WITHOUT an ID.
    </Rules>

    <Format>
    id: word1_word2 this and that happened on X year in Y location
    </Format>
    """

    prompt = merge_events_prompt.format(
        original_events=original_events, url_events_summarized=url_events_summarized
    )

    print("merge events pormpt", prompt)

    matched_events = await model_for_tools.ainvoke(prompt)

    return Command(
        goto="structure_events", update={"matched_events": matched_events.content}
    )


async def structure_events(state: MergeEventsState) -> Command[Literal["merge_events"]]:
    """Structure the events"""
    matched_events = state.get("matched_events", "")

    structure_events_prompt = """You are a data processing specialist. Your sole task is to convert a pre-cleaned, chronologically ordered list of life events into a structured JSON object.

    <Task>
    You will be given a list of events that is already de-duplicated and ordered. You must not change the order or content of the events. For each event in the list, you will extract its name, a detailed description, its date, and location, and format it as JSON.
    </Task>

    <Guidelines>
    1.  For the `id` field, use the SAME id already defined in the merged events or create a new one that extremely briefy summarizes the event in lowercase and _ instead of space.
    2.  For the `name` field, create a short, descriptive title for the event .
    3.  For the `description` field, provide the clear and concise summary of what happened from the input text.
    4.  For the `date` field, populate `year`, `month`, and `day` whenever possible.
    5.  If the date is an estimate or a range (e.g., "circa YYYY" or "Between YYYY-YYYY"), you MUST capture that specific text in the `note` field of the date object, and provide your best estimate for the `year`.
    </Guidelines>

    <Chronological Events List>
    ----
    Merged Events:
    {matched_events}
    ----
    </Chronological Events List>

    CRITICAL: You must only return the structured JSON output. Do not add any commentary, greetings, or explanations before or after the JSON.
    """

    prompt = structure_events_prompt.format(matched_events=matched_events)
    structured_llm = model_for_structured.with_structured_output(Chronology)

    chronology = await structured_llm.ainvoke(prompt)

    structured_events = chronology.events
    for event in structured_events:
        if event.id is None:
            event.id = str(uuid4())  # default id

    return Command(goto="merge_events", update={"structured_events": structured_events})


async def merge_events(state: MergeEventsState) -> Command[Literal["__end__"]]:
    """Merge the events"""
    structured_events = state.get("structured_events", [])
    original_events = state.get("original_events", [])

    if not structured_events:
        return Command(goto="__end__", update={"merged_events": original_events})
    structured_events_ids = [event.id for event in structured_events]

    merged_events = []
    # Replaces or let's the old event be added if the id is not in the new or matched structured events
    for event in original_events:
        print("event", event)
        if id in structured_events_ids:
            # replace the event with the new one
            new_merged_event = structured_events[structured_events_ids.index(event.id)]
            merged_events.append(new_merged_event)
        else:
            # Add the old event
            merged_events.append(event)

    return Command(goto="__end__", update={"merged_events": merged_events})


merge_events_graph_builder = StateGraph(
    MergeEventsState,
    input_schema=InputMergeEventsState,
)

merge_events_graph_builder.add_node("match_events", match_events)
merge_events_graph_builder.add_node("structure_events", structure_events)
merge_events_graph_builder.add_node("merge_events", merge_events)
merge_events_graph_builder.add_edge(START, "match_events")
merge_events_graph = merge_events_graph_builder.compile()
