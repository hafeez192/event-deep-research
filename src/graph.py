from typing import Literal

from langchain_core.messages import ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from src.llm_service import model_for_tools
from src.prompts import lead_researcher_prompt
from src.state import (
    CategoriesWithEvents,
    FinishResearchTool,
    ResearchEventsTool,
    SupervisorState,
    SupervisorStateInput,
)
from src.utils import create_messages_summary, think_tool

MAX_TOOL_CALL_ITERATIONS = 4


async def supervisor_node(
    state: SupervisorState,
) -> Command[Literal["supervisor_tools"]]:
    """The 'brain' of the agent. It decides the next action."""
    prompt = lead_researcher_prompt.format(
        person_to_research=state["person_to_research"],
        existing_events=state.get("existing_events", []),
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

    print("summary", prompt)

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
    existing_events = state.get("existing_events", [])

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
            prompt = tool_args["research_question"]
            # result = await research_events_app.ainvoke(
            #     prompt=prompt, existing_events=existing_events
            # )
            # combined_events = result["combined_events"]
            result = ""

            mockCombinedEvents = (
                CategoriesWithEvents(
                    early="- Henry Valentine Miller was born in New York City on December 26, 1891.\n- He lived at 450 East 85th Street in Manhattan during his early years.\n- His family moved to Williamsburg, Brooklyn when he was around nine years old, and later to Bushwick.\n- Miller attended Eastern District High School in Williamsburg.\n- He briefly studied at the City College of New York.\n- Miller became active with the Socialist Party of America.\n- He admired Hubert Harrison.",
                    personal="- Miller married Beatrice Sylvas Wickens in 1917 and divorced her in 1923. They had a daughter, Barbara.\n- Miller met June Mansfield around 1924 and they married on June 1, 1924.\n- Miller lived with Kronski at some point between 1926-1927.\n- Miller moved to Paris in 1930. He spent several months there with June in 1938. During his ten-year stay in Paris, Miller became fluent in French.\n- Miller returned to New York in 1940 and moved to California in 1942, initially residing just outside Hollywood in Beverly Glen before settling in Big Sur in 1944.\n- Miller married Janina Martha Lepska in 1944 and had two children with her. They divorced in 1952.\n- Miller married Eve McClure in 1953 but they divorced in 1960.\n- Miller married Hiroko Tokuda in 1967 but they divorced in 1977.",
                    career="- Miller quit Western Union to dedicate himself to writing in 1924.\n- He was supported financially by Roland Freedman who paid June Mansfield to write a novel, pretending it was her work and reviewing Miller's writing weekly.\n- Miller moved to Paris unaccompanied in 1930.\n- He was employed as a proofreader for the Chicago Tribune Paris edition in 1931 thanks to Alfred Perlès.\n- This period marked a creative time for Miller, and he began building a network of authors around Villa Seurat.\n- Lawrence Durrell became a lifelong friend.\n- Anaïs Nin and Hugh Guiler financially supported Miller between 1931-1934, covering his living expenses including rent at 18 Villa Seurat.\n- Nin became his lover and financed the first printing of Tropic of Cancer in 1934 with money from Otto Rank.",
                    legacy="- Miller was nominated for the Nobel Prize in Literature by University of Copenhagen professor Allan Philip in 1973.\n- Miller participated in the filming of Reds in the late 1970s.\n- Miller held an ongoing correspondence of over 1,500 letters with Brenda Venus between 1978 and 1981.\n- Miller died on June 7, 1980 at his home in Pacific Palisades, Los Angeles, aged 88.\n- The Henry Miller Memorial Library was founded in Big Sur in 1981 by Emil White.",
                ),
            )
            combined_events = mockCombinedEvents
            existing_events = combined_events
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
            "existing_events": existing_events,
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
