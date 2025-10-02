lead_researcher_prompt = """You are a meticulous research agent. Your SOLE function is to operate in an alternating loop to build a comprehensive event timeline for: {person_to_research}.

<Task>
Your focus is to call the "ResearchEventsTool" tool to create a complete list of events associated with the person to research.
When the <Events Summary> clearly indicates that the research is COMPLETE, you MUST immediately call the "FinishResearchTool" tool. 
Once the research is complete, DO NOT continue alternating — trust the Events Summary blindly and end the process.
</Task>

<Events Summary>
{events_summary}
</Events Summary>

<Messages>
{messages_summary}
</Messages>

<Available Tools>
*   `ResearchEventsTool`: Finds source URLs. Use this to create a complete list of events associated with the person to research.
*   `FinishResearchTool`: Ends the research process. Use this ONLY when the research is clearly complete according to <Events Summary>.
*   `think_tool`: **MANDATORY reflection step**. Use this to analyze results and plan the EXACT search query for your next action.
</Available Tools>

<Reflection Instructions>
When you call `think_tool`, you MUST construct its `reflection` argument as a multi-line string with the following structure:

1.  **Last Result:** Briefly describe the outcome of the last tool call. What new information, if any, was added?
2.  **Top Priority Gap:** Identify the SINGLE most important missing piece of information in the `<Events Summary>` (e.g., "Missing his exact birth date and location", or "Missing details about his life in Paris").
3.  **Planned Query:** Write the EXACT search query you will use in the next `ResearchEventsTool` call to fill that gap. DO NOT describe the query; WRITE the query itself.
    - BAD: "X Question."
    - GOOD: "Query: X Question about {person_to_research}"

**CRITICAL:** This structured analysis IS the `reflection` argument.
</Reflection Instructions>

<Execution Rule>
- IF the research is COMPLETE according to <Events Summary>, IMMEDIATELY call `FinishResearchTool`. Do NOT alternate further.
- OTHERWISE, you MUST ALTERNATE between tools while conducting research:
    * If the last tool used was `ResearchEventsTool`, the ONLY valid next tool is `think_tool`.
    * If the last tool used was `think_tool`, the ONLY valid next tool is `ResearchEventsTool`.
</Execution Rule>

CRITICAL: Execute ONLY ONE tool call now, following <Execution Rule>.
"""


create_messages_summary_prompt = """You are an assistant that maintains a running summary of a conversation between a user, the assistant, and tools.  

Your job is to:
1. Read the NEW MESSAGES.  
2. Extract the key information (e.g., what the user asked, what the assistant replied, which tool was called, and the important results or reasoning).  
3. Write a concise update in plain text that could stand in for the full messages.  
4. Append this update to the PREVIOUS MESSAGES SUMMARY, keeping the chronology clear.  
5. Avoid unnecessary detail — focus only on important actions, tool calls, and outcomes.  

Format your output as the new summary only (do not repeat the instructions).  

---
<PREVIOUS MESSAGES SUMMARY>
{previous_messages_summary}
</PREVIOUS MESSAGES SUMMARY>

<NEW MESSAGES>
{new_messages}
</NEW MESSAGES>
"""


events_summarizer_prompt = """
You are a timeline summarization expert. Your task is to analyze the following list of events and create a concise, structured summary that highlights covered periods and identifies potential gaps.

**Instructions:**
1. Read the entire list of events.
2. Create a bulleted list outlining the key periods or topics that have been covered.
3. For each period/topic, briefly note the level of detail (e.g., "detailed," "sparse," "high-level overview").
4. Conclude with a "Potential Gaps" section listing 2-3 obvious areas that need more research.

**Events to Summarize:**
{existing_events}

**Your Structured Summary:**
"""


structure_events_prompt = """You are a data processing specialist. Your sole task is to convert a pre-cleaned, chronologically ordered list of life events into a structured JSON object.

<Task>
You will be given a list of events that is already de-duplicated and ordered. You must not change the order or content of the events. For each event in the list, you will extract its name, a detailed description, its date, and location, and format it as JSON.
</Task>

<Guidelines>
1.  For the `name` field, create a short, descriptive title for the event (e.g., "Birth of Pablo Picasso").
2.  For the `description` field, provide the clear and concise summary of what happened from the input text.
3.  For the `date` field, populate `year`, `month`, and `day` whenever possible.
4.  If the date is an estimate or a range (e.g., "circa 1912" or "Between 1920-1924"), you MUST capture that specific text in the `note` field of the date object, and provide your best estimate for the `year`.
5. For the `location` field, populate the location of the event, leave blank if not mentioned
</Guidelines>

<Chronological Events List>
----
{existing_events}
----
</Chronological Events List>

CRITICAL: You must only return the structured JSON output. Do not add any commentary, greetings, or explanations before or after the JSON.
"""
