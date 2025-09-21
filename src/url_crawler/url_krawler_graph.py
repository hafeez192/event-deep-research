from typing import Literal, TypedDict

from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field

from src.url_crawler.prompts import EXTRACT_EVENTS_PROMPT
from src.url_crawler.utils import (
    chunk_text_by_tokens,
    count_tokens,
    url_crawl,
)
from src.utils import model_for_tools


class RelevantChunk(BaseModel):
    """Use this when the VAST MAJORITY (e.g., >80%) of the chunk describes significant
    personal life events of the historical figure. The entire chunk can be kept.
    """

    explanation: str = Field(
        description="A short explanation of why the entire chunk is relevant to the person's life story."
    )


class PartialChunk(BaseModel):
    """Use this when the chunk is a MIX of personal life events and irrelevant details
    (like plot summaries of their work, literary criticism, or general historical context).
    You will need to extract ONLY the parts about their life.
    """

    relevant_content: str = Field(
        description="An extraction of ALL sentences or phrases describing personal life events. Combine them into a coherent paragraph. Omit all work-related content."
    )
    explanation: str = Field(
        description="A short explanation of what was kept (life events) and what was discarded (e.g., work details)."
    )


class IrrelevantChunk(BaseModel):
    """Use this when the chunk is ENTIRELY about the person's works, literary analysis,
    references to them after their death, or trivial details with no biographical importance.
    """

    explanation: str = Field(
        description="A short explanation of why the chunk is irrelevant (e.g., 'Focuses only on literary criticism of their book.')."
    )


class InputUrlCrawlerState(TypedDict):
    url: str
    historical_figure: str


class ChunkWithCategory(TypedDict):
    content: str
    category: str
    explanation: str
    origianl_chunk: str


class UrlCrawlerState(InputUrlCrawlerState):
    content: str
    chunks: list[str]
    events: str
    chunks_with_categories: list[ChunkWithCategory]


## Build the nodes to do the folloing.
# 1. url is received and all the content is scraped using markdown/html
# 2. the content is divided into small chunks separated by tokens. Or maybe separated by h2 html tags??
# 3. From the chunks, make it able to separate them into three different types of chunks
# 1. They are about biography of historical figure, all of them should be included.
# 2. Just a small part of them are about the biography of person, just this part should be included. Discard all events that happened after it's death.
# 3. They don't have anything that can be included to the biography.

# Make it clear which content is included, these are events that happened to the person and are relevant. to it's biography.
# 4. Extract from every chunks multiple events about the life of the person, at the end mix all of these events together.
# 5. Return all of these events in a single string of contnet, without structuring.


async def scrape_content(
    state: UrlCrawlerState,
) -> Command[Literal["divide_content_into_chunks"]]:
    url = state.get("url", "")

    print(f"Scraping content for URL: {url}")
    content = await url_crawl(url)

    return Command(goto="divide_content_into_chunks", update={"content": content})


async def divide_content_into_chunks(
    state: UrlCrawlerState,
) -> Command[Literal["extract_events_from_chunks"]]:
    content = state.get("content", "")

    print("Total token size: ", count_tokens(content))
    chunks = chunk_text_by_tokens(content, chunk_size=1000, overlap_size=20)
    return Command(goto="extract_events_from_chunks", update={"chunks": chunks})


async def extract_events_from_chunks(
    state: UrlCrawlerState,
) -> Command[Literal["merge_events"]]:
    historical_figure = state.get("historical_figure", "")
    chunks = state.get("chunks", [])

    tools = [tool(RelevantChunk), tool(PartialChunk), tool(IrrelevantChunk)]
    model_tools = model_for_tools.bind_tools(tools)

    print(f"Extracting events from {len(chunks)} chunks")

    # first_two_chunks = chunks[:2]
    chunks_with_categories = []
    for chunk in chunks:
        prompt = EXTRACT_EVENTS_PROMPT.format(
            historical_figure=historical_figure, text_chunk=chunk
        )
        print("Extracting chunk ", chunk[0:10])
        response = await model_tools.ainvoke(prompt)

        tool_call_name = ""
        if response.tool_calls:
            tool_call_name = response.tool_calls[0]["name"]
        else:
            print("No tool calls found in response: ", response)
            chunks_with_categories.append({"content": chunk, "category": "UNKNOWN"})
            continue

        tool_call_args = response.tool_calls[0]["args"]
        explanation = tool_call_args["explanation"]
        if tool_call_name == "RelevantChunk":
            chunks_with_categories.append(
                {
                    "content": chunk,
                    "category": tool_call_name,
                    "explanation": explanation,
                    "origianl_chunk": chunk,
                }
            )
        elif tool_call_name == "PartialChunk":
            relevant_content = tool_call_args["relevant_content"]
            chunks_with_categories.append(
                {
                    "content": relevant_content,
                    "category": tool_call_name,
                    "explanation": explanation,
                    "origianl_chunk": chunk,
                }
            )
        elif tool_call_name == "IrrelevantChunk":
            explanation = tool_call_args["explanation"]
            chunks_with_categories.append(
                {
                    "content": "",
                    "category": tool_call_name,
                    "explanation": explanation,
                    "origianl_chunk": chunk,
                }
            )
        else:
            print("Invalid response: ", response)
            chunks_with_categories.append({"content": chunk, "category": "UNKNOWN"})
            continue

    return Command(
        goto="merge_events", update={"chunks_with_categories": chunks_with_categories}
    )


def merge_events(state: UrlCrawlerState) -> Command[Literal["__end__"]]:
    chunks_with_categories = state.get("chunks_with_categories", [])
    events = ""
    for chunk_with_category in chunks_with_categories:
        events += chunk_with_category["content"]
    return Command(goto=END, update={"events": events})


# How many nodes to build.
# 1. Scrape the content
# 2. Divide the content into chunks
# 3. Separate the chunks into three different types of chunks
# 4. Extract the events from the chunks
# 5. Return the events


builder = StateGraph(UrlCrawlerState, input_schema=InputUrlCrawlerState)

builder.add_node("scrape_content", scrape_content)
builder.add_node("divide_content_into_chunks", divide_content_into_chunks)
builder.add_node("extract_events_from_chunks", extract_events_from_chunks)
builder.add_node("merge_events", merge_events)
# builder.add_node("return_events", return_events)
builder.add_edge(START, "scrape_content")

url_crawler_graph = builder.compile()
