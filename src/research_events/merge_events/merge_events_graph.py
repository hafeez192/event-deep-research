from typing import Literal, TypedDict

from langgraph.graph import START, StateGraph
from langgraph.types import Command
from src.llm_service import model_for_structured, model_for_tools
from src.state import Chronology, ChronologyEvent


class InputMergeEventsState(TypedDict):
    original_events: list[ChronologyEvent]
    new_events: str


# Example
# {
#     "original_events": [
#         {
#             "id": "5875781",
#             "name": "Birth of Henry Miller",
#             "description": "Born in New York City",
#             "date": "",
#             "location": "New York City"
#         },
#         {
#             "id": "9887595",
#             "name": "Moved to Paris",
#             "description": "Moved to Paris in 1930",
#             "date": "1930",
#             "location": "Paris"
#         }
#     ],
#     "new_events": "Birth of Henry Miller in 1891 in New York City"
# }


class MergeEventsState(InputMergeEventsState):
    matched_events: str
    structured_events: list[ChronologyEvent]
    merged_events: list[ChronologyEvent]


async def match_events(
    state: MergeEventsState,
) -> Command[Literal["structure_events"]]:
    original_events = state.get("original_events", [])
    new_events = state.get("new_events", [])
    """Merge the events from the urls"""

    prompt = f"""
    Original events:
    {original_events}


    New Events:
    {new_events}


    Create a new list of matched events in the following format:
    Example:
    - Id: 5 Original: Birth of Henry Miller in 1891  New: Henry Miller was born in New York City    
    - Id: 6 Original: Wrote Tropic of Cancer in 1934  New: Henry Miller wrote Tropic of Cancer in 1934, this is a novel inspired by his life in Paris and includes references to many of his experiences.
    """

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
    1.  For the `id` field, use the SAME id already defined in the merged events. 
    2.  For the `name` field, create a short, descriptive title for the event (e.g., "Birth of Pablo Picasso").
    3.  For the `description` field, provide the clear and concise summary of what happened from the input text.
    4.  For the `date` field, populate `year`, `month`, and `day` whenever possible.
    5.  If the date is an estimate or a range (e.g., "circa 1912" or "Between 1920-1924"), you MUST capture that specific text in the `note` field of the date object, and provide your best estimate for the `year`.
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
    print(prompt)
    structured_llm = model_for_structured.with_structured_output(Chronology)

    chronology = await structured_llm.ainvoke(prompt)

    structured_events = chronology.events
    # for event in structured_events.events:
    #     event.id = str(uuid.uuid4())

    return Command(goto="merge_events", update={"structured_events": structured_events})


async def merge_events(state: MergeEventsState) -> Command[Literal["__end__"]]:
    """Merge the events"""
    structured_events = state.get("structured_events", [])
    original_events = state.get("original_events", [])

    print(structured_events)
    if not structured_events:
        return Command(goto="__end__", update={"merged_events": original_events})
    structured_events_ids = [event.id for event in structured_events]

    merged_events = []
    for event in original_events:
        print("event", event)
        if event["id"] in structured_events_ids:
            # replace the event with the new one
            new_merged_event = structured_events[
                structured_events_ids.index(event["id"])
            ]
            merged_events.append(new_merged_event)
        else:
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
