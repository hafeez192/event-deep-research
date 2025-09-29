from typing import Literal, TypedDict
from urllib.parse import urlparse

from langchain_tavily import TavilySearch
from langgraph.graph import START, StateGraph
from langgraph.types import Command
from src.research_events.merge_events.merge_events_graph import merge_events_app
from src.state import CategoriesWithEvents
from src.url_crawler.url_krawler_graph import url_crawler_app


class InputResearchEventsState(TypedDict):
    research_question: str
    existing_events: CategoriesWithEvents
    used_domains: list[str]


class ResearchEventsState(InputResearchEventsState):
    urls: list[str]
    # Add this temporary field
    raw_extracted_events: str


class OutputResearchEventsState(TypedDict):
    existing_events: CategoriesWithEvents
    used_domains: list[str]


def url_finder(
    state: ResearchEventsState,
) -> Command[Literal["should_process_url_router"]]:
    """Find the urls for the research_question"""
    print("state", state)
    research_question = state.get("research_question", "")
    used_domains = state.get("used_domains", [])

    if not research_question:
        raise ValueError("research_question is required")

    print("used_domains", used_domains)

    # return Command(
    #     goto=END,
    #     update={
    #         "existing_events": CategoriesWithEvents(
    #             early="test", personal="test", career="test", legacy="test"
    #         ),
    #         "used_domains": ["en.wikipedia.org", "www.britannica.com"],
    #     },
    # )

    tool = TavilySearch(
        max_results=2,
        topic="general",
        include_answer=False,
        include_raw_content=False,
        include_images=False,
        include_image_descriptions=False,
        include_domains=None,
        exclude_domains=used_domains,
    )

    result = tool.invoke({"query": research_question})

    urls = [result["url"] for result in result["results"]]

    ### call to tavily/duck duck go
    # urls = model.invoke(research_question)
    # urls = [
    #     "https://en.wikipedia.org/wiki/Henry_Miller",
    #     "https://www.britannica.com/biography/Henry-Miller",
    # ]

    return Command(goto="should_process_url_router", update={"urls": urls})


def updateUrlList(
    state: ResearchEventsState,
) -> tuple[list[str], list[str]]:
    # Pop the first URL (removes it from the list and returns it)
    url = state.get("urls", []).pop(0)

    # Extract domain safely
    domain = urlparse(url).netloc

    # Track used domains
    used_domains = state.get("used_domains", [])
    used_domains.append(domain)

    remaining_urls = state["urls"]  # Go back to the router to check for more URLs

    return remaining_urls, used_domains


def should_process_url_router(
    state: ResearchEventsState,
) -> Command[Literal["crawl_url", "__end__"]]:
    urls = state.get("urls", [])
    used_domains = state.get("used_domains", [])

    if urls and len(urls) > 0:
        domain = urlparse(urls[0]).netloc
        if domain in used_domains:
            # remove first url
            remaining_urls = urls[1:]
            return Command(
                goto="should_process_url_router",
                update={"urls": remaining_urls, "used_domains": used_domains},
            )

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

    # return Command(
    #     goto="merge_events_and_update",
    #     update={"raw_extracted_events": "raw_extracted_events mock"},
    # )

    # Invoke the crawler subgraph
    result = await url_crawler_app.ainvoke({"url": url_to_process})
    events_from_url = result["extracted_events"]

    # Go to the merge node, updating the state with the extracted events
    return Command(
        goto="merge_events_and_update",
        update={"raw_extracted_events": events_from_url},
    )


async def merge_events_and_update(
    state: ResearchEventsState,
) -> Command[Literal["should_process_url_router"]]:
    """Merges new events, removes the processed URL, and loops back to the router."""
    existing_events = state.get("existing_events", CategoriesWithEvents())
    new_events = state.get("raw_extracted_events", "")

    # Invoke the merge subgraph
    existing_events = await merge_events_app.ainvoke(
        {
            "existing_events": existing_events,
            "raw_extracted_events": new_events,
        }
    )

    remaining_urls, used_domains = updateUrlList(state)

    # Remaining URLs after removal
    return Command(
        goto="should_process_url_router",
        update={
            "existing_events": existing_events,
            "urls": remaining_urls,
            "used_domains": used_domains,
            "raw_extracted_events": "",  # Clear the temporary state
        },
    )


research_events_builder = StateGraph(
    ResearchEventsState,
    input_schema=InputResearchEventsState,
    output_schema=OutputResearchEventsState,
)

# Add all the nodes to the graph
research_events_builder.add_node("url_finder", url_finder)
research_events_builder.add_node("should_process_url_router", should_process_url_router)
research_events_builder.add_node("crawl_url", crawl_url)
research_events_builder.add_node("merge_events_and_update", merge_events_and_update)

# Set the entry point
research_events_builder.add_edge(START, "url_finder")

research_events_app = research_events_builder.compile()
