from typing import Literal, TypedDict

from langgraph.graph import START, StateGraph
from langgraph.types import Command
from src.research_events.merge_events.merge_events_graph import merge_events_app
from src.research_events.state import CategoriesWithEvents
from src.url_crawler.url_krawler_graph import url_crawler_app


class InputResearchEventsState(TypedDict):
    prompt: str
    events: CategoriesWithEvents


class ResearchEventsState(InputResearchEventsState):
    urls: list[str]
    # Add this temporary field
    merged_events: CategoriesWithEvents
    events_extracted_from_url: str


def url_finder(
    state: ResearchEventsState,
) -> Command[Literal["should_process_url_router"]]:
    """Find the urls for the prompt"""
    prompt = state.get("prompt", "")

    if not prompt:
        raise ValueError("Prompt is required")

    ### call to tavily/duck duck go
    # urls = model.invoke(prompt)

    urls = [
        # "https://en.wikipedia.org/wiki/Henry_Miller",
        "https://www.britannica.com/biography/Henry-Miller",
    ]

    return Command(goto="should_process_url_router", update={"urls": urls})


def should_process_url_router(
    state: ResearchEventsState,
) -> Command[Literal["crawl_url", "__end__"]]:
    if state.get("urls"):
        print(f"URLs remaining: {len(state['urls'])}. Routing to crawl.")
        return Command(goto="crawl_url")
    else:
        print("No URLs remaining. Routing to __end__.")
        # Otherwise, end the graph execution
        return Command(
            goto="__end__",
        )


async def crawl_url(
    state: ResearchEventsState,
) -> Command[Literal["merge_events_and_update"]]:
    """Crawls the next URL and updates the temporary state with new events."""
    urls = state["urls"]
    url_to_process = urls[0]  # Always process the first one

    # Invoke the crawler subgraph
    result = await url_crawler_app.ainvoke({"url": url_to_process})
    events_from_url = result["events"]

    # Go to the merge node, updating the state with the extracted events
    return Command(
        goto="merge_events_and_update",
        update={"events_extracted_from_url": events_from_url},
    )


async def merge_events_and_update(
    state: ResearchEventsState,
) -> Command[Literal["should_process_url_router"]]:
    """Merges new events, removes the processed URL, and loops back to the router."""
    original_events = state.get("events", CategoriesWithEvents())
    new_events = state.get("events_extracted_from_url", "")

    # Invoke the merge subgraph
    merged_events = await merge_events_app.ainvoke(
        {
            "original_events": original_events,
            "events_extracted_from_url": new_events,
        }
    )

    remaining_urls = state["urls"][1:]

    # Go back to the router to check for more URLs
    return Command(
        goto="should_process_url_router",
        update={
            "events": merged_events,
            "urls": remaining_urls,
            "events_extracted_from_url": [],  # Clear the temporary state
        },
    )


research_events_builder = StateGraph(
    ResearchEventsState,
    input_schema=InputResearchEventsState,
    output_schema=ResearchEventsState,
)

# Add all the nodes to the graph
research_events_builder.add_node("url_finder", url_finder)
research_events_builder.add_node("should_process_url_router", should_process_url_router)
research_events_builder.add_node("crawl_url", crawl_url)
research_events_builder.add_node("merge_events_and_update", merge_events_and_update)

# Set the entry point
research_events_builder.add_edge(START, "url_finder")

research_events_app = research_events_builder.compile()
