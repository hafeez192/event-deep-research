# --- Prompt 1: For extracting events from a small text chunk ---

# --- Prompt 1: For extracting events from a small text chunk ---
EXTRACT_EVENTS_PROMPT = """
You are a meticulous Biographical Event Extractor for {historical_figure}.
Your goal is to build a comprehensive personal timeline. You must analyze the provided text chunk and classify it using one of the available tools.

**Primary Directive: Distinguish the person's LIFE from their WORK.**

**RULES FOR CONTENT SELECTION:**
- **KEEP (Life Events):** Focus on core biographical facts. This includes:
  - Personal relationships (marriage, divorce, children, affairs, key friendships).
  - Major life changes (moving to a new city/country, changing careers).
  - Personal circumstances (financial state, health, military service, education).
  - Key dates (birth, death).

- **DISCARD (Work-Related Content):** Ignore everything else, specifically:
  - Summaries, plots, or analysis of their books, art, or achievements.
  - The reception or legacy of their work.
  - References to them after their death (unless it's the date of death itself).
  - General historical context not directly involving them.

**TOOL SELECTION GUIDELINES:**

1.  **RelevantChunk**: Choose this if the text is almost entirely (>80%) about personal life events. The whole chunk is valuable.
2.  **PartialChunk**: Choose this if the text is a mix of personal life events and work-related details. You MUST extract ALL sentences about their life and discard the rest.
3.  **IrrelevantChunk**: Choose this if the text is completely about their work, its legacy, or other non-biographical topics.

<Text to Analyze>
{text_chunk}
</Text to Analyze>

You must call exactly one of the provided tools. Do not respond with plain text.
"""


create_event_list_prompt = """You are a biographical assistant. Your task is to convert blocks of text that contains events of a person into single events where the date, description of the event, location of the event are included for {historical_figure}.

**Instructions**:
- Analyze the "New Extracted Events" and convert them into single events where the date, description of the event, location of the event are included.
- **MAINTAIN** a chronological order.

**Output Format**:
- A single, comprehensive, and chronological list in bullet points.

<Input>
New Extracted Events:
----
{newly_extracted_events}

</Input>

<Output>
Provide the single, consolidated, and chronological list of biographical events.
</Output>
"""
