# Revised Graph Consolidation Proposal

## Updated Architecture

Keep the URL crawler separate for modularity, but merge the chunking and categorization logic into the merge events graph.

### New Architecture:

```
research_events_graph.py
├── url_finder (unchanged)
├── should_process_url_router (unchanged)
├── crawl_url → calls url_crawler_app (just for scraping)
└── merge_events_and_update → calls enhanced_merge_events_app
```

```
enhanced_merge_events_graph.py (NEW)
├── split_events (from URL crawler - token-based)
├── extract_and_categorize_chunk (COMBINED PROMPT)
├── merge_categorizations (unchanged)
└── combine_new_and_original_events (unchanged)
```

## Combined Prompt Analysis

### Current Two-Step Process:

1. **URL Crawler**: Extract relevant content using tools (Relevant/Partial/Irrelevant)
2. **Merge Events**: Categorize extracted content into 4 themes

### Proposed Combined Prompt:

```python
EXTRACT_AND_CATEGORIZE_PROMPT = """
You are a Biographical Event Extractor and Categorizer. Your task is to analyze text chunks for events related to: **"{research_question}"**

<Available Tools>
- `IrrelevantChunk` (use if the text contains NO biographical events relevant to the research question)
- `RelevantEventsCategorized` (use if the text contains relevant events - categorize them into the 4 categories)
</Available Tools>

<Categories>
early: Covers childhood, upbringing, family, education, and early influences that shaped the author.
personal: Focuses on relationships, friendships, family life, places of residence, and notable personal traits or beliefs.
career: Details their professional journey: first steps into writing, major publications, collaborations, recurring themes, style, and significant milestones.
legacy: Explains how their work was received, awards or recognition, cultural/literary impact, influence on other authors, and how they are remembered today.
</Categories>

**EXTRACTION RULES**:
- Extract COMPLETE sentences with all details (dates, names, locations, context)
- Do NOT summarize or abbreviate any information
- Include only events directly relevant to the research question
- Maintain chronological order within each category
- Format as clean bullet points (e.g., "- Event description with date and location.")

<Text to Analyze>
{text_chunk}
</Text to Analyze>

You must call exactly one of the provided tools. Do not respond with plain text.
"""

# Pydantic models for the combined approach
class RelevantEventsCategorized(BaseModel):
    """The chunk contains relevant biographical events that have been categorized."""
    early: str = Field(description="Bullet points of events related to childhood, upbringing, family, education, and early influences")
    personal: str = Field(description="Bullet points of events related to relationships, friendships, family life, residence, and personal traits")
    career: str = Field(description="Bullet points of events related to professional journey, publications, collaborations, and milestones")
    legacy: str = Field(description="Bullet points of events related to recognition, impact, influence, and how they are remembered")

class IrrelevantChunk(BaseModel):
    """The chunk contains NO biographical events relevant to the research question."""
```

## Benefits of Combined Prompt:

### 1. **Reduced LLM Calls**

- Before: 2 calls per chunk (relevance + categorization)
- After: 1 call per chunk (combined)
- **50% reduction in API costs and latency**

### 2. **Better Context Preservation**

- Single analysis pass maintains full context
- No information loss between relevance filtering and categorization
- More accurate categorization with full chunk context

### 3. **Simplified Logic**

- Single decision tree instead of two-step process
- Cleaner error handling
- Easier to debug and maintain

### 4. **Improved Accuracy**

- Can make nuanced decisions about partial relevance
- Better handling of mixed-content chunks
- More consistent categorization criteria

## Implementation Details:

### Enhanced Merge Events Graph:

```python
class MergeEventsState(TypedDict):
    existing_events: CategoriesWithEvents
    extracted_events: str  # raw text from URL crawler
    text_chunks: List[str]  # token-based chunks
    categorized_chunks: List[CategoriesWithEvents]  # results per chunk

async def split_events(state: MergeEventsState):
    """Use token-based chunking from URL crawler"""
    extracted_events = state.get("extracted_events", "")
    chunks = await chunk_text_by_tokens(extracted_events)  # from url_crawler.utils
    return Command(
        goto="extract_and_categorize_chunk",
        update={"text_chunks": chunks, "categorized_chunks": []}
    )

async def extract_and_categorize_chunk(state: MergeEventsState, config: RunnableConfig):
    """Combined extraction and categorization"""
    chunks = state.get("text_chunks", [])
    done = state.get("categorized_chunks", [])

    if len(done) >= len(chunks):
        return Command(goto="merge_categorizations")

    chunk = chunks[len(done)]
    research_question = state.get("research_question", "")

    prompt = EXTRACT_AND_CATEGORIZE_PROMPT.format(
        research_question=research_question,
        text_chunk=chunk
    )

    tools = [tool(RelevantEventsCategorized), tool(IrrelevantChunk)]
    model = create_tools_model(tools=tools, config=config)
    response = await model.ainvoke(prompt)

    # Parse response
    if response.tool_calls[0]["name"] == "RelevantEventsCategorized":
        categorized = CategoriesWithEvents(**response.tool_calls[0]["args"])
    else:
        categorized = CategoriesWithEvents(early="", personal="", career="", legacy="")

    return Command(
        goto="extract_and_categorize_chunk",
        update={"categorized_chunks": done + [categorized]}
    )
```

### Updated URL Crawler:

Simplify to just scrape and return raw content:

```python
class UrlCrawlerState(TypedDict):
    url: str
    research_question: str
    extracted_events: str  # Just raw scraped content

async def scrape_and_return_content(state: UrlCrawlerState):
    """Just scrape content, no processing"""
    url = state.get("url", "")
    content = await url_crawl(url)
    return Command(goto=END, update={"extracted_events": content})
```

## Migration Strategy:

### Phase 1: Create Enhanced Merge Graph

1. Create `merge_events_graph.py`
2. Implement combined prompt and logic
3. Test with existing data

### Phase 2: Update URL Crawler

1. Simplify URL crawler to just scrape content
2. Remove chunking and categorization logic
3. Update tests

### Phase 3: Integration

1. Update `research_events_graph.py` to use new components
2. Update configuration and imports
3. Performance testing

## Expected Improvements:

- **50% fewer LLM calls** per URL processed
- **Faster processing** due to reduced API latency
- **Better accuracy** with combined context analysis
- **Cleaner architecture** with separated concerns (scraping vs processing)

This approach keeps the modular structure while eliminating the redundant chunking and categorization logic.
