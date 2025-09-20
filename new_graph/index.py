# src/krono_researcher.py

from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import START, StateGraph
from langgraph.graph.state import RunnableConfig
from langgraph.types import Command

from new_graph.prompts import (
    CREATE_EVENT_SUMMARY_PROMPT,
    compress_research_system_prompt,
    research_system_prompt,
)
from new_graph.state import (
    Chronology,
    ResearcherState,
)
from new_graph.utils import (
    configurable_model,
    execute_tool_safely,
    get_all_tools,
    structured_model,
    url_crawl,
)

load_dotenv()


async def researcher(
    state: ResearcherState, config: RunnableConfig
) -> Command[Literal["researcher_tools"]]:
    """Node 1: The "Brain". Decides the next action and which node to go to."""
    print("\n--- 🧠 RESEARCHER ---")

    historical_figure = state["historical_figure"]
    if not historical_figure:
        raise ValueError("Historical figure is required")

    # Logic to decide if we should end is now INSIDE this node.
    messages = state.get("messages", [])
    messages = [
        SystemMessage(
            content=research_system_prompt.format(historical_figure=historical_figure)
        )
    ] + messages

    tools = await get_all_tools(config)
    research_model = configurable_model.bind_tools(tools)
    response = await research_model.ainvoke(messages)

    return Command(
        goto="researcher_tools",
        update={
            "messages": [response],
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1,
        },
    )


async def researcher_tools(
    state: ResearcherState, config: RunnableConfig
) -> Command[Literal["researcher", "compress_research"]]:
    """Node 2: The "Worker". Executes tools and always proceeds to the processing step."""
    print("\n--- 🛠️ EXECUTING TOOLS ---")
    most_recent_message = state["messages"][-1]

    # Step 1: Check exit conditions
    research_complete_tool_call = any(
        tool_call["name"] == "ResearchComplete"
        for tool_call in most_recent_message.tool_calls
    )

    if (
        not isinstance(most_recent_message, AIMessage)
        or not most_recent_message.tool_calls
        or research_complete_tool_call
    ):
        return Command(goto="compress_research")  # Go back if no tools to execute

    # Step 2: Process all tool calls together (both think_tool and url_crawl)
    all_tool_messages = []

    # Step 3: Handle think_tool calls (strategic reflection)
    think_tool_calls = [
        tool_call
        for tool_call in most_recent_message.tool_calls
        if tool_call["name"] == "think_tool"
    ]

    for tool_call in think_tool_calls:
        reflection_content = tool_call["args"]["reflection_and_plan"]
        all_tool_messages.append(
            ToolMessage(
                content=f"Reflection recorded: {reflection_content}",
                name="think_tool",
                tool_call_id=tool_call["id"],
            )
        )

    # Step 4: Handle Url_crawl calls (url crawling)
    url_crawl_calls = [
        tool_call
        for tool_call in most_recent_message.tool_calls
        if tool_call["name"] == "url_crawl"
    ]
    event_summary = state.get("event_summary", "")
    for tool_call in url_crawl_calls:
        url = tool_call["args"]["url"]
        result = await execute_tool_safely(url_crawl, tool_call["args"], config)
        event_summary = await update_event_summary(state, result)
        all_tool_messages.append(
            ToolMessage(
                content=f"Url crawled: {url}",
                name="url_crawl",
                tool_call_id=tool_call["id"],
            )
        )

    return Command(
        goto="researcher",
        update={"messages": all_tool_messages, "event_summary": event_summary},
    )


async def update_event_summary(state: ResearcherState, result: str) -> str:
    """Updates the event summary with the new result."""
    prompt = CREATE_EVENT_SUMMARY_PROMPT.format(
        historical_figure=state.get("historical_figure", ""),
        previous_events_summary=state.get("event_summary", ""),
        new_text=result,
    )
    response = await configurable_model.ainvoke(prompt)

    return response


async def compress_research(state: ResearcherState, config: RunnableConfig):
    """Extracts chronological events from research findings and structures them.

    This function processes all research messages, identifies key life events
    of the subject, and formats them into a structured list of ChronologyEvent objects.

    Args:
        state: Current researcher state with accumulated research messages.
        config: Runtime configuration with model settings.

    Returns:
        Dictionary containing a list of structured chronology events and raw notes.
    """
    # Step 1: Configure the model

    structured_llm = structured_model.with_structured_output(Chronology)

    messages = state.get("messages", [])
    messages.append(
        HumanMessage(
            content=compress_research_system_prompt.format(
                events_summary=state.get("event_summary", "")
            )
        )
    )

    response = await structured_llm.ainvoke(messages)

    return {
        # Return an empty list to match the required type for 'compressed_research'
        "compressed_research": response.events,
    }


## if the research tool goes throug a url_crawl. then go to new node called event_summary and instead of passing the whole response to the state pass just a succesfull message.
## events_summary is used every time the agent goes through a url_crawl and the prompt contains also the previous events_summary. it is overwritten.

# if the resarch tool goes through a think_tool. then save into the messages state as the complete response that says what to think afterwars,
# but these think_tool responses could be also overriden when going to the succesive think_tool, as the previous message is not needed anymore and bloats the context.


# --- 4. Define the Graph ---

builder = StateGraph(ResearcherState)

# Add the four nodes
builder.add_node("researcher", researcher)
builder.add_node("researcher_tools", researcher_tools)
builder.add_node("compress_research", compress_research)
# Define the workflow edges
builder.add_edge(START, "researcher")

# Compile the graph
app = builder.compile()

# --- 5. Run the Agent ---


# async def run_agent():
#     historical_figure = "Albert Einstein"

#     # Your original system prompt can now be the first message in the state
#     system_prompt = f"""
# You are a research assistant. Your task is to research a historical figure by extracting key life events from Wikipedia and Britannica.
# Historical figure: {historical_figure}
# You must operate in a strict **search -> reflect** loop.
# 1. Call `url_crawl` to gather information from Wikipedia or Britannica.
# 2. CRITICAL: After crawling, you MUST call `think_tool` to analyze the results and decide your next action.
# 3. Repeat until you have crawled both sources, then call `ResearchComplete`.
#     """

#     initial_state = {
#         "historical_figure": historical_figure,
#         "messages": [SystemMessage(content=system_prompt)],
#         "retrieved_documents": [],
#         "tool_call_iterations": 0,
#     }

#     # Stream the execution to see the agent's steps
#     async for event in app.astream_events(initial_state, version="v1"):
#         kind = event["event"]
#         if kind == "on_chain_end":
#             # Print the final state
#             print("\n\n--- ✅ FINAL STATE ---")
#             print(event["data"]["output"])


# if __name__ == "__main__":
#     asyncio.run(run_agent())
