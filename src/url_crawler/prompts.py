# --- Prompt 1: For extracting events from a small text chunk ---

# --- Prompt 1: For extracting events from a small text chunk ---
EXTRACT_EVENTS_PROMPT = """
You are a strict Biographical Event Selector for the author {historical_figure}. Your task is to distinguish significant personal life events from information about their creative works.

**RULES:**
- **KEEP (Life Events):** Birth, death, marriage, children, education, moving country, military service, major illness, or personal hardships.
- **DISCARD (Work-Related Content):** The creation, publication, plot, or reception of any work (book, film, etc.). Also discard analysis of their literary style, influence, and posthumous events.

You must always select one of the tools below based on these rules.

<TOOLS>
1. RelevantChunk. The entire chunk describes a significant life event according to the rules.
ARGS : 
explanation: A short explanation of why the event is a key part of their personal life.

2. PartialChunk. The chunk mixes a life event with work-related content. Extract ONLY the life event.
ARGS: 
relevant_content: The exact text describing the significant life event. All work-related content must be removed.
explanation: A short explanation of what was kept and why the rest was discarded.

3. IrrelevantChunk. The chunk is entirely work-related content or a trivial detail.
ARGS: 
explanation: A short explanation of why the chunk is irrelevant (e.g., "Discusses only the plot of a book.").
</TOOLS>

<Text to Analyze>
{text_chunk}
</Text to Analyze>

You must call one of the tools defined above.

Never return plain text, always invoke exactly one tool.
"""


# --- Prompt 2: For consolidating new events with the existing summary ---
CONSOLIDATE_SUMMARY_PROMPT = """You are a biographical assistant. Your task is to consolidate new biographical events with a previous summary for {historical_figure}.

**Instructions**:
- Analyze the "New Extracted Events" and merge them into the "Previous Event Summary".
- **UPDATE** existing events if new information provides more detail.
- **ADD** new events that don't already exist.
- **MAINTAIN** a chronological order.
- **ELIMINATE** all duplicates.

**Output Format**:
- A single, comprehensive, and de-duplicated list in bullet points.

<Input>
New Extracted Events:
----
{newly_extracted_events}

Previous Event Summary:
----
{previous_events_summary}
</Input>

<Output>
Provide the single, consolidated, and chronological list of biographical events.
</Output>
"""
