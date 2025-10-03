import os

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool


@tool(
    description="Mandatory reflection tool. Analyze results and plan the next search query."
)
def think_tool(reflection: str) -> str:
    """Mandatory reflection step. Use this to analyze the last result, identify gaps, and formulate the EXACT query for the next search.

    You MUST use this tool immediately after every ResearchEventsTool call.

    Analyze if an additional call to the ResearchEventsTool is needed to fill the gaps or the research is completed. When is completed, you must call the FinishResearchTool.

    The `reflection` argument must follow the structure defined in the system prompt, culminating in the precise search query you will use next.

    Args:
        reflection: Structured analysis of the last result, current gaps, and the PLANNED QUERY for the next step.

    Returns:
        Confirmation and instruction to proceed to the next step.
    """
    # The return value is crucial. It becomes the ToolMessage the LLM sees next.
    # By explicitly telling it what to do, we break the loop.
    return f"Reflection recorded. {reflection}"


def get_api_key_for_model(model_name: str, config: RunnableConfig):
    """Get API key for a specific model from environment or config."""
    model_name = model_name.lower()

    if model_name.startswith("openai:"):
        return os.getenv("OPENAI_API_KEY")
    elif model_name.startswith("anthropic:"):
        return os.getenv("ANTHROPIC_API_KEY")
    elif model_name.startswith("google"):
        print("GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY"))
        return os.getenv("GOOGLE_API_KEY")
    elif model_name.startswith("ollama:"):
        # Ollama doesn't need API key
        return None
    return None
