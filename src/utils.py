from langchain_core.messages import MessageLikeRepresentation
from langchain_core.tools import tool
from src.llm_service import model_for_structured
from src.prompts import create_messages_summary_prompt
from src.state import SupervisorState


async def create_messages_summary(
    state: SupervisorState, new_messages: list[MessageLikeRepresentation]
) -> str:
    previous_messages_summary = state.get("conversation_summary", "")
    """Create a summary of the messages."""
    prompt = create_messages_summary_prompt.format(
        new_messages=new_messages,
        previous_messages_summary=previous_messages_summary,
    )

    response = await model_for_structured.ainvoke(prompt)
    return response.content


@tool(
    description="Mandatory reflection tool. Analyze results and plan the next search query."
)
def think_tool(reflection: str) -> str:
    """Mandatory reflection step. Use this to analyze the last result, identify gaps, and formulate the EXACT query for the next search.

    You MUST use this tool immediately after every ResearchEventsTool call.

    The `reflection` argument must follow the structure defined in the system prompt, culminating in the precise search query you will use next.

    Args:
        reflection: Structured analysis of the last result, current gaps, and the PLANNED QUERY for the next step.

    Returns:
        Confirmation and instruction to proceed to the next step.
    """
    # The return value is crucial. It becomes the ToolMessage the LLM sees next.
    # By explicitly telling it what to do, we break the loop.
    return f"Reflection recorded. {reflection}"
