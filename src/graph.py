from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from src.llm_service import model_for_tools
from src.prompts import supervisor_tool_selector_prompt
from src.state import (
    FinishResearchTool,
    FurtherEventResearchTool,
    SupervisorState,
    SupervisorStateInput,
    UrlCrawlerTool,
    UrlFinderTool,
)


@tool(description="Strategic reflection tool for research planning")
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.

    Use this tool after each search to analyze results and plan next steps systematically.
    This creates a deliberate pause in the research workflow for quality decision-making.

    When to use:
    - After receiving search results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing research gaps: What specific information am I still missing?
    - Before concluding research: Can I provide a complete answer now?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
    4. Strategic decision - Should I continue searching or provide my answer?

    Args:
        reflection: Your detailed reflection on research progress, findings, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"


def url_finder_func():
    """Mock implementation for finding URLs."""
    print("--- Executing Mock URL Finder ---")
    return {
        "output": "Found 2 URLs.",
        "urls": [
            "https://en.wikipedia.org/wiki/Henry_Miller",
            "https://www.britannica.com/biography/Henry-Miller",
        ],
    }


def url_crawler_func(url: str):
    """Mock implementation for crawling a URL."""
    print(f"--- Executing Mock URL Crawler for: {url} ---")
    if url.contains("wikipedia"):
        return {
            "output": "Extracted 2 new events from Wikipedia.",
            "new_events": [
                {
                    "id": 1,
                    "name": "Birth",
                    "description": "Born in Yorkville, NYC.",
                    "source": "Wikipedia",
                    "date": {"year": 1891},
                    "location": "New York City",
                },
                {
                    "id": 2,
                    "name": "Moved to Paris",
                    "description": "Moved to Paris, a defining moment.",
                    "source": "Wikipedia",
                    "date": {"year": 1930},
                    "location": "Paris, France",
                },
            ],
        }
    else:
        return {
            "output": "Extracted 2 new events from Britannica.",
            "new_events": [
                {
                    "id": 1,
                    "name": "Death",
                    "description": "Died in Pacific Palisades, Los Angeles.",
                    "source": "Britannica",
                    "date": {"year": 1980},
                    "location": "Pacific Palisades, Los Angeles",
                },
            ],
        }


def further_event_research_func(event_name: str):
    """Mock implementation for enriching an event."""
    print(f"--- Executing Mock Further Research for: {event_name} ---")
    return {
        "output": "Found more detail for the 'Moved to Paris' event.",
        "updated_event": {
            "id": 2,
            "name": "Moved to Paris",
            "description": "Moved to Paris in 1930, a period which would define his literary career.",
            "source": "Britannica",
            "date": {"year": 1930},
            "location": "Paris, France",
        },
    }


async def supervisor_node(
    state: SupervisorState,
) -> Command[Literal["supervisor_tools"]]:
    """The 'brain' of the agent. It decides the next action."""
    prompt = supervisor_tool_selector_prompt.format(
        person_to_research=state["person_to_research"],
        event_summary=state.get("events", []),
        max_iterations=5,
    )

    tools = [
        UrlFinderTool,
        UrlCrawlerTool,
        FurtherEventResearchTool,
        FinishResearchTool,
        think_tool,
    ]
    llm_with_tools = model_for_tools.bind_tools(tools)

    messages = state.get("messages", [])

    prompt = [("system", prompt)] + messages
    print("Supervisor PROMPT", prompt)
    response = await llm_with_tools.ainvoke(prompt)

    # The output is an AIMessage with tool_calls, which we add to the history
    return Command(
        goto="supervisor_tools",
        update={"messages": [response]},
    )


async def supervisor_tools_node(
    state: SupervisorState,
) -> Command[Literal["supervisor", "__end__"]]:
    """The 'hands' of the agent. Executes tools and returns a Command for routing."""
    last_message = state["messages"][-1]

    # If the LLM made no tool calls, we finish.
    if not last_message.tool_calls:
        return Command(goto=END)

    # This is the core logic for executing tools and updating state.
    all_tool_messages = []
    current_events = state.get("events", [])

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        if tool_name == "FinishResearchTool":
            return Command(goto=END)

        elif tool_name == "think_tool":
            # The 'think' tool is special: it just records a reflection.
            # The reflection will be in the message history for the *next* supervisor turn.
            response_content = tool_args["reflection"]
            all_tool_messages.append(
                ToolMessage(
                    content=response_content,
                    tool_call_id=tool_call["id"],
                    name=tool_name,
                )
            )

        elif tool_name == "UrlFinderTool":
            result = url_finder_func()
            all_tool_messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_call["id"])
            )

        elif tool_name == "UrlCrawlerTool":
            result = url_crawler_func(tool_args["url"])
            if "new_events" in result:
                current_events.extend(result["new_events"])  # Update events list
            all_tool_messages.append(
                ToolMessage(content=result["output"], tool_call_id=tool_call["id"])
            )

        elif tool_name == "FurtherEventResearchTool":
            result = further_event_research_func(tool_args["event_name"])
            if "updated_event" in result:
                # Simple update logic for MVP
                for i, event in enumerate(current_events):
                    if event["id"] == result["updated_event"]["id"]:
                        current_events[i] = result["updated_event"]
                        break
            all_tool_messages.append(
                ToolMessage(content=result["output"], tool_call_id=tool_call["id"])
            )

    # The Command helper tells the graph where to go next and what state to update.
    return Command(
        goto="supervisor",
        update={"events": current_events, "messages": all_tool_messages},
    )


workflow = StateGraph(SupervisorState, input_schema=SupervisorStateInput)

# Add the two core nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("supervisor_tools", supervisor_tools_node)

workflow.add_edge(START, "supervisor")


graph = workflow.compile()
