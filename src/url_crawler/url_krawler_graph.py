import random
from typing import Literal, TypedDict

from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field
from src.llm_service import model_for_big_queries, model_for_tools
from src.url_crawler.prompts import (
    EXTRACT_EVENTS_PROMPT,
    create_event_list_prompt,
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
    """The VAST MAJORITY (>80%) of the chunk consists of events directly relevant
    to the research question.
    """


class PartialChunk(BaseModel):
    """The chunk is a MIX of relevant and irrelevant content. Use this even for a
    single sentence that may refer to a biographical event.
    """

    relevant_content: str = Field(
        description="An extraction of ALL sentences relevant to the research question. "
        "Must include full details (dates, names, context) from the original text."
    )


class IrrelevantChunk(BaseModel):
    """The chunk contains ABSOLUTELY NO information that are relevant to the biography of the person in the research question."""


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
    for chunk in text_chunks:
        prompt = EXTRACT_EVENTS_PROMPT.format(
            research_question=research_question, text_chunk=chunk
        )
        response = await model_tools.ainvoke(prompt)

        tool_call_name = ""
        if response.tool_calls:
            tool_call_name = response.tool_calls[0]["name"]
        else:
            categorized_chunks.append(
                {"content": chunk, "category": "UNKNOWN", "original_chunk": chunk}
            )
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
    raw_content = ""
    extracted_events = ""
    for chunk_with_category in categorized_chunks:
        event_summary = await create_event_list_from_chunks(
            state, chunk_with_category["content"]
        )
        extracted_events += event_summary
        raw_content += chunk_with_category["original_chunk"]

    return Command(
        goto=END,
        update={
            "extracted_events": extracted_events,
            "raw_scraped_content": raw_content,
        },
    )


async def create_event_list_from_chunks(
    state: UrlCrawlerState, chunk_content: str
) -> str:
    """Chunks large text, extracts events in parallel, and consolidates them
    with the previous summary.
    """
    research_question = state.get("research_question", "")
    # 4. Consolidate new events with the previous summary
    if chunk_content:
        prompt = create_event_list_prompt.format(
            research_question=research_question, newly_extracted_events=chunk_content
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

from langfuse.langchain import CallbackHandler

langfuse_handler = CallbackHandler()

url_crawler_app = builder.compile().with_config({"callbacks": [langfuse_handler]})
