# Plan for AI Agent: Author Biography Event Extraction Graph

## Supervisor Graph

The supervisor graph coordinates the research process, managing state and deciding which tools to call based on the current events. It merges new data from tools into existing events, handles incremental inputs, and controls when to stop. After each tool call, invoke `think_tool` to reflect and plan next steps.

### State Definition

- `person_to_research`: String (e.g., "Henry Miller")
- `events`: List of structured events (schema: id, name, description, source, date {year/month/day nullable}, location)
- `initial_events` (optional): Pre-provided events for incremental runs
- `messages`: List of dicts tracking history (lightweight for MVP: e.g., [{tool: "url_crawler", input: "Wikipedia", summary: "Added 3 events", think: "Gaps in career—next: Britannica"}]; cap at 5 entries, summarize if longer)

### Key Processes

- **Merging New Events**:
  - Match similar events semantically (e.g., via prompt for paraphrases).
  - Merge details, prioritizing detailed/primary sources (e.g., Wikipedia); flag conflicts.
  - Add unmatched new events automatically.
- **Tool Flow with Reflection**:
  - Always start with `url_finder`.
  - If <5 events: Run `url_crawler` to add more.
  - If ≥5 events: Run `further_event_research` to deepen details.
  - After _each_ tool: Call `think_tool` (prompt: "Review output + recent messages: New info? Gaps? Recommend next tool or stop?") → Append to `messages` → Use output to decide next.
  - For incremental: Prompt to check gaps in `initial_events` + messages; skip if complete.
- **Termination**: Max 5 tool calls; stop if `think_tool` recommends it, no changes in last 2 calls, or >80% events have full details (prompt-evaluated).
- **Example Merge**:
  - Supervisor event: {id: "1", name: "Birth", desc: "Born in NYC 1891", loc: "NYC"}
  - Tool event: {id: "4", name: "Birth", desc: "Born in Yorkville to immigrants", loc: "Yorkville"}
  - Merged: {id: "1", name: "Birth", desc: "Born in NYC/Yorkville 1891 to immigrants", loc: "Yorkville", source: "Wikipedia"}

### Example Flow

- Input: "Henry Miller" → `url_finder` → `think_tool` ("Good URLs found—crawl top one") → `url_crawler` (Wikipedia) → Merge → `think_tool` ("3 events added; <5 total—crawl next") → `url_crawler` (Britannica) → Merge → `think_tool` ("Now ≥5; deepen details") → `further_event_research` → `think_tool` ("Complete") → Done.
- Messages after flow: [{tool: "url_finder", input: "Henry Miller bio", summary: "3 URLs"}, {tool: "url_crawler", ..., think: "Gaps in career—next: Britannica"}, ...]

## Think Tool (New: Post-Tool Reflection)

Prompt-based tool to analyze tool outputs and history for better planning.

### Process

- Input: Recent tool output + last 2-3 messages.
- Prompt: "Summarize new info from [output]. Check events/messages for gaps (e.g., missing dates). Recommend: next tool (or none), reason. Output: {recommendation: 'url_crawler', reason: '...'}"
- Output: Dict appended to `messages` for supervisor to use.

### Example

- Input: url_crawler output (3 events) + messages (prior URLs).
- Think Output: {recommendation: "further_event_research", reason: "Birth/death covered; career events lack locations—targeted search next"}

## 1. URL Crawler Subgraph

Crawls a provided URL to extract and structure biographical events.

### Process Flow

1. Crawl URL and chunk content.
2. Categorize chunks (e.g., life events) and merge into `events_summary` string.
3. Clean/order via prompt and output as structured events (matching schema).

### Example

- Input URL: Wikipedia/Henry_Miller
- `events_summary`: "Dec 26, 1891 - Born in Yorkville; 1917 - Moved to Paris..."
- Output: List like [{name: "Birth", desc: "Born in Yorkville Dec 26 1891", date: {year:1891, month:12, day:26}, loc: "Yorkville", source: "Wikipedia"}]

## 2. Further Event Research Subgraph

Analyzes and enriches existing events with targeted research.

### Process Flow

1. Scan events for gaps (e.g., missing date/location) via prompt; select top 3-5.
2. For each: Search web (e.g., Tavily) for details, merge updates per supervisor rules.

### Example

- Input Event: {name: "Marriage", desc: "Married June 1 1924", date: {year:1924, month:6, day:1}, loc: null}
- Search Query: "Henry Miller marriage June 1924 details"
- Update: Add loc: "Croton-on-Hudson" from results, merged desc: "Married in Croton-on-Hudson..."

## 3. URL Finder Tool

Searches for top biography URLs.

### Process

- Query web search: `"[person] biography" site:wikipedia.org OR site:britannica.com OR site:biography.com` (top 5 results).
- Filter to 3 authoritative URLs, sorted by priority (e.g., Wikipedia first); dedupe.

### Example

- Input: "Henry Miller"
- Output: ["https://en.wikipedia.org/wiki/Henry_Miller", "https://www.britannica.com/biography/Henry-Miller", "https://www.biography.com/authors-writers/henry-miller"]
