import random
from typing import List, Literal, TypedDict

from langchain_core.tools import tool
from langfuse.langchain import CallbackHandler
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel, Field
from src.configuration import Configuration
from src.llm_service import create_structured_model, create_tools_model
from src.url_crawler.prompts import (
    EXTRACT_EVENTS_PROMPT,
    create_event_list_prompt,
)
from src.url_crawler.utils import (
    chunk_text_by_tokens,
    url_crawl,
)

config = Configuration()
CHUNK_SIZE = config.default_chunk_size
OVERLAP_SIZE = config.default_overlap_size
MAX_CONTENT_LENGTH = config.max_content_length

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
    # The queue of work to be done
    text_chunks: List[str]
    # The list of completed work
    categorized_chunks: List[ChunkWithCategory]
    # Final output
    extracted_events: str | None


class OutputUrlCrawlerState(UrlCrawlerState):
    extracted_events: str
    raw_scraped_content: str


async def scrape_content(
    state: UrlCrawlerState,
) -> Command[Literal["chunk_content"]]:
    url = state.get("url", "")

    content = await url_crawl(url)

    if len(content) > MAX_CONTENT_LENGTH:
        # At random start
        start_index = random.randint(0, len(content) - MAX_CONTENT_LENGTH)
        content = content[start_index : start_index + MAX_CONTENT_LENGTH]

    return Command(goto="chunk_content", update={"raw_scraped_content": content})


async def chunk_content(
    state: UrlCrawlerState,
) -> Command[Literal["categorize_chunk"]]:
    """Takes the raw content and splits it into chunks, initializing the work queue."""
    print("--- Splitting content into chunks ---")
    content = state.get("raw_scraped_content", "")

    text_chunks = await chunk_text_by_tokens(
        content, chunk_size=CHUNK_SIZE, overlap_size=OVERLAP_SIZE
    )

    # Initialize the categorized_chunks list as empty
    return Command(
        goto="categorize_chunk",
        update={"text_chunks": text_chunks, "categorized_chunks": []},
    )


async def categorize_chunk(
    state: UrlCrawlerState,
    config: RunnableConfig,
) -> Command[Literal["categorize_chunk", "create_event_list"]]:
    """Processes a single chunk from the queue. If the queue is empty, it proceeds
    to the next step. Otherwise, it loops back to itself.
    """
    text_chunks = state.get("text_chunks", [])
    categorized_so_far = state.get("categorized_chunks", [])

    # 1. Check for the exit condition
    if len(categorized_so_far) >= len(text_chunks):
        print("--- All chunks categorized. Moving to merge. ---")
        return Command(goto="create_event_list")

    # 2. Get the next chunk to process
    current_index = len(categorized_so_far)
    chunk = text_chunks[current_index]
    print(f"--- Categorizing chunk {current_index + 1}/{len(text_chunks)} ---")

    # 3. Perform the work for this single chunk (logic moved from the old for-loop)
    research_question = state.get("research_question", "")
    prompt = EXTRACT_EVENTS_PROMPT.format(
        research_question=research_question, text_chunk=chunk
    )

    # Let's define these globally so they aren't recreated on every call
    tools = [tool(RelevantChunk), tool(PartialChunk), tool(IrrelevantChunk)]
    model_tools = create_tools_model(tools=tools, config=config)
    response = await model_tools.ainvoke(prompt)

    # This is the same parsing logic as before, but it creates a single result_dict
    result_dict = {}
    tool_call_name = (
        response.tool_calls[0]["name"] if response.tool_calls else "UNKNOWN"
    )
    tool_call_args = response.tool_calls[0]["args"] if response.tool_calls else {}

    if tool_call_name == "RelevantChunk":
        result_dict = {
            "content": chunk,
            "category": tool_call_name,
            "original_chunk": chunk,
        }
    elif tool_call_name == "PartialChunk":
        relevant_content = tool_call_args.get("relevant_content", "")
        result_dict = {
            "content": relevant_content,
            "category": tool_call_name,
            "original_chunk": chunk,
        }
    elif tool_call_name == "IrrelevantChunk":
        result_dict = {
            "content": "",
            "category": tool_call_name,
            "original_chunk": chunk,
        }
    else:
        result_dict = {"content": chunk, "category": "UNKNOWN", "original_chunk": chunk}

    # 4. Update the state and loop
    return Command(
        goto="categorize_chunk",  # Loop back to this same node
        update={"categorized_chunks": categorized_so_far + [result_dict]},
    )


async def create_event_list(
    state: UrlCrawlerState, config: RunnableConfig
) -> Command[Literal["__end__"]]:
    """Takes the final list of all categorized chunks and extracts a single event list."""
    print("--- Merging all categorized chunks into a final event list ---")
    categorized_chunks = state.get("categorized_chunks", [])

    raw_content = ""
    extracted_events = ""
    for chunk_with_category in categorized_chunks:
        event_summary = await create_event_list_from_chunks(
            state, chunk_with_category["content"], config
        )
        extracted_events += event_summary
        # Reconstruct the original content for context if needed
        raw_content += chunk_with_category.get("original_chunk", "")

    return Command(
        goto=END,
        update={
            "extracted_events": extracted_events,
            "raw_scraped_content": raw_content,
        },
    )


async def create_event_list_from_chunks(
    state: UrlCrawlerState, chunk_content: str, config: RunnableConfig
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

        final_summary = await create_structured_model(config=config).ainvoke(prompt)
        return final_summary.content

    return ""


builder = StateGraph(
    UrlCrawlerState,
    input_schema=InputUrlCrawlerState,
    output_schema=UrlCrawlerState,
    config_schema=Configuration,
)

builder.add_node("scrape_content", scrape_content)
builder.add_node("chunk_content", chunk_content)
builder.add_node("categorize_chunk", categorize_chunk)
builder.add_node("create_event_list", create_event_list)
# builder.add_node("return_events", return_events)
builder.add_edge(START, "scrape_content")


def get_langfuse_handler():
    return CallbackHandler()


url_crawler_app = builder.compile().with_config({"callbacks": [get_langfuse_handler()]})
