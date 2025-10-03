# Graph Consolidation Proposal: Merging URL Crawler and Merge Events

## Current Analysis

### Existing Architecture
The current system has two separate graphs that perform similar chunking and categorization operations:

1. **URL Crawler Graph** (`url_krawler_graph.py`):
   - Scrapes URL content
   - Chunks content by tokens (2000 tokens, 20 overlap)
   - Categorizes chunks as Relevant/Partial/Irrelevant using tools
   - Extracts relevant content from Partial chunks
   - Creates event list from categorized content

2. **Merge Events Graph** (`merge_events_graph.py`):
   - Splits extracted events into chunks (2000 characters)
   - Categorizes chunks into 4 categories (early, personal, career, legacy)
   - Merges categorized chunks
   - Combines with existing events

### Identified Duplication

1. **Chunking Logic**: Both graphs implement chunking but with different approaches:
   - URL Crawler: Token-based chunking (2000 tokens, 20 overlap)
   - Merge Events: Character-based chunking (2000 characters)

2. **Categorization**: Both categorize content but for different purposes:
   - URL Crawler: Relevance filtering (Relevant/Partial/Irrelevant)
   - Merge Events: Thematic categorization (early/personal/career/legacy)

3. **Sequential Processing**: Both process chunks in loops with similar patterns

## Proposed Consolidated Architecture

### Single Graph Design: `consolidated_research_graph.py`

```
┌─────────────────┐
│   url_finder    │
└─────────┬───────┘
          │
┌─────────▼───────┐
│crawl_and_process│
└─────────┬───────┘
          │
┌─────────▼───────┐
│  process_url    │ ← Loop for each URL
└─────────┬───────┘
          │
┌─────────▼───────┐
│ scrape_content  │
└─────────┬───────┘
          │
┌─────────▼───────┐
│  chunk_content  │
└─────────┬───────┘
          │
┌─────────▼───────┐
│categorize_chunk │ ← Loop for each chunk
└─────────┬───────┘
          │
┌─────────▼───────┐
│merge_and_update │
└─────────┬───────┘
          │
┌─────────▼───────┐
│next_url_router  │
└─────────────────┘
```

### Key Changes

#### 1. Unified State Management
```python
class ConsolidatedResearchState(TypedDict):
    research_question: str
    existing_events: CategoriesWithEvents
    used_domains: list[str]
    urls: list[str]
    
    # URL processing state
    current_url: str
    raw_scraped_content: str
    text_chunks: List[str]
    categorized_chunks: List[ChunkWithCategory]
    
    # Processing control
    current_chunk_index: int
    current_url_index: int
```

#### 2. Combined Chunk Processing
Instead of two separate categorization steps, we'll combine them:

```python
async def categorize_chunk(state: ConsolidatedResearchState, config: RunnableConfig):
    """Single categorization step that does both relevance filtering and thematic categorization"""
    
    # Step 1: Relevance filtering (from URL crawler)
    relevance_prompt = EXTRACT_EVENTS_PROMPT.format(
        research_question=research_question, 
        text_chunk=chunk
    )
    relevance_result = await relevance_model.ainvoke(relevance_prompt)
    
    # Step 2: If relevant, categorize thematically (from merge events)
    if relevance_result.is_relevant:
        category_prompt = categorize_events_prompt.format(
            events=relevance_result.content
        )
        category_result = await category_model.ainvoke(category_prompt)
        
        return {
            "content": relevance_result.content,
            "category": category_result,  # early/personal/career/legacy
            "original_chunk": chunk
        }
    else:
        return {
            "content": "",
            "category": CategoriesWithEvents(early="", personal="", career="", legacy=""),
            "original_chunk": chunk
        }
```

#### 3. Unified Chunking Strategy
Use the more sophisticated token-based chunking from URL crawler:
- 2000 tokens per chunk
- 20 token overlap
- Better for handling varied content lengths

#### 4. Simplified Processing Flow
```python
async def process_single_url(state: ConsolidatedResearchState):
    """Process one URL completely before moving to the next"""
    
    # 1. Scrape content
    content = await url_crawl(current_url)
    
    # 2. Chunk content
    chunks = await chunk_text_by_tokens(content)
    
    # 3. Process all chunks
    categorized_chunks = []
    for chunk in chunks:
        result = await categorize_chunk(chunk, research_question, config)
        categorized_chunks.append(result)
    
    # 4. Merge categorized results
    new_events = merge_categorized_chunks(categorized_chunks)
    
    # 5. Combine with existing events
    final_events = await combine_events(existing_events, new_events, config)
    
    return final_events
```

## Implementation Plan

### Phase 1: Create Consolidated Graph
1. Create `consolidated_research_graph.py`
2. Implement unified state management
3. Combine chunking logic (use token-based from URL crawler)
4. Merge categorization steps

### Phase 2: Update Main Graph
1. Modify `research_events_graph.py` to use new consolidated graph
2. Remove calls to separate URL crawler and merge events graphs
3. Update routing logic

### Phase 3: Cleanup
1. Remove `url_krawler_graph.py` (or deprecate)
2. Remove `merge_events_graph.py` (or deprecate)
3. Update imports and dependencies
4. Update tests

## Benefits

### 1. Reduced Complexity
- Single graph instead of three
- Unified state management
- Clearer data flow

### 2. Improved Performance
- No intermediate serialization between graphs
- Single pass categorization
- Reduced LLM calls (combine relevance + thematic categorization)

### 3. Better Maintainability
- Single place to modify chunking logic
- Unified error handling
- Consistent configuration

### 4. Enhanced Flexibility
- Easy to add new categorization dimensions
- Configurable processing strategies
- Better debugging visibility

## Potential Challenges

### 1. Prompt Complexity
Combined categorization prompt may become complex. Solution: Use two-step LLM calls within single node.

### 2. State Management
Larger state object. Solution: Use clear field naming and validation.

### 3. Error Handling
Need robust error handling for combined operations. Solution: Use existing `@with_error_handling` decorator.

## Migration Strategy

1. **Backward Compatibility**: Keep old graphs during transition
2. **Feature Flag**: Add config option to use consolidated vs separate graphs
3. **Gradual Rollout**: Test with sample URLs first
4. **Performance Monitoring**: Compare LLM usage and processing time

## Code Structure

### New Files to Create:
- `src/research_events/consolidated_research_graph.py`
- `src/research_events/consolidated_prompts.py` (optional)

### Files to Modify:
- `src/research_events/research_events_graph.py`
- Update tests in `test/` directory

### Files to Deprecate:
- `src/url_crawler/url_krawler_graph.py`
- `src/research_events/merge_events/merge_events_graph.py`

This consolidation will significantly simplify the architecture while maintaining all existing functionality and improving performance.