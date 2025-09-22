import operator
from typing import Annotated, Dict, List, Literal, TypedDict

from langchain_core.messages import MessageLikeRepresentation, ToolMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from src.llm_service import get_llm
from src.prompts import supervisor_tool_selector_prompt

# --- PRE-REQUISITE: Set your OpenAI API Key ---
# Make sure to set this environment variable before running
# os.environ["OPENAI_API_KEY"] = "sk-..."

# --- 1. DEFINE TOOLS FOR THE SUPERVISOR LLM ---

# These Pydantic models define the "schema" of the tools the supervisor can call.


def override_reducer(current_value, new_value):
    """Reducer function that allows overriding values in state."""
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)


class UrlFinderTool(BaseModel):
    """Finds a list of authoritative biography URLs for a given person.
    This should be the very first tool you call in the research process to gather a list of
    high-quality sources (like Wikipedia, Britannica) before you can start extracting events.
    """

    pass  # No arguments needed


class UrlCrawlerTool(BaseModel):
    """Extracts structured biographical events from a single URL.
    Use this tool after `UrlFinderTool` has provided a list of sources. This is the primary
    tool for populating the initial timeline with new events. You should call this for each
    promising URL you find.
    """

    url: str = Field(
        description="The single, most promising URL to crawl for new events."
    )


class FurtherEventResearchTool(BaseModel):
    """Deepens the research on a single, *existing* event to find missing details like
    specific dates, locations, or context. Use this tool when you already have a baseline
    of events from `UrlCrawlerTool` but they are incomplete. Do NOT use this to find new events.
    """

    event_name: str = Field(
        description="The exact name of the event from the timeline that needs more detail. For example, 'Marriage to June Mansfield'."
    )


class FinishResearchTool(BaseModel):
    """Concludes the research process.
    Call this tool ONLY when you have a comprehensive timeline of the person's life,
    including key events like birth, death, major achievements, and significant personal
    milestones, and you are confident that no major gaps remain.
    """

    pass


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


# --- 2. MOCK TOOL IMPLEMENTATIONS ---
# These are the actual Python functions that get executed.


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


# --- 3. DEFINE STATE ---


class SupervisorStateInput(TypedDict):
    person_to_research: str


class SupervisorState(SupervisorStateInput):
    events: List[Dict]
    messages: Annotated[list[MessageLikeRepresentation], override_reducer]


# --- 4. DEFINE GRAPH NODES ---


async def supervisor_node(
    state: SupervisorState,
) -> Command[Literal["supervisor_tools"]]:
    """The 'brain' of the agent. It decides the next action."""
    print("--- SUPERVISOR: Planning next action ---")

    prompt = supervisor_tool_selector_prompt.format(
        person_to_research=state["person_to_research"],
        event_summary=state.get("events", []),
        max_iterations=5,
    )

    # Use a real LLM to make the decision
    llm = get_llm("ollama:gpt-oss:latest")
    tools = [
        UrlFinderTool,
        UrlCrawlerTool,
        FurtherEventResearchTool,
        FinishResearchTool,
        think_tool,
    ]
    llm_with_tools = llm.bind_tools(tools)

    messages = state.get("messages", [])

    prompt = [("system", prompt)] + messages
    print("PROMPT", prompt)

    response = await llm_with_tools.ainvoke(prompt)

    print("RESPONSE", response)
    # The output is an AIMessage with tool_calls, which we add to the history
    return Command(
        goto="supervisor_tools",
        update={"messages": [response]},
    )


async def supervisor_tools_node(
    state: SupervisorState,
) -> Command[Literal["supervisor", "__end__"]]:
    """The 'hands' of the agent. Executes tools and returns a Command for routing."""
    print("--- SUPERVISOR_TOOLS: Executing tools ---")

    last_message = state["messages"][-1]

    # If the LLM made no tool calls, we finish.
    if not last_message.tool_calls:
        print("    -> No tool calls. Finishing.")
        return Command(goto=END)

    # This is the core logic for executing tools and updating state.
    all_tool_messages = []
    current_events = state.get("events", [])

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        print(f"    -> Executing tool: {tool_name} with args: {tool_args}")

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


# --- 5. BUILD THE GRAPH ---

workflow = StateGraph(SupervisorState, input_schema=SupervisorStateInput)

# Add the two core nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("supervisor_tools", supervisor_tools_node)

# The supervisor node is the entry point
workflow.add_edge(START, "supervisor")

# The supervisor plans, and then the tools node executes.

# The `supervisor_tools` node uses the Command helper to decide what to do next:
# - Command(goto="supervisor", ...) will loop back to the supervisor.
# - Command(goto=END) or just END will terminate the graph.
# LangGraph inherently understands how to handle the Command object, so no more edges are needed.

graph = workflow.compile()
