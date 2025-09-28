from typing import Literal

from langchain_core.messages import ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from src.llm_service import model_for_tools
from src.prompts import supervisor_tool_selector_prompt
from src.research_events.research_events_graph import research_events_app
from src.state import (
    FinishResearchTool,
    ResearchEventsTool,
    SupervisorState,
    SupervisorStateInput,
)
from src.utils import create_messages_summary, think_tool

MAX_TOOL_CALL_ITERATIONS = 5


async def supervisor_node(
    state: SupervisorState,
) -> Command[Literal["supervisor_tools"]]:
    """The 'brain' of the agent. It decides the next action."""
    prompt = supervisor_tool_selector_prompt.format(
        person_to_research=state["person_to_research"],
        event_summary=state.get("chronology_events", []),
        messages_summary=state.get("conversation_summary", ""),
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

    conversation_summary = await create_messages_summary(state, [response])

    # The output is an AIMessage with tool_calls, which we add to the history
    return Command(
        goto="supervisor_tools",
        update={
            "conversation_history": [response],
            "conversation_summary": conversation_summary,
            "iteration_count": state.get("iteration_count", 0) + 1,
        },
    )


async def supervisor_tools_node(
    state: SupervisorState,
) -> Command[Literal["supervisor", "__end__"]]:
    """The 'hands' of the agent. Executes tools and returns a Command for routing."""
    last_message = state["conversation_history"][-1]
    iteration_count = state.get("iteration_count", 0)
    exceeded_allowed_iterations = iteration_count >= MAX_TOOL_CALL_ITERATIONS

    # If the LLM made no tool calls, we finish.
    if not last_message.tool_calls or exceeded_allowed_iterations:
        return Command(goto=END)

    # This is the core logic for executing tools and updating state.
    all_tool_messages = []
    chronology_events = state.get("chronology_events", [])

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
            result = await research_events_app.ainvoke(
                prompt=prompt, existing_events=chronology_events
            )
            all_tool_messages.append(
                ToolMessage(
                    content=str(result), tool_call_id=tool_call["id"], name=tool_name
                )
            )

    conversation_summary = await create_messages_summary(state, all_tool_messages)
    # The Command helper tells the graph where to go next and what state to update.
    return Command(
        goto="supervisor",
        update={
            "chronology_events": chronology_events,
            "conversation_history": all_tool_messages,
            "conversation_summary": conversation_summary,
        },
    )


workflow = StateGraph(SupervisorState, input_schema=SupervisorStateInput)

# Add the two core nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("supervisor_tools", supervisor_tools_node)

workflow.add_edge(START, "supervisor")


graph = workflow.compile()
