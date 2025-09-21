import asyncio
from typing import List

import tiktoken  # You might need to run: pip install tiktoken
from langchain_core.messages import (
    BaseMessage,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from src.llm_service import get_llm
from src.state import ResearchComplete

model_for_tools = get_llm("ollama:gpt-oss:latest")
model_for_big_queries = get_llm("ollama:gemma3:12b")
structured_model = get_llm("ollama:llama3.1:latest")


@tool
def think_tool(reflection_and_plan: str) -> str:
    """A tool for the agent to reflect on its findings and plan the next step."""
    print(f"--- AGENT REFLECTION ---\n{reflection_and_plan}\n----------------------")
    return reflection_and_plan


@tool
async def url_crawl(url: str) -> str:  ## REPLACE WITH SUBGRAPH
    """A tool for the agent to crawl a URL and return the content."""
    from src.url_crawler.utils import url_crawl as actual_url_crawl

    return await actual_url_crawl(url)


async def get_all_tools(config: RunnableConfig):
    """Returns the list of available tools."""
    return [url_crawl, think_tool, tool(ResearchComplete)]


async def execute_tool_safely(tool_to_call, args, config):
    """Safely execute a tool with error handling."""
    print(f"Executing tool: {tool_to_call.name} with args {args}")
    try:
        # Note: LangChain tools are not all natively async.
        # For simplicity here, we run sync tools in a thread pool executor.
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: tool_to_call.invoke(args, config)
        )
    except Exception as e:
        return f"Error executing tool {tool_to_call.name}: {str(e)}"


# --- New Helper Function: Token Counter ---
# Use the tokenizer for your specific model
tokenizer = tiktoken.get_encoding("cl100k_base")


def count_tokens(messages: List[BaseMessage]) -> int:
    """Counts the total tokens in a list of messages."""
    return sum(len(tokenizer.encode(msg.content)) for msg in messages)
