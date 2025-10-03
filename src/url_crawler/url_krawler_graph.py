import random
from typing import Literal, TypedDict

from langfuse.langchain import CallbackHandler
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import Command
from src.configuration import Configuration
from src.url_crawler.utils import url_crawl

config = Configuration()
MAX_CONTENT_LENGTH = config.max_content_length


class InputUrlCrawlerState(TypedDict):
    url: str
    research_question: str


class UrlCrawlerState(InputUrlCrawlerState):
    raw_scraped_content: str


class OutputUrlCrawlerState(UrlCrawlerState):
    extracted_events: str
    raw_scraped_content: str


async def scrape_content(state: UrlCrawlerState) -> Command[Literal["__end__"]]:
    """Scrapes URL content and returns it without any processing."""
    url = state.get("url", "")
    
    content = await url_crawl(url)
    
    if len(content) > MAX_CONTENT_LENGTH:
        # At random start to get diverse content
        start_index = random.randint(0, len(content) - MAX_CONTENT_LENGTH)
        content = content[start_index : start_index + MAX_CONTENT_LENGTH]
    
    return Command(
        goto=END,
        update={
            "raw_scraped_content": content,
            "extracted_events": content,  # For compatibility with existing interface
        },
    )


builder = StateGraph(
    UrlCrawlerState,
    input_schema=InputUrlCrawlerState,
    output_schema=OutputUrlCrawlerState,
    config_schema=Configuration,
)

builder.add_node("scrape_content", scrape_content)
builder.add_edge(START, "scrape_content")


def get_langfuse_handler():
    return CallbackHandler()


url_crawler_app = builder.compile().with_config({"callbacks": [get_langfuse_handler()]})