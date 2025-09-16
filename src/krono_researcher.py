# src/krono_researcher.py

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    ToolMessage,
    filter_messages,
)
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import Literal
from langgraph.graph.state import RunnableConfig
import asyncio
from langgraph.types import Command

from src.configuration import Configuration
from src.prompts import (
    compress_research_simple_human_message,
    compress_research_system_prompt,
    lead_researcher_prompt,
    research_system_prompt,
)
from src.utils import get_all_tools, get_api_key_for_model, think_tool
from src.state import (
    ConductResearch,
    ResearchComplete,
    ResearcherOutputState,
    ResearcherState,
    SupervisorState,
    SupervisorStateInput,
)

load_dotenv()


# Initialize a configurable model that we will use throughout the agent
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


async def supervisor(
    state: SupervisorState, config: RunnableConfig
) -> Command[Literal["supervisor_tools"]]:
    # Step 1: Configure the supervisor model with available tools
    configurable = Configuration.from_runnable_config(config)
    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
        "tags": ["langsmith:nostream"],
    }
    person_researcher_tools = [ConductResearch, ResearchComplete, think_tool]
    person_to_research = state.get("person_to_research", "")

    if not person_to_research:
        raise ValueError("Person to research is required")

    research_model = (
        configurable_model.bind_tools(person_researcher_tools)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(research_model_config)
    )

    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    if research_iterations == 0:
        print("first iteration")
        supervisor_messages = [
            SystemMessage(content=lead_researcher_prompt),
            HumanMessage(content=person_to_research),
        ]

    # Step 2: Invoke the supervisor model with the search messages
    response = await research_model.ainvoke(supervisor_messages)

    if research_iterations == 0:
        messages_to_add = supervisor_messages + [response]
    else:
        # On subsequent runs, just add the latest AI response.
        messages_to_add = [response]

    return Command(
        goto="supervisor_tools",
        update={
            "supervisor_messages": messages_to_add,
            "research_iterations": state.get("research_iterations", 0) + 1,
        },
    )


async def supervisor_tools(
    state: SupervisorState, config: RunnableConfig
) -> Command[Literal["supervisor", END]]:
    """Execute tools called by the supervisor, including research delegation and strategic thinking.

    This function handles three types of supervisor tool calls:
    1. think_tool - Strategic reflection that continues the conversation
    2. ConductResearch - Delegates research tasks to sub-researchers
    3. ResearchComplete - Signals completion of research phase

    Args:
        state: Current supervisor state with messages and iteration count
        config: Runtime configuration with research limits and model settings

    Returns:
        Command to either continue supervision loop or end research phase
    """
    # Step 1: Extract current state and check exit conditions
    configurable = Configuration.from_runnable_config(config)
    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    most_recent_message = supervisor_messages[-1]

    # Define exit criteria for research phase
    exceeded_allowed_iterations = (
        research_iterations > configurable.max_researcher_iterations
    )
    no_tool_calls = not most_recent_message.tool_calls
    research_complete_tool_call = any(
        tool_call["name"] == "ResearchComplete"
        for tool_call in most_recent_message.tool_calls
    )

    # Exit if any termination condition is met
    if exceeded_allowed_iterations or no_tool_calls or research_complete_tool_call:
        return Command(goto=END)

    # Step 2: Process all tool calls together (both think_tool and ConductResearch)
    all_tool_messages = []
    update_payload = {"supervisor_messages": []}

    # Handle think_tool calls (strategic reflection)
    think_tool_calls = [
        tool_call
        for tool_call in most_recent_message.tool_calls
        if tool_call["name"] == "think_tool"
    ]

    for tool_call in think_tool_calls:
        reflection_content = tool_call["args"]["reflection"]
        all_tool_messages.append(
            ToolMessage(
                content=f"Reflection recorded: {reflection_content}",
                name="think_tool",
                tool_call_id=tool_call["id"],
            )
        )

    # Handle ConductResearch calls (research delegation)
    conduct_research_calls = [
        tool_call
        for tool_call in most_recent_message.tool_calls
        if tool_call["name"] == "ConductResearch"
    ]

    if conduct_research_calls:
        # Execute research tasks in parallel
        research_tasks = [
            researcher_subgraph.ainvoke(
                {
                    "researcher_messages": [
                        HumanMessage(content=tool_call["args"]["research_topic"])
                    ],
                    "research_topic": tool_call["args"]["research_topic"],
                },
                config,
            )
            for tool_call in conduct_research_calls
        ]

        tool_results = await asyncio.gather(*research_tasks)

        # Create tool messages with research results
        for observation, tool_call in zip(tool_results, conduct_research_calls):
            all_tool_messages.append(
                ToolMessage(
                    content=observation.get(
                        "compressed_research",
                        "Error synthesizing research report: Maximum retries exceeded",
                    ),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )

    # Step 3: Return command with all tool results
    update_payload["supervisor_messages"] = all_tool_messages
    return Command(goto="supervisor", update=update_payload)


########################################################
# Researcher Subgraph
########################################################


async def researcher(
    state: ResearcherState, config: RunnableConfig
) -> Command[Literal["researcher_tools"]]:
    """Individual researcher that conducts focused research on specific topics."""

    configurable = Configuration.from_runnable_config(config)
    tools = await get_all_tools(config)
    if len(tools) == 0:
        raise ValueError(
            "No tools found to conduct research: Please configure your "
            "search API to your configuration."
        )

    # Step 2: Configure the researcher model with tools
    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
        "tags": ["langsmith:nostream"],
    }

    # Configure model with tools, retry logic, and settings
    research_model = (
        configurable_model.bind_tools(tools)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(research_model_config)
    )

    # Step 3: Generate researcher response with system context
    messages = [SystemMessage(content=research_system_prompt)] + state.get(
        "researcher_messages", []
    )
    response = await research_model.ainvoke(messages)

    # Step 4: Update state and proceed to tool execution
    return Command(
        goto="researcher_tools",
        update={
            "researcher_messages": [response],
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1,
        },
    )


# Tool Execution Helper Function
async def execute_tool_safely(tool, args, config):
    """Safely execute a tool with error handling."""
    try:
        return await tool.ainvoke(args, config)
    except Exception as e:
        return f"Error executing tool: {str(e)}"


async def researcher_tools(
    state: ResearcherState, config: RunnableConfig
) -> Command[Literal["researcher", "compress_research"]]:
    """Execute tools called by the researcher, including search tools and strategic thinking.

    This function handles various types of researcher tool calls:
    1. think_tool - Strategic reflection that continues the research conversation
    2. Search tools (tavily_search, web_search) - Information gathering
    3. MCP tools - External tool integrations
    4. ResearchComplete - Signals completion of individual research task

    Args:
        state: Current researcher state with messages and iteration count
        config: Runtime configuration with research limits and tool settings

    Returns:
        Command to either continue research loop or proceed to compression
    """
    # Step 1: Extract current state and check early exit conditions
    configurable = Configuration.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])
    most_recent_message = researcher_messages[-1]

    # Early exit if no tool calls were made (including native web search)
    has_tool_calls = bool(most_recent_message.tool_calls)

    if not has_tool_calls:
        return Command(goto="compress_research")

    # Step 2: Handle other tool calls (search, MCP tools, etc.)
    tools = await get_all_tools(config)
    tools_by_name = {
        tool.name if hasattr(tool, "name") else tool.get("name", "web_search"): tool
        for tool in tools
    }

    # Execute all tool calls in parallel
    tool_calls = most_recent_message.tool_calls
    tool_execution_tasks = [
        execute_tool_safely(tools_by_name[tool_call["name"]], tool_call["args"], config)
        for tool_call in tool_calls
    ]
    observations = await asyncio.gather(*tool_execution_tasks)

    # Create tool messages from execution results
    tool_outputs = [
        ToolMessage(
            content=observation, name=tool_call["name"], tool_call_id=tool_call["id"]
        )
        for observation, tool_call in zip(observations, tool_calls)
    ]

    # Step 3: Check late exit conditions (after processing tools)
    exceeded_iterations = (
        state.get("tool_call_iterations", 0) >= configurable.max_react_tool_calls
    )
    research_complete_called = any(
        tool_call["name"] == "ResearchComplete"
        for tool_call in most_recent_message.tool_calls
    )

    if exceeded_iterations or research_complete_called:
        # End research and proceed to compression
        return Command(
            goto="compress_research", update={"researcher_messages": tool_outputs}
        )

    # Continue research loop with tool results
    return Command(goto="researcher", update={"researcher_messages": tool_outputs})


async def compress_research(state: ResearcherState, config: RunnableConfig):
    """Compress and synthesize research findings into a concise, structured summary.

    This function takes all the research findings, tool outputs, and AI messages from
    a researcher's work and distills them into a clean, comprehensive summary while
    preserving all important information and findings.

    Args:
        state: Current researcher state with accumulated research messages
        config: Runtime configuration with compression model settings

    Returns:
        Dictionary containing compressed research summary and raw notes
    """
    # Step 1: Configure the compression model
    configurable = Configuration.from_runnable_config(config)
    synthesizer_model = configurable_model.with_config(
        {
            "model": configurable.compression_model,
            "max_tokens": configurable.compression_model_max_tokens,
            "api_key": get_api_key_for_model(configurable.compression_model, config),
            "tags": ["langsmith:nostream"],
        }
    )

    # Step 2: Prepare messages for compression
    researcher_messages = state.get("researcher_messages", [])
    print("length of researcher_messages", len(researcher_messages))
    # Add instruction to switch from research mode to compression mode
    researcher_messages.append(
        HumanMessage(content=compress_research_simple_human_message)
    )

    # Step 3: Attempt compression with retry logic for token limit issues
    synthesis_attempts = 0
    max_attempts = 3

    while synthesis_attempts < max_attempts:
        try:
            print("attempting compression", synthesis_attempts)
            # Create system prompt focused on compression task
            compression_prompt = compress_research_system_prompt
            messages = [SystemMessage(content=compression_prompt)] + researcher_messages

            # Execute compression
            response = await synthesizer_model.ainvoke(messages)
            print("response", response)
            # Extract raw notes from all tool and AI messages
            raw_notes_content = "\n".join(
                [
                    str(message.content)
                    for message in filter_messages(
                        researcher_messages, include_types=["tool", "ai"]
                    )
                ]
            )

            # Return successful compression result
            return {
                "compressed_research": str(response.content),
                "raw_notes": raw_notes_content,
            }

        except Exception as e:
            print("error attempting compression", e)
            synthesis_attempts += 1
            # For other errors, continue retrying
            continue

    # Step 4: Return error result if all attempts failed
    raw_notes_content = "\n".join(
        [
            str(message.content)
            for message in filter_messages(
                researcher_messages, include_types=["tool", "ai"]
            )
        ]
    )

    return {
        "compressed_research": "Error synthesizing research report: Maximum retries exceeded",
        "raw_notes": [raw_notes_content],
    }


researcher_builder = StateGraph(
    ResearcherState, output=ResearcherOutputState, config_schema=Configuration
)
# Add researcher nodes for research execution and compression
researcher_builder.add_node("researcher", researcher)  # Main researcher logic
researcher_builder.add_node(
    "researcher_tools", researcher_tools
)  # Tool execution handler
researcher_builder.add_node(
    "compress_research", compress_research
)  # Research compression

# Define researcher workflow edges
researcher_builder.add_edge(START, "researcher")  # Entry point to researcher
researcher_builder.add_edge("compress_research", END)  # Exit point after compression

# Compile researcher subgraph for parallel execution by supervisor
researcher_subgraph = researcher_builder.compile()

# Build the graph
graph_builder = StateGraph(SupervisorState, input_schema=SupervisorStateInput)

graph_builder.add_node("supervisor", supervisor)
graph_builder.add_node("supervisor_tools", supervisor_tools)

graph_builder.add_edge(START, "supervisor")

graph = graph_builder.compile()
