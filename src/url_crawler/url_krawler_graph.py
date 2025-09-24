from typing import Literal, TypedDict

from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field
from src.llm_service import model_for_big_queries, model_for_tools
from src.url_crawler.prompts import EXTRACT_EVENTS_PROMPT, create_event_list_prompt
from src.url_crawler.utils import (
    chunk_text_by_tokens,
    url_crawl,
)


class RelevantChunk(BaseModel):
    """Use this when the VAST MAJORITY (e.g., >80%) of the chunk describes significant
    personal life events of the historical figure. The entire chunk can be kept.
    """


class PartialChunk(BaseModel):
    """Use this when the chunk is a MIX of personal life events and irrelevant details
    (like plot summaries of their work, literary criticism, or general historical context).
    You will need to extract ONLY the parts about their life.
    """

    relevant_content: str = Field(
        description="An extraction of ALL sentences or phrases describing personal life events. Combine them into a coherent paragraph. Omit all work-related content."
    )


class IrrelevantChunk(BaseModel):
    """Use this when the chunk is ENTIRELY about the person's works, literary analysis,
    references to them after their death, or trivial details with no biographical importance.
    """


class InputUrlCrawlerState(TypedDict):
    url: str
    historical_figure: str


class ChunkWithCategory(TypedDict):
    content: str
    category: str
    origianl_chunk: str


class UrlCrawlerState(InputUrlCrawlerState):
    content: str
    chunks: list[str]
    events: str
    chunks_with_categories: list[ChunkWithCategory]


class OutputUrlCrawlerState(UrlCrawlerState):
    events: str
    content: str


async def scrape_content(
    state: UrlCrawlerState,
) -> Command[Literal["divide_and_extract_chunks"]]:
    url = state.get("url", "")

    print(f"Scraping content for URL: {url}")
    content = await url_crawl(url)

    return Command(goto="divide_and_extract_chunks", update={"content": content})


async def divide_and_extract_chunks(
    state: UrlCrawlerState,
) -> Command[Literal["create_event_list"]]:
    content = state.get("content", "")
    historical_figure = state.get("historical_figure", "")

    # 1. Chunks are divided into chunks by tokens
    chunks = chunk_text_by_tokens(content, chunk_size=1000, overlap_size=20)

    # 2. tools are binded to the model
    tools = [tool(RelevantChunk), tool(PartialChunk), tool(IrrelevantChunk)]
    model_tools = model_for_tools.bind_tools(tools)

    # 3. Chunks are analyzed and simplified.

    first_two_chunks = chunks[:2]
    chunks_with_categories = []
    for chunk in first_two_chunks:
        prompt = EXTRACT_EVENTS_PROMPT.format(
            historical_figure=historical_figure, text_chunk=chunk
        )
        response = await model_tools.ainvoke(prompt)

        tool_call_name = ""
        if response.tool_calls:
            tool_call_name = response.tool_calls[0]["name"]
        else:
            chunks_with_categories.append({"content": chunk, "category": "UNKNOWN"})
            continue

        tool_call_args = response.tool_calls[0]["args"]
        if tool_call_name == "RelevantChunk":
            chunks_with_categories.append(
                {
                    "content": chunk,
                    "category": tool_call_name,
                    "origianl_chunk": chunk,
                }
            )
        elif tool_call_name == "PartialChunk":
            relevant_content = tool_call_args["relevant_content"]
            chunks_with_categories.append(
                {
                    "content": relevant_content,
                    "category": tool_call_name,
                    "origianl_chunk": chunk,
                }
            )
        elif tool_call_name == "IrrelevantChunk":
            chunks_with_categories.append(
                {
                    "content": "",
                    "category": tool_call_name,
                    "origianl_chunk": chunk,
                }
            )
        else:
            print("Invalid response: ", response)
            chunks_with_categories.append({"content": chunk, "category": "UNKNOWN"})
            continue

    return Command(
        goto="create_event_list",
        update={"chunks_with_categories": chunks_with_categories},
    )


async def create_event_list(state: UrlCrawlerState) -> Command[Literal["__end__"]]:
    chunks_with_categories = state.get("chunks_with_categories", [])
    raw_content = ""
    events = ""
    for chunk_with_category in chunks_with_categories:
        event_summary = await create_event_list_from_chunks(
            state, chunk_with_category["content"]
        )
        events += event_summary
        raw_content += chunk_with_category["origianl_chunk"]

    return Command(goto=END, update={"events": events})


async def create_event_list_from_chunks(
    state: UrlCrawlerState, chunk_content: str
) -> str:
    """Chunks large text, extracts events in parallel, and consolidates them
    with the previous summary.
    """
    historical_figure = state.get("historical_figure", "")

    # 4. Consolidate new events with the previous summary
    if chunk_content:
        prompt = create_event_list_prompt.format(
            historical_figure=historical_figure, newly_extracted_events=chunk_content
        )

        final_summary = await model_for_big_queries.ainvoke(prompt)
        return final_summary.content

    return ""


builder = StateGraph(
    UrlCrawlerState, input_schema=InputUrlCrawlerState, output_schema=UrlCrawlerState
)

builder.add_node("scrape_content", scrape_content)
builder.add_node("divide_and_extract_chunks", divide_and_extract_chunks)
builder.add_node("create_event_list", create_event_list)
# builder.add_node("return_events", return_events)
builder.add_edge(START, "scrape_content")

url_crawler_graph = builder.compile()
