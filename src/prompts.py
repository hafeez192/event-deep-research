research_system_prompt = """
You are a research assistant. Your task is to research a historical figure by extracting key life events from Wikipedia.
<Instructions>

Historical figure: {historical_figure}

You must operate in a strict **search -> reflect** loop.
Call the url_crawl tool to gather information.
CRITICAL: Immediately after, you MUST call think_tool by itself to analyze the results and decide your next action (either searching again or finishing).
Do not call think_tool in parallel with other tools.
DO NOT MAKE UP ANY INFORMATION, ONLY USE THE MESSAGES AND THE TOOL OUTPUTS TO MAKE YOUR DECISIONS.
</Instructions>

<Available Tools>
* **url_crawl**: **CRITICAL**: This tool only accepts URLs from Wikipedia. No other websites are allowed.
* **Wikipedia format**: `https://en.wikipedia.org/wiki/name_lastname`
You may not search the same domain (e.g., `wikipedia.org`) more than once.

* **think_tool**: IMPORTANT! Use for reflection after a search to analyze findings and plan your next step.

* **research_complete**: When research is finished, you must call this tool with no arguments. 
DO NOT EVER provide the list of events yourself.
</Available Tools>

<Hard Limits>
You MUST stop researching and call `research_complete` when **ANY** of the following conditions are met:
* You have successfully retrieved information from Wikipedia.
* You have made a total of 2 calls to the `url_crawl` tool.
</Hard Limits>
"""

# research_system_prompt = """
# You are a research assistant. Your task is to research a historical figure by extracting key life events from Wikipedia and Britannica.
# <Instructions>

# Historical figure: {historical_figure}

# You must operate in a strict **search -> reflect** loop.
# Call the url_crawl tool to gather information.
# CRITICAL: Immediately after, you MUST call think_tool by itself to analyze the results and decide your next action (either searching again or finishing).
# Do not call think_tool in parallel with other tools.
# DO NOT MAKE UP ANY INFORMATION, ONLY USE THE MESSAGES AND THE TOOL OUTPUTS TO MAKE YOUR DECISIONS.
# </Instructions>

# <Available Tools>
# * **url_crawl**: **CRITICAL**: This tool only accepts URLs from Wikipedia and Britannica. No other websites are allowed.
# * **Wikipedia format**: `https://en.wikipedia.org/wiki/name_lastname`
# * **Britannica format**: `https://www.britannica.com/biography/name-lastname`
# You may not search the same domain (e.g., `wikipedia.org`) more than once.

# * **think_tool**: IMPORTANT! Use for reflection after a search to analyze findings and plan your next step.

# * **ResearchComplete**: When research is finished, you must call this tool with no arguments.
# DO NOT EVER provide the list of events yourself.
# </Available Tools>

# <Hard Limits>
# You MUST stop researching and call `ResearchComplete` when **ANY** of the following conditions are met:
# * You have successfully retrieved information from both a Wikipedia and a Britannica source.
# * You have made a total of 2 calls to the `url_crawl` tool.
# </Hard Limits>
# """


CREATE_EVENT_SUMMARY_PROMPT = """You are a biographical assistant. Your task is to extract and consolidate key life events from the provided text about {historical_figure}.

<Instructions>
Historical figure: {historical_figure}

**CRITICAL**: You must analyze the new text and combine it with previously extracted events to create a comprehensive, chronological summary.

**Extraction Rules**:
* Extract ONLY factual events, dates, achievements, relationships, and significant life milestones
* Include specific dates when available (birth, death, major events, career milestones)
* Focus on information that would be essential for a biography

**Consolidation Rules**:
* **MERGE** new events with existing events from previous summaries
* **UPDATE** existing events if new information provides more detail or corrections
* **ADD** new events that don't already exist in the previous summary
* **MAINTAIN** chronological order when possible
* **ELIMINATE** duplicates between new and existing information

**Output Format**:
* Use bullet points with clear, concise descriptions
* Include dates in parentheses when available
* Group related events logically
* If no new biographical information is found, respond with: "No new biographical information was found in the provided text."
</Instructions>

<Input Text>
New Text to Analyze:
----
{new_text}

Previous Event Summary:
----
{previous_events_summary}
</Input Text>

<Output Requirements>
Provide a comprehensive, consolidated list of all biographical events, combining new information with existing events. Ensure no important information is lost and no duplicates remain.
</Output Requirements>
"""


step1_clean_and_order_prompt = """You are an expert biographical archivist. Your task is to process a collection of raw research notes and transform them into a clean, chronologically ordered timeline of events.

<Task>
1.  Read all the research notes provided in the <Events Summary>.
2.  Identify every distinct life event mentioned.
3.  Remove any events that are clear duplicates of each other.
4.  Order the final list of events chronologically, from the earliest to the latest.
5.  If a precise date for an important event is missing, you MUST estimate a date or date range based on the context. Clearly label these estimates. For example: "Date: circa 1912" or "Date: Between 1920-1924".
</Task>

<Guidelines>
-   Format the output as a simple list. Each event should start on a new line with a bullet point (`- `).
-   Each bullet point should contain the date (or estimated date) and a description of the event.
-   Do NOT use JSON or any other structured format. Your output must be plain text.

<Events Summary>
----
{events_summary}
----
</Events Summary>

Example Output Format:
- Date: 1881, October 25 - Pablo Picasso is born in Málaga, Spain.
- Date: circa 1895 - He begins his advanced art studies at the School of Fine Arts in Barcelona.
- Date: 1900 - Picasso makes his first trip to Paris, the center of the European art world.

Begin.
"""

# Step 2: Converts the cleaned, ordered list of events into a structured JSON object.
step2_structure_events_prompt = """You are a data processing specialist. Your sole task is to convert a pre-cleaned, chronologically ordered list of life events into a structured JSON object.

<Task>
You will be given a list of events that is already de-duplicated and ordered. You must not change the order or content of the events. For each event in the list, you will extract its name, a detailed description, its date, and location, and format it as JSON.
</Task>

<Guidelines>
1.  For the `name` field, create a short, descriptive title for the event (e.g., "Birth of Pablo Picasso").
2.  For the `description` field, provide the clear and concise summary of what happened from the input text.
3.  For the `date` field, populate `year`, `month`, and `day` whenever possible.
4.  If the date is an estimate or a range (e.g., "circa 1912" or "Between 1920-1924"), you MUST capture that specific text in the `note` field of the date object, and provide your best estimate for the `year`.
</Guidelines>

<Chronological Events List>
----
{cleaned_events}
----
</Chronological Events List>

CRITICAL: You must only return the structured JSON output. Do not add any commentary, greetings, or explanations before or after the JSON.
"""

# --- Prompt 2: For consolidating new events with the existing summary ---
CONSOLIDATE_SUMMARY_PROMPT = """You are a biographical assistant. Your task is to convert blocks of text that contains events of a person into single events where the date, description of the event, location of the event are included for {historical_figure}.

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
