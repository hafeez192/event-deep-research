from typing import Literal, TypedDict

from langgraph.graph import START, StateGraph
from langgraph.types import Command
from src.research_events.merge_events.merge_events_graph import merge_events_graph
from src.state import ChronologyEvent


class InputResearchEventsState(TypedDict):
    prompt: str
    events: list[ChronologyEvent]


# Example
# {
#     "prompt": "Biography ofHenry Miller",
#     "events": []
# }


class ResearchEventsState(InputResearchEventsState):
    urls: list[str]


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

        events = await merge_events_graph.ainvoke(
            {"events": events, "new_events": new_events}
        )
        # events = new_events

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
