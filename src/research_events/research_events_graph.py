from typing import Literal, TypedDict

from langgraph.graph import START, StateGraph
from langgraph.types import Command
from src.research_events.merge_events.merge_events_graph import merge_events_app
from src.state import ChronologyEvent
from src.url_crawler.url_krawler_graph import url_crawler_app


class InputResearchEventsState(TypedDict):
    prompt: str
    events: list[ChronologyEvent]


class ResearchEventsState(InputResearchEventsState):
    urls: list[str]
    # Add this temporary field
    newly_extracted_events: list[ChronologyEvent]


def should_process_url_router(
    state: ResearchEventsState,
) -> Command[Literal["crawl_url", "__end__"]]:
    """Checks if URLs are available and routes to the crawler or ends the graph."""
    print("---[ROUTER: Checking for URLs]---")
    if state.get("urls"):
        print(f"URLs remaining: {len(state['urls'])}. Routing to crawl.")
        # If URLs exist, go to the crawl_url node
        return Command(goto="crawl_url")
    else:
        print("No URLs remaining. Routing to __end__.")
        # Otherwise, end the graph execution
        return Command(goto="__end__")


async def crawl_url(
    state: ResearchEventsState,
) -> Command[Literal["merge_events_and_update"]]:
    """Crawls the next URL and updates the temporary state with new events."""
    print("---[NODE: Crawling URL]---")
    urls = state["urls"]
    url_to_process = urls[0]  # Always process the first one

    print(f"Crawling: {url_to_process}")

    # Invoke the crawler subgraph
    result = await url_crawler_app.ainvoke({"url": url_to_process})
    events_from_url = result["events"]
    print(f"Extracted {len(events_from_url)} events from {url_to_process}")

    # Go to the merge node, updating the state with the extracted events
    return Command(
        goto="merge_events_and_update",
        update={"newly_extracted_events": events_from_url},
    )


def url_finder(
    state: ResearchEventsState,
) -> Command[Literal["should_process_url_router"]]:
    """Find the urls for the prompt"""
    prompt = state.get("prompt", "")
    print("events", state.get("events", []))

    if not prompt:
        raise ValueError("Prompt is required")

    ### call to tavily/duck duck go
    # urls = model.invoke(prompt)

    urls = [
        "https://en.wikipedia.org/wiki/Henry_Miller",
        # "https://www.britannica.com/biography/Henry-Miller",
    ]

    return Command(goto="should_process_url_router", update={"urls": urls})


async def merge_events_and_update(
    state: ResearchEventsState,
) -> Command[Literal["should_process_url_router"]]:
    """Merges new events, removes the processed URL, and loops back to the router."""
    print("---[NODE: Merging Events]---")
    current_events = state.get("events", [])
    new_events = state.get("newly_extracted_events", [])

    print(
        f"Merging {len(new_events)} new events with {len(current_events)} existing events."
    )

    # Invoke the merge subgraph
    merged_events = await merge_events_app.ainvoke(
        {
            "original_events": current_events,
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
            "newly_extracted_events": [],  # Clear the temporary state
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
