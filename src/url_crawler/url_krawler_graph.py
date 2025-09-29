import random
from typing import Literal, TypedDict

from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field
from src.llm_service import model_for_big_queries, model_for_tools
from src.url_crawler.prompts import (
    EXTRACT_EVENTS_PROMPT,
    FINAL_EVENT_LIST_PROMPT,
)
from src.url_crawler.utils import (
    chunk_text_by_tokens,
    url_crawl,
)

CHUNK_SIZE = 800
OVERLAP_SIZE = 20
MAX_CONTENT_LENGTH = 100000

# CHUNK_SIZE = 40
# OVERLAP_SIZE = 0


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
    research_question: str


class ChunkWithCategory(TypedDict):
    content: str
    category: str
    original_chunk: str


class UrlCrawlerState(InputUrlCrawlerState):
    raw_scraped_content: str
    text_chunks: list[str]
    extracted_events: str
    categorized_chunks: list[ChunkWithCategory]


class OutputUrlCrawlerState(UrlCrawlerState):
    extracted_events: str
    raw_scraped_content: str


async def scrape_content(
    state: UrlCrawlerState,
) -> Command[Literal["divide_and_extract_chunks"]]:
    url = state.get("url", "")

    print(f"Scraping content for URL: {url}")
    content = await url_crawl(url)

    if len(content) > MAX_CONTENT_LENGTH:
        # At random start
        start_index = random.randint(0, len(content) - MAX_CONTENT_LENGTH)
        content = content[start_index : start_index + MAX_CONTENT_LENGTH]

    return Command(
        goto="divide_and_extract_chunks", update={"raw_scraped_content": content}
    )


async def divide_and_extract_chunks(
    state: UrlCrawlerState,
) -> Command[Literal["create_event_list"]]:
    content = state.get("raw_scraped_content", "")
    research_question = state.get("research_question", "")

    # 1. Chunks are divided into chunks by tokens
    text_chunks = chunk_text_by_tokens(
        content, chunk_size=CHUNK_SIZE, overlap_size=OVERLAP_SIZE
    )

    # 2. tools are binded to the model
    tools = [tool(RelevantChunk), tool(PartialChunk), tool(IrrelevantChunk)]
    model_tools = model_for_tools.bind_tools(tools)

    # 3. Chunks are analyzed and simplified.

    categorized_chunks = []
    for chunk in text_chunks[4:6]:
        prompt = EXTRACT_EVENTS_PROMPT.format(
            research_question=research_question, text_chunk=chunk
        )
        response = await model_tools.ainvoke(prompt)

        tool_call_name = ""
        if response.tool_calls:
            tool_call_name = response.tool_calls[0]["name"]
        else:
            categorized_chunks.append({"content": chunk, "category": "UNKNOWN"})
            continue

        tool_call_args = response.tool_calls[0]["args"]
        if tool_call_name == "RelevantChunk":
            categorized_chunks.append(
                {
                    "content": chunk,
                    "category": tool_call_name,
                    "original_chunk": chunk,
                }
            )
        elif tool_call_name == "PartialChunk":
            relevant_content = tool_call_args["relevant_content"]
            categorized_chunks.append(
                {
                    "content": relevant_content,
                    "category": tool_call_name,
                    "original_chunk": chunk,
                }
            )
        elif tool_call_name == "IrrelevantChunk":
            categorized_chunks.append(
                {
                    "content": "",
                    "category": tool_call_name,
                    "original_chunk": chunk,
                }
            )
        else:
            print("Invalid response: ", response)
            categorized_chunks.append(
                {"content": chunk, "category": "UNKNOWN", "original_chunk": chunk}
            )
            continue

    return Command(
        goto="create_event_list",
        update={"categorized_chunks": categorized_chunks},
    )


async def create_event_list(state: UrlCrawlerState) -> Command[Literal["__end__"]]:
    categorized_chunks = state.get("categorized_chunks", [])
    research_question = state.get("research_question", "")

    relevant_texts = []
    raw_content_rebuilt = ""

    # 1. Consolidate Phase: Loop ONLY to gather data, NO LLM calls here
    for chunk in categorized_chunks:
        # Rebuild the full raw content for the final state
        raw_content_rebuilt += chunk["original_chunk"]

        # Collect only the content deemed useful by the previous step
        # We check the category to be safe, or we could just check if chunk["content"] is not empty
        if chunk["category"] in ["RelevantChunk", "PartialChunk"] and chunk["content"]:
            relevant_texts.append(chunk["content"])

    # Join all relevant pieces into one large document, separated by newlines
    consolidated_context = "\n\n".join(relevant_texts)

    extracted_events = ""

    # 2. Summarize Phase: ONE single LLM call
    if consolidated_context:
        print("Generating final event list from consolidated content...")
        prompt = FINAL_EVENT_LIST_PROMPT.format(
            research_question=research_question,
            consolidated_context=consolidated_context,
        )

        # This is now the ONLY call to the model in this node
        final_summary = await model_for_big_queries.ainvoke(prompt)
        extracted_events = final_summary.content
    else:
        extracted_events = "No relevant events found matching the research question."

    return Command(
        goto=END,
        update={
            "extracted_events": extracted_events,
            "raw_scraped_content": raw_content_rebuilt,
        },
    )


builder = StateGraph(
    UrlCrawlerState, input_schema=InputUrlCrawlerState, output_schema=UrlCrawlerState
)

builder.add_node("scrape_content", scrape_content)
builder.add_node("divide_and_extract_chunks", divide_and_extract_chunks)
builder.add_node("create_event_list", create_event_list)
# builder.add_node("return_events", return_events)
builder.add_edge(START, "scrape_content")

url_crawler_app = builder.compile()
