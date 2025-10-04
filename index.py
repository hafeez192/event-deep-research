from typing import Dict, List, TypedDict
from langchain_core.messages import AIMessage, HumanMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.graph import CompiledGraph
from pydantic import BaseModel, Field


class BiographicEventCheck(BaseModel):
    contains_biographic_event: bool = Field(
        description="Whether the text chunk contains biographical events"
    )


class ChunkState(TypedDict):
    text: str
    chunks: List[str]
    results: Dict[str, bool]


def split_text(state: ChunkState) -> ChunkState:
    """Split text into smaller chunks."""
    text = state["text"]
    chunk_size = 200
    chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    return {"chunks": chunks}


def check_chunk_for_events(state: ChunkState) -> ChunkState:
    """Check each chunk for biographical events using structured output."""
    model = ChatOllama(model="gemma3:4b")
    results = {}
    
    for i, chunk in enumerate(state["chunks"]):
        prompt = f"""
        Analyze this text chunk and determine if it contains SPECIFIC biographical events.
        
        ONLY mark as true if the chunk contains:
        - Birth/death dates or locations
        - Marriage ceremonies or relationships
        - Educational enrollment or graduation
        - Career appointments or job changes
        - Awards, prizes, or honors received
        - Relocations to new cities/countries
        - Major discoveries or inventions
        
        DO NOT mark as true for:
        - General descriptions or background information
        - Character traits or personality descriptions
        - General statements about time periods
        - Descriptions of places without personal connection
        - General knowledge or context
        
        The event must be specific and concrete, not general background.
        
        Text chunk: "{chunk}"
        """
        
        structured_model = model.with_structured_output(BiographicEventCheck)
        result = structured_model.invoke(prompt)
        results[f"chunk_{i}"] = result.contains_biographic_event
    
    return {"results": results}


def create_biographic_event_graph() -> CompiledGraph:
    """Create and return the biographic event detection graph."""
    graph = StateGraph(ChunkState)
    
    graph.add_node("split_text", split_text)
    graph.add_node("check_events", check_chunk_for_events)
    
    graph.add_edge(START, "split_text")
    graph.add_edge("split_text", "check_events")
    graph.add_edge("check_events", END)
    
    return graph.compile()


if __name__ == "__main__":
    sample_text = """
    Marie Curie, born Maria Skłodowska in Warsaw in 1867, was a monumental figure in science.
    Her early years in Poland were marked by a thirst for knowledge, a difficult path for women at the time.
    This passion led her to leave her homeland, and in 1891, she moved to Paris to enroll at the Sorbonne.
    The city was a hub of intellectual activity. She dedicated herself to her studies.
    She met her future husband, Pierre Curie, a professor in the School of Physics and Chemistry.
    They married in a simple ceremony in 1895. Their partnership would change the world of physics.
    Working together, the couple discovered two new elements, polonium and radium.
    This groundbreaking work on radioactivity earned her, Pierre, and Henri Becquerel the Nobel Prize in Physics in 1903, which was awarded in Stockholm.

    Tragedy struck in 1906 when Pierre was killed in a street accident in Paris. Despite her grief,
    Marie continued their work. She took over his professorship at the Sorbonne, becoming the first woman to hold the position.
    In 1911, she was awarded a second Nobel Prize, this time in Chemistry, for her work in isolating pure radium.
    During World War I, she developed mobile radiography units to provide X-ray services to field hospitals.
    After the war, she continued her research at the Radium Institute in Paris.
    She died in 1934 in Passy, France, from aplastic anemia, likely caused by her long-term exposure to radiation.
    """
    
    graph = create_biographic_event_graph()
    initial_state = {"text": sample_text}
    result = graph.invoke(initial_state)
    
    print("Biographic Event Detection Results:")
    for chunk_id, has_event in result["results"].items():
        print(f"{chunk_id}: {has_event}")