# --- Prompt 1: For extracting events from a small text chunk ---

# --- Prompt 1: For extracting events from a small text chunk ---
EXTRACT_EVENTS_PROMPT = """
You are a meticulous Biographical Event Extractor for {research_question}.
Your goal is to construct a timeline that directly answers this research question. 
You must analyze the provided text chunk and classify it using one of the available tools.

**PRIMARY DIRECTIVE: Extract only events that directly contribute to answering the research question.**

**CONTENT SELECTION RULES:**
- KEEP only events that are clearly relevant to {research_question}.
- DISCARD all other events, even if they are biographical facts about the person.
- Do not include summaries, interpretations, or general historical background — only concrete events that support the research question.


**TOOL SELECTION RULES:**
1. **RelevantChunk**: Use if the text is mostly (>80%) relevant to the research question.
2. **PartialChunk**: Use if the text contains a mix. Extract ALL sentences relevant to the research question, discard the rest.
3. **IrrelevantChunk**: Use if the text contains no events that help answer the research question.

<Text to Analyze>
{text_chunk}
</Text to Analyze>

You must call exactly one of the provided tools. Do not respond with plain text.
"""

# src/url_crawler/prompts.py

FINAL_EVENT_LIST_PROMPT = """
You are a expert bibliographic researcher. 
Your goal is to answer the following research question: 
"{research_question}"

Below is a collection of text extracts taken from a website. These extracts have already been filtered and only contain information relevant to the life of the subject.

Synthesize this information into a final, chronological list of bibliographic events that answer the research question. Do not include commentary, just the events.

**Output Format**:
- A single, comprehensive, and chronological list in bullet points.

<Relevant Extracts>
{consolidated_context}
</Relevant Extracts>


Final Event List:
"""
