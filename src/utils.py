import asyncio
from datetime import datetime
import logging
from langchain_core.language_models import BaseChatModel
import requests
from tavily import AsyncTavilyClient
from langchain_core.tools import (
    tool,
)
import os
from langgraph.graph.state import RunnableConfig

from src.configuration import SearchAPI
from src.configuration import Configuration

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, MessageLikeRepresentation
from langchain_core.tools import InjectedToolArg
from typing import Annotated, List, Literal

from src.prompts import summarize_webpage_prompt
from src.state import ResearchComplete, Summary
import re

##########################
# Tavily Search Tool Utils
##########################
TAVILY_SEARCH_DESCRIPTION = (
    "A search engine optimized for comprehensive, accurate, and trusted results. "
    "Useful for when you need to answer questions about current events."
)
FIRECRAWL_API_URL = "http://localhost:3002/v0/scrape"


@tool(description="Url Crawl")
async def url_crawl(url: str) -> str:
    """Crawl a URL and return the content.

    Args:
        url: The URL to crawl

    Returns:
        The content of the URL
    """

    content = scrape_page_content(url)
    return remove_markdown_links(content)


def scrape_page_content(url):
    """Scrapes URL using Firecrawl API and returns Markdown content."""
    try:
        response = requests.post(
            FIRECRAWL_API_URL,
            json={
                "url": url,
                "pageOptions": {"onlyMainContent": True},
                "formats": ["markdown"],
            },
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("data", {}).get("markdown")
    except requests.exceptions.RequestException:
        return None


def remove_markdown_links(markdown_text):
    """Removes Markdown links, keeping only display text."""
    return re.sub(r"\[(.*?)\]\(.*?\)", r"\1", markdown_text)


@tool(description=TAVILY_SEARCH_DESCRIPTION)
async def tavily_search(
    queries: List[str],
    max_results: Annotated[int, InjectedToolArg] = 5,
    topic: Annotated[
        Literal["general", "news", "finance"], InjectedToolArg
    ] = "general",
    config: RunnableConfig = None,
) -> str:
    """Fetch and summarize search results from Tavily search API.

    Args:
        queries: List of search queries to execute
        max_results: Maximum number of results to return per query
        topic: Topic filter for search results (general, news, or finance)
        config: Runtime configuration for API keys and model settings

    Returns:
        Formatted string containing summarized search results
    """
    # Step 1: Execute search queries asynchronously
    search_results = await tavily_search_async(
        queries,
        max_results=max_results,
        topic=topic,
        include_raw_content=True,
        config=config,
    )

    # Step 2: Deduplicate results by URL to avoid processing the same content multiple times
    unique_results = {}
    for response in search_results:
        for result in response["results"]:
            url = result["url"]
            if url not in unique_results:
                unique_results[url] = {**result, "query": response["query"]}

    # Step 3: Set up the summarization model with configuration
    configurable = Configuration.from_runnable_config(config)

    # Character limit to stay within model token limits (configurable)
    max_char_to_include = configurable.max_content_length

    # Initialize summarization model with retry logic
    model_api_key = get_api_key_for_model(configurable.summarization_model, config)
    summarization_model = (
        init_chat_model(
            model=configurable.summarization_model,
            max_tokens=configurable.summarization_model_max_tokens,
            api_key=model_api_key,
            tags=["langsmith:nostream"],
        )
        .with_structured_output(Summary)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
    )

    # Step 4: Create summarization tasks (skip empty content)
    async def noop():
        """No-op function for results without raw content."""
        return None

    summarization_tasks = [
        noop()
        if not result.get("raw_content")
        else summarize_webpage(
            summarization_model, result["raw_content"][:max_char_to_include]
        )
        for result in unique_results.values()
    ]

    # Step 5: Execute all summarization tasks in parallel
    summaries = await asyncio.gather(*summarization_tasks)

    # Step 6: Combine results with their summaries
    summarized_results = {
        url: {
            "title": result["title"],
            "content": result["content"] if summary is None else summary,
        }
        for url, result, summary in zip(
            unique_results.keys(), unique_results.values(), summaries
        )
    }

    # Step 7: Format the final output
    if not summarized_results:
        return "No valid search results found. Please try different search queries or use a different search API."

    formatted_output = "Search results: \n\n"
    for i, (url, result) in enumerate(summarized_results.items()):
        formatted_output += f"\n\n--- SOURCE {i + 1}: {result['title']} ---\n"
        formatted_output += f"URL: {url}\n\n"
        formatted_output += f"SUMMARY:\n{result['content']}\n\n"
        formatted_output += "\n\n" + "-" * 80 + "\n"

    return formatted_output


async def tavily_search_async(
    search_queries,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = True,
    config: RunnableConfig = None,
):
    """Execute multiple Tavily search queries asynchronously.

    Args:
        search_queries: List of search query strings to execute
        max_results: Maximum number of results per query
        topic: Topic category for filtering results
        include_raw_content: Whether to include full webpage content
        config: Runtime configuration for API key access

    Returns:
        List of search result dictionaries from Tavily API
    """
    # Initialize the Tavily client with API key from config
    tavily_client = AsyncTavilyClient(api_key=get_tavily_api_key(config))

    # Create search tasks for parallel execution
    search_tasks = [
        tavily_client.search(
            query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic,
        )
        for query in search_queries
    ]

    # Execute all search queries in parallel and return results
    search_results = await asyncio.gather(*search_tasks)
    return search_results


async def summarize_webpage(model: BaseChatModel, webpage_content: str) -> str:
    """Summarize webpage content using AI model with timeout protection.

    Args:
        model: The chat model configured for summarization
        webpage_content: Raw webpage content to be summarized

    Returns:
        Formatted summary with key excerpts, or original content if summarization fails
    """
    try:
        # Create prompt with current date context
        prompt_content = summarize_webpage_prompt.format(
            webpage_content=webpage_content, date=get_today_str()
        )

        # Execute summarization with timeout to prevent hanging
        summary = await asyncio.wait_for(
            model.ainvoke([HumanMessage(content=prompt_content)]),
            timeout=60.0,  # 60 second timeout for summarization
        )

        # Format the summary with structured sections
        formatted_summary = (
            f"<summary>\n{summary.summary}\n</summary>\n\n"
            f"<key_excerpts>\n{summary.key_excerpts}\n</key_excerpts>"
        )

        return formatted_summary

    except asyncio.TimeoutError:
        # Timeout during summarization - return original content
        logging.warning(
            "Summarization timed out after 60 seconds, returning original content"
        )
        return webpage_content
    except Exception as e:
        # Other errors during summarization - log and return original content
        logging.warning(
            f"Summarization failed with error: {str(e)}, returning original content"
        )
        return webpage_content


##########################
# Reflection Tool Utils
##########################


@tool
def reflect_on_chronology(reflection_and_plan: str) -> str:
    """
    A tool for the research assistant to reflect on chronological findings, identify gaps in the timeline, and plan the next research step.

    Use this tool after every web search to assess the completeness of the biography.
    The input should be a concise summary of your thoughts.

    Args:
        reflection_and_plan: A concise, multi-line string that must include these three parts:
        1. **Events Found:** A summary of new chronological facts and dates just learned.
        2. **Timeline Gaps:** An analysis of what key periods or events are still missing from the person's life story.
        3. **Next Action:** The specific search query to run next to fill the gaps, or the single word "STOP" if the timeline is complete enough.
    """
    # The tool's main purpose is to force the agent to pause, structure its thoughts,
    # and document its plan. It simply returns the thought process to be added to the
    # message history, which guides the agent's next turn.
    print(f"--- AGENT REFLECTION ---\n{reflection_and_plan}\n----------------------")
    return reflection_and_plan


def get_api_key_for_model(model_name: str, config: RunnableConfig):
    """Get API key for a specific model from environment or config."""
    should_get_from_config = os.getenv("GET_API_KEYS_FROM_CONFIG", "false")
    model_name = model_name.lower()
    if should_get_from_config.lower() == "true":
        api_keys = config.get("configurable", {}).get("apiKeys", {})
        if not api_keys:
            return None
        if model_name.startswith("openai:"):
            return api_keys.get("OPENAI_API_KEY")
        elif model_name.startswith("google"):
            return api_keys.get("GOOGLE_API_KEY")
        return None
    else:
        if model_name.startswith("openai:"):
            return os.getenv("OPENAI_API_KEY")
        elif model_name.startswith("google"):
            return os.getenv("GOOGLE_API_KEY")
        return None


async def get_search_tool(search_api: SearchAPI):
    """Configure and return search tools based on the specified API provider.

    Args:
        search_api: The search API provider to use (Anthropic, OpenAI, Tavily, or None)

    Returns:
        List of configured search tool objects for the specified provider
    """
    if search_api == SearchAPI.TAVILY:
        # Configure Tavily search tool with metadata
        search_tool = tavily_search
        search_tool.metadata = {
            **(search_tool.metadata or {}),
            "type": "search",
            "name": "web_search",
        }
        return [search_tool]

    elif search_api == SearchAPI.NONE:
        # No search functionality configured
        return []

    # Default fallback for unknown search API types
    return []


async def get_all_tools(config: RunnableConfig):
    """Assemble complete toolkit including research, search, and MCP tools.

    Args:
        config: Runtime configuration specifying search API and MCP settings

    Returns:
        List of all configured and available tools for research operations
    """
    # Start with core research tools
    tools = [tool(ResearchComplete), reflect_on_chronology]

    # Add configured search tools
    configurable = Configuration.from_runnable_config(config)
    # search_api = SearchAPI(get_config_value(configurable.search_api))
    # search_tools = await get_search_tool(search_api)
    search_tools = [url_crawl]
    # tools.extend(search_tools)

    print(f"Tools: {tools}")

    return tools


def remove_up_to_last_ai_message(
    messages: list[MessageLikeRepresentation],
) -> list[MessageLikeRepresentation]:
    """Truncate message history by removing up to the last AI message.

    This is useful for handling token limit exceeded errors by removing recent context.

    Args:
        messages: List of message objects to truncate

    Returns:
        Truncated message list up to (but not including) the last AI message
    """
    # Search backwards through messages to find the last AI message
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], AIMessage):
            # Return everything up to (but not including) the last AI message
            return messages[:i]

    # No AI messages found, return original list
    return messages


##########################
# Misc Utils
##########################


def get_today_str() -> str:
    """Get current date formatted for display in prompts and outputs.

    Returns:
        Human-readable date string in format like 'Mon Jan 15, 2024'
    """
    now = datetime.now()
    return f"{now:%a} {now:%b} {now.day}, {now:%Y}"


def get_config_value(value):
    """Extract value from configuration, handling enums and None values."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    elif isinstance(value, dict):
        return value
    else:
        return value.value


def get_tavily_api_key(config: RunnableConfig):
    """Get Tavily API key from environment or config."""
    should_get_from_config = os.getenv("GET_API_KEYS_FROM_CONFIG", "false")
    if should_get_from_config.lower() == "true":
        api_keys = config.get("configurable", {}).get("apiKeys", {})
        if not api_keys:
            return None
        return api_keys.get("TAVILY_API_KEY")
    else:
        return os.getenv("TAVILY_API_KEY")
