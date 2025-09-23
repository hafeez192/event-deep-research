from typing import Literal, TypedDict

from langgraph.graph import START, StateGraph
from langgraph.types import Command
from src.llm_service import model_for_structured, model_for_tools
from src.state import Chronology, ChronologyEvent


class InputResearchEventsState(TypedDict):
    prompt: str
    events: list[ChronologyEvent]


class ResearchEventsState(InputResearchEventsState):
    urls: list[str]


class InputMergeEventsState(TypedDict):
    original_events: list[ChronologyEvent]
    new_events: str


# Example
{
    "original_events": [
        {
            "id": "5875781",
            "name": "Birth of Henry Miller",
            "description": "Born in New York City",
            "date": "",
            "location": "New York City",
        },
        {
            "id": "9887595",
            "name": "Moved to Paris",
            "description": "Moved to Paris in 1930",
            "date": "1930",
            "location": "Paris",
        },
    ],
    "new_events": "Birth of Henry Miller in 1891 in New York City",
}


class MergeEventsState(InputMergeEventsState):
    merged_events: str
    structured_events: list[ChronologyEvent]


async def merge_events(
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

    merged_events = await model_for_tools.ainvoke(prompt)

    return Command(
        goto="structure_events", update={"merged_events": merged_events.content}
    )


async def structure_events(state: MergeEventsState) -> Command[Literal["__end__"]]:
    """Structure the events"""
    merged_events = state.get("merged_events", "")

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
    {merged_events}
    ----
    </Chronological Events List>

    CRITICAL: You must only return the structured JSON output. Do not add any commentary, greetings, or explanations before or after the JSON.
    """

    prompt = structure_events_prompt.format(merged_events=merged_events)
    print(prompt)
    structured_llm = model_for_structured.with_structured_output(Chronology)

    structured_events = await structured_llm.ainvoke(prompt)
    # for event in structured_events.events:
    #     event.id = str(uuid.uuid4())

    return Command(goto="__end__", update={"structured_events": structured_events})


merge_events_graph_builder = StateGraph(
    MergeEventsState,
    input_schema=InputMergeEventsState,
)

merge_events_graph_builder.add_node("merge_events", merge_events)
merge_events_graph_builder.add_node("structure_events", structure_events)
merge_events_graph_builder.add_edge(START, "merge_events")
merge_events_graph = merge_events_graph_builder.compile()


async def url_finder(
    state: ResearchEventsState,
) -> Command[Literal["loop_url_crawler"]]:
    """Find the urls for the prompt"""
    prompt = state.get("prompt", "")

    if not prompt:
        raise ValueError("Prompt is required")

    ### call to tavily/duck duck go
    # urls = model.invoke(prompt)

    urls = [
        "https://en.wikipedia.org/wiki/Henry_Miller",
        "https://www.britannica.com/biography/Henry-Miller",
    ]

    state["urls"] = urls
    return Command(goto="loop_url_crawler", update={"urls": urls})


async def loop_url_crawler(
    state: ResearchEventsState,
) -> Command[Literal["__end__"]]:
    """Loop through the urls and crawl them"""
    urls = state.get("urls", [])
    events = state.get("events", [])
    if not urls:
        return Command(goto="__end__", update={"events": events})
    url = urls.pop(0)

    for url in urls:
        # result = await url_crawler_graph.ainvoke(url)
        result = {
            "url_events": """
                - Birth of Henry Miller in 1891 in New York City
                - Moved to Paris in 1930
                - Wrote Tropic of Cancer in 1934
            """
        }
        new_events = result["url_events"]

        events = await merge_events_graph.ainvoke(events, new_events)

    return Command(goto="__end__", update={"events": events})


research_events_builder = StateGraph(
    ResearchEventsState,
    input_schema=InputResearchEventsState,
    output_schema=ResearchEventsState,
)

research_events_builder.add_node("url_finder", url_finder)
research_events_builder.add_node("loop_url_crawler", loop_url_crawler)
research_events_builder.add_edge(START, "url_finder")
research_events_graph = research_events_builder.compile()
