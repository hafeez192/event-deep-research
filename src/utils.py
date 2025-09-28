from langchain_core.messages import MessageLikeRepresentation
from langchain_core.tools import tool
from src.llm_service import model_for_big_queries
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

    response = await model_for_big_queries.ainvoke(prompt)
    return response.content


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
