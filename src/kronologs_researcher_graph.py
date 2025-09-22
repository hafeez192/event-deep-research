# src/krono_researcher.py

from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import START, StateGraph
from langgraph.graph.state import RunnableConfig
from langgraph.types import Command

from src.prompts import (
    research_system_prompt,
    step1_clean_and_order_prompt,
    step2_structure_events_prompt,
)
from src.state import (
    Chronology,
    InputResearcherState,
    ResearcherOutputState,
    ResearcherState,
)
from src.url_crawler.url_krawler_graph import url_crawler_graph
from src.utils import (
    count_tokens,
    get_all_tools,
    model_for_tools,
    structured_model,
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
    research_model = model_for_tools.bind_tools(tools)

    messages_token_count = count_tokens(messages)
    print("MESSAGES TOKEN COUNT", messages_token_count)
    response = await research_model.ainvoke(messages)

    print("RESPONSE", response)
    return Command(
        goto="researcher_tools",
        update={
            "messages": [response],
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1,
        },
    )


async def researcher_tools(
    state: ResearcherState, config: RunnableConfig
) -> Command[Literal["researcher", "clean_and_order_events"]]:
    """Node 2: The "Worker". Executes tools and always proceeds to the processing step."""
    print("\n--- 🛠️ EXECUTING TOOLS ---")
    most_recent_message = state["messages"][-1]

    # Step 1: Check exit conditions
    research_complete_tool_call = any(
        tool_call["name"] == "research_complete"
        for tool_call in most_recent_message.tool_calls
    )

    if (
        not isinstance(most_recent_message, AIMessage)
        or not most_recent_message.tool_calls
        or research_complete_tool_call
    ):
        return Command(goto="clean_and_order_events")  # Go back if no tools to execute

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
    raw_notes = state.get("raw_notes", {})
    event_summary = state.get("event_summary", "")
    for tool_call in url_crawl_calls:
        url = tool_call["args"]["url"]
        result = await url_crawler_graph.ainvoke(
            {"url": url, "historical_figure": state["historical_figure"]}
        )
        event_summary = result["events"]
        raw_notes[url] = result["content"]
        all_tool_messages.append(
            ToolMessage(
                content=f"Url crawled: {url}",
                name="url_crawl",
                tool_call_id=tool_call["id"],
            )
        )

    return Command(
        goto="researcher",
        update={
            "messages": all_tool_messages,
            "event_summary": event_summary,
            "raw_notes": raw_notes,
        },
    )


async def clean_and_order_events(
    state: ResearcherState, config: RunnableConfig
) -> Command[Literal["structure_events"]]:
    """Step 1: Cleans, de-duplicates, and chronologically orders the raw notes.

    Args:
        state: Current researcher state with accumulated research messages.
        config: Runtime configuration with model settings.

    Returns:
        Command to proceed to structure_events with updated state.
    """
    print("--- Step 1: Cleaning and Ordering Events ---")

    prompt1 = step1_clean_and_order_prompt.format(
        events_summary=state.get("event_summary", "")
    )

    # Invoke the first model to get a clean, ordered string of events
    cleaning_response = await model_for_tools.ainvoke(prompt1)
    cleaned_events_text = cleaning_response.content

    print("--- Cleaned and Ordered Events Text ---")
    print(cleaned_events_text)
    print("---------------------------------------")

    # Update the state with cleaned events text
    updated_state = {
        "cleaned_events_text": cleaned_events_text,
        "event_summary": f"Processed: {cleaned_events_text[:100]}..."
        if len(cleaned_events_text) > 100
        else f"Processed: {cleaned_events_text}",
    }

    # Return Command to go to the next node with updated state
    return Command(goto="structure_events", update=updated_state)


async def structure_events(
    state: ResearcherState, config: RunnableConfig
) -> Command[Literal["__end__"]]:
    """Step 2: Structures the cleaned events into JSON format.

    Args:
        state: Current researcher state with cleaned events text.
        config: Runtime configuration with model settings.

    Returns:
        Dictionary containing a list of structured chronology events.
    """
    print("--- Step 2: Structuring Events into JSON ---")

    # Get the cleaned events from the previous step
    cleaned_events_text = state.get("cleaned_events_text", "")

    if not cleaned_events_text:
        print("Warning: No cleaned events text found in state")
        return {"compressed_research": []}

    structured_llm = structured_model.with_structured_output(Chronology)

    prompt2 = step2_structure_events_prompt.format(cleaned_events=cleaned_events_text)

    # Invoke the second model to get the final structured output
    structured_response = await structured_llm.ainvoke(prompt2)

    return {
        "compressed_research": structured_response.events,
    }


# --- 4. Define the Graph ---

builder = StateGraph(
    ResearcherState,
    input_schema=InputResearcherState,
    output_schema=ResearcherOutputState,
)

# Add the four nodes
builder.add_node("researcher", researcher)
builder.add_node("researcher_tools", researcher_tools)
builder.add_node("clean_and_order_events", clean_and_order_events)
builder.add_node("structure_events", structure_events)
# Define the workflow edges
builder.add_edge(START, "researcher")

# Compile the graph
app = builder.compile()


# if the resarch tool goes through a think_tool. then save into the messages state as the complete response that says what to think afterwars,
# but these think_tool responses could be also overriden when going to the succesive think_tool, as the previous message is not needed anymore and bloats the context.
