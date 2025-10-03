# Graph Structure Refactoring Suggestions

## Overview

The current codebase implements a multi-layered graph architecture for event research with the following main components:

- **Main Supervisor Graph** (`src/graph.py`) - Orchestrates the overall research process
- **Research Events Graph** (`src/research_events/research_events_graph.py`) - Handles URL finding and event extraction
- **Merge Events Graph** (`src/research_events/merge_events/merge_events_graph.py`) - Merges and categorizes events
- **URL Crawler Graph** (`src/url_crawler/url_krawler_graph.py`) - Scrapes and processes web content

## Key Issues Identified

### 1. **Code Duplication and Inconsistency**

- **Tool Definitions**: Scattered tool definitions with similar patterns

### 3. **Configuration and Dependencies**

- **Mixed Configuration**: Some components use `Configuration` class, others use hardcoded values
- **Import Dependencies**: Circular import risks between graph modules
- **Environment Variables**: Inconsistent environment variable handling

## Detailed Refactoring Recommendations

### 3. **Improve State Design**

#### 3.1 Consolidate State Schemas

```python
# src/core/unified_state.py
class ResearchState(BaseState):
    # Input fields
    person_to_research: str
    research_question: str

    # Processing state
    urls: List[str] = []
    used_domains: List[str] = []
    raw_content: str = ""
    extracted_events: str = ""
    categorized_events: CategoriesWithEvents = CategoriesWithEvents()

    # Output fields
    final_events: List[ChronologyEvent] = []
    structured_events: List[ChronologyEvent] = []
```

#### 3.2 Type Safety Improvements

```python
# Use proper Pydantic models instead of TypedDict where possible
class ProcessingResult(BaseModel):
    success: bool
    data: Any
    error: Optional[str] = None
```

### 4. **Extract Business Logic**

#### 4.1 Service Layer

```python
# src/services/url_service.py
class URLService:
    def find_relevant_urls(self, query: str, used_domains: List[str]) -> List[str]:
        # URL finding logic

    def extract_domain(self, url: str) -> str:
        # Domain extraction logic

# src/services/event_service.py
class EventService:
    def extract_events_from_content(self, content: str, question: str) -> str:
        # Event extraction logic

    def merge_events(self, existing: CategoriesWithEvents, new: str) -> CategoriesWithEvents:
        # Event merging logic
```

#### 4.2 Validation Layer

```python
# src/core/validation.py
class StateValidator:
    @staticmethod
    def validate_research_state(state: ResearchState) -> List[str]:
        # Validate state completeness

    @staticmethod
    def sanitize_input(input_data: dict) -> dict:
        # Input sanitization
```

### 5. **Improve Error Handling and Observability**

#### 5.1 Centralized Error Handling

```python
# src/core/error_handling.py
class GraphError(Exception):
    def __init__(self, message: str, node: str, state: dict):
        self.message = message
        self.node = node
        self.state = state

def with_error_handling(func):
    @wraps(func)
    async def wrapper(state, config):
        try:
            return await func(state, config)
        except Exception as e:
            error_info = {
                "error": str(e),
                "node": func.__name__,
                "state_snapshot": state
            }
            return Command(goto="error_handler", update=error_info)
    return wrapper
```

### 6. **Configuration Improvements**

#### 6.1 Environment-Specific Configs

```python
# src/configuration.py
class Configuration(BaseModel):
    # Move hardcoded values here
    default_chunk_size: int = 800
    default_overlap_size: int = 20
    max_content_length: int = 100000
    max_tool_iterations: int = 7

    @classmethod
    def from_env(cls) -> "Configuration":
        # Load from environment with defaults
```

#### 6.2 Model Configuration Registry

```python
# src/models/model_registry.py
class ModelRegistry:
    models = {
        "tools": "ollama:gpt-oss:20b",
        "structured": "ollama:mistral-nemo:latest",
        "fast": "ollama:qwen3:14b"
    }

    @classmethod
    def get_model(cls, purpose: str) -> str:
        return cls.models.get(purpose, cls.models["structured"])
```

### 7. **Testing Infrastructure**

#### 7.1 Graph Testing Framework

```python
# tests/graph_test_utils.py
class GraphTestHelper:
    @staticmethod
    def create_test_state(**overrides) -> dict:
        # Create test state with defaults

    @staticmethod
    async def run_graph_node(graph, node_name: str, state: dict):
        # Test individual nodes

    @staticmethod
    def assert_state_transition(initial: dict, final: dict, expected_changes: dict):
        # Validate state changes
```
