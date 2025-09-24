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
) -> Command[Literal["process_urls"]]:
    """Find the urls for the prompt"""
    prompt = state.get("prompt", "")
    print("events", state.get("events", []))

    if not prompt:
        raise ValueError("Prompt is required")

    ### call to tavily/duck duck go
    # urls = model.invoke(prompt)

    urls = [
        "https://en.wikipedia.org/wiki/Henry_Miller",
        "https://www.britannica.com/biography/Henry-Miller",
    ]

    state["urls"] = urls
    return Command(goto="process_urls", update={"urls": urls})


async def process_urls(
    state: ResearchEventsState,
) -> Command[Literal["__end__"]]:
    """Loop through the urls and crawl them"""
    urls = state.get("urls", [])
    events = state.get("events", [])
    print("events", events)
    if not urls:
        return Command(goto="__end__", update={"events": events})
    url = urls.pop(0)

    for url in urls:
        # result = await url_crawler_graph.ainvoke(url)
        result = {
            "url_events_summarized": """
               Henry Valentine Miller was born at his family's home, 450 East 85th Street, in the Yorkville section of Manhattan, New York City, U.S. He was the son of Lutheran German parents, Louise Marie (Neiting) and tailor Heinrich Miller.


Miller attended Eastern District High School in Williamsburg, Brooklyn, after finishing elementary school


While he was a socialist, his "quondam idol" was the black Socialist Hubert Harrison


Miller married his first wife, Beatrice Sylvas Wickens, in 1917;[11] their divorce was granted on December 21, 1923.[12] Together they had a daughter, Barbara, born in 1919


            """
        }
        url_events_summarized = result["url_events_summarized"]

        events = await merge_events_graph.ainvoke(
            {"original_events": events, "url_events_summarized": url_events_summarized}
        )
        # events = url_events_summarized

    return Command(goto="__end__", update={"events": events})


research_events_builder = StateGraph(
    ResearchEventsState,
    input_schema=InputResearchEventsState,
    output_schema=ResearchEventsState,
)

research_events_builder.add_node("url_finder", url_finder)
research_events_builder.add_node("process_urls", process_urls)
research_events_builder.add_edge(START, "url_finder")
research_events_graph = research_events_builder.compile()
