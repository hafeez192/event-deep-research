from typing import Literal

from langchain_core.messages import MessageLikeRepresentation, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from src.llm_service import model_for_tools
from src.prompts import create_messages_summary_prompt, supervisor_tool_selector_prompt
from src.research_events.research_event_graph import research_events_graph
from src.state import (
    FinishResearchTool,
    ResearchEventsTool,
    SupervisorState,
    SupervisorStateInput,
)

MAX_TOOL_CALL_ITERATIONS = 5


@tool(description="Strategic reflection tool for research planning")
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.

    Use this tool after each search to analyze what are the current events and plan next step systematically.
    This creates a deliberate pause in the research workflow for quality decision-making.

    When to use:
    - After finding new events: Which new events have been added?
    - Which events may be missing or need to be further researched?
    - When assessing events gaps: What specific information am I still missing?
    - Before concluding research: Is the chronology sufficient to know in detail the life of the person?

    Reflection should address:
    1. Analysis of current events - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient events and are these enough explained for a good chronology?
    4. Strategic decision - Should I continue searching or provide my chronology?

    Args:
        reflection: Your detailed reflection on research progress, events, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"


def research_events_func(prompt: str):
    """Mock implementation for finding URLs.

    Args:
        prompt: The prompt for the search engine to find URLs

    Returns:
        A list of URLs
    """
    print("--- Executing Mock URL Finder ---")
    print(f"Prompt: {prompt}")

    urls = (
        [
            "https://en.wikipedia.org/wiki/Henry_Miller",
            "https://www.britannica.com/biography/Henry-Miller",
        ],
    )
    new_events = []
    for url in urls:
        ## Trigger Url Crawler and what do we want to get?
        if "wikipedia" in url:
            events_from_url = """
                - Birth of Henry Miller in 1891 in New York City
                - Moved to Paris in 1930
            """

            merged_events = [
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
            ]
            new_events.append(merged_events)
        # elif "britannica" in url:

    return new_events


async def create_messages_summary(
    state: SupervisorState, new_messages: list[MessageLikeRepresentation]
) -> str:
    previous_messages_summary = state.get("messages_summary", "")
    """Create a summary of the messages."""
    prompt = create_messages_summary_prompt.format(
        new_messages=new_messages,
        previous_messages_summary=previous_messages_summary,
    )

    response = await model_for_tools.ainvoke(prompt)
    return response.content


async def supervisor_node(
    state: SupervisorState,
) -> Command[Literal["supervisor_tools"]]:
    """The 'brain' of the agent. It decides the next action."""
    prompt = supervisor_tool_selector_prompt.format(
        person_to_research=state["person_to_research"],
        event_summary=state.get("events", []),
        messages_summary=state.get("messages_summary", ""),
        max_iterations=5,
    )

    tools = [
        ResearchEventsTool,
        FinishResearchTool,
        think_tool,
    ]
    llm_with_tools = model_for_tools.bind_tools(tools)

    prompt = [("system", prompt)]

    response = await llm_with_tools.ainvoke(prompt)

    messages_summary = await create_messages_summary(state, [response])

    # The output is an AIMessage with tool_calls, which we add to the history
    return Command(
        goto="supervisor_tools",
        update={
            "messages": [response],
            "messages_summary": messages_summary,
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1,
        },
    )


async def supervisor_tools_node(
    state: SupervisorState,
) -> Command[Literal["supervisor", "__end__"]]:
    """The 'hands' of the agent. Executes tools and returns a Command for routing."""
    last_message = state["messages"][-1]
    tool_call_iterations = state.get("tool_call_iterations", 0)
    exceeded_allowed_iterations = tool_call_iterations >= MAX_TOOL_CALL_ITERATIONS

    # If the LLM made no tool calls, we finish.
    if not last_message.tool_calls or exceeded_allowed_iterations:
        return Command(goto=END)

    # This is the core logic for executing tools and updating state.
    all_tool_messages = []
    events = state.get("events", [])

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

        elif tool_name == "ResearchEventsTool":
            prompt = tool_args["prompt"]
            result = await research_events_graph.ainvoke(prompt=prompt, events=events)
            all_tool_messages.append(
                ToolMessage(
                    content=str(result), tool_call_id=tool_call["id"], name=tool_name
                )
            )

    messages_summary = await create_messages_summary(state, all_tool_messages)
    # The Command helper tells the graph where to go next and what state to update.
    return Command(
        goto="supervisor",
        update={
            "events": events,
            "messages": all_tool_messages,
            "messages_summary": messages_summary,
        },
    )


workflow = StateGraph(SupervisorState, input_schema=SupervisorStateInput)

# Add the two core nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("supervisor_tools", supervisor_tools_node)

workflow.add_edge(START, "supervisor")


graph = workflow.compile()
