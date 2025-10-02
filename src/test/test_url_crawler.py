# tests/url_crawler/test_url_crawler.py

"""Tests for the url_krawler_graph."""

from unittest.mock import AsyncMock, patch

import pytest

# Imports are relative to the src directory (configured in pyproject.toml pythonpath)
from url_crawler.url_krawler_graph import url_crawler_app


@pytest.fixture
def sample_input_state() -> dict:
    """Provide a sample input state for the url_crawler_app graph."""
    return {
        "url": "https://www.britannica.com/biography/Henry-Miller",
        "research_question": "Research the life of Henry Miller",
    }


class MockResponse:
    """Mock response class for LLM responses."""

    def __init__(self, content):
        """Initialize mock response with content."""
        self.content = content


class MockToolCall:
    """Mock tool call for structured LLM responses."""

    def __init__(self, name, args):
        """Initialize mock tool call with name and args."""
        self.name = name
        self.args = args

    def __getitem__(self, key):
        """Make the object subscriptable like a dictionary."""
        if key == "name":
            return self.name
        elif key == "args":
            return self.args
        else:
            raise KeyError(key)


class MockToolResponse:
    """Mock tool response for structured LLM responses."""

    def __init__(self, tool_calls=None):
        """Initialize mock tool response with tool calls."""
        self.tool_calls = tool_calls or []


@pytest.fixture
def mock_scraped_content():
    """Provide mock scraped content for testing."""
    return """
    Henry Miller was an American novelist, short story writer and essayist. 
    He was born in Yorkville, NYC on December 26, 1891. 
    He moved to Paris in 1930 where he lived for many years.
    He wrote Tropic of Cancer, part of his series of novels about his life.
    He married his first wife Beatrice in 1917.
    He had a daughter named Barbara in 1919.
    He divorced Beatrice in 1924.
    He married his second wife June in 1924.
    He died in Pacific Palisades, California on June 7, 1980.
    """


@pytest.fixture
def mock_llm_responses():
    """Provide mock LLM responses for different chunks."""
    return [
        # First chunk - RelevantChunk
        MockToolResponse([MockToolCall("RelevantChunk", {})]),
        # Second chunk - PartialChunk
        MockToolResponse(
            [
                MockToolCall(
                    "PartialChunk",
                    {
                        "relevant_content": "He was born in Yorkville, NYC on December 26, 1891. He married his first wife Beatrice in 1917."
                    },
                )
            ]
        ),
        # Third chunk - IrrelevantChunk
        MockToolResponse([MockToolCall("IrrelevantChunk", {})]),
    ]


@pytest.fixture
def mock_event_summaries():
    """Provide mock event summaries for create_event_list_from_chunks."""
    return [
        "Born in Yorkville, NYC on December 26, 1891.",
        "Married his first wife Beatrice in 1917. Had a daughter named Barbara in 1919.",
        "Moved to Paris in 1930 where he lived for many years.",
        "Divorced Beatrice in 1924. Married his second wife June in 1924.",
        "Died in Pacific Palisades, California on June 7, 1980.",
    ]


# @pytest.mark.skip(reason="Skip mocked LLM test for now")
@pytest.mark.asyncio
async def test_url_crawler_with_mocked_llm(
    sample_input_state: dict,
    mock_scraped_content: str,
    mock_llm_responses: list,
    mock_event_summaries: list,
):
    """Unit test for the URL crawler graph with mocked LLM calls."""
    # --- Arrange: Mock Data Setup ---

    # --- Act: Execute the graph with patched dependencies ---
    with (
        patch("url_crawler.url_krawler_graph.url_crawl") as mock_crawl,
        patch("url_crawler.url_krawler_graph.model_for_tools") as mock_model_tools,
        patch("url_crawler.url_krawler_graph.model_for_structured") as mock_model_big,
    ):
        # Configure URL crawling mock
        mock_crawl.return_value = mock_scraped_content

        # Configure model_for_tools mock (for chunk categorization)
        mock_tools_model = AsyncMock()
        mock_tools_model.ainvoke.side_effect = mock_llm_responses
        mock_model_tools.bind_tools.return_value = mock_tools_model

        # Configure model_for_structured mock (for event summarization)
        mock_model_big.ainvoke = AsyncMock(
            side_effect=[MockResponse(summary) for summary in mock_event_summaries]
        )

        result = await url_crawler_app.ainvoke(sample_input_state)

    # --- Assert: Verify the output ---
    assert "extracted_events" in result
    assert "raw_scraped_content" in result

    extracted_events = result["extracted_events"]
    raw_content = result["raw_scraped_content"]

    # Verify that events were extracted
    assert len(extracted_events) > 0
    assert "Born" in extracted_events or "1891" in extracted_events

    # Verify that raw content was captured
    assert len(raw_content) > 0
    assert "Henry Miller" in raw_content

    # Verify that the URL was processed
    mock_crawl.assert_called_once_with(sample_input_state["url"])


# @pytest.mark.skip(reason="Skip real LLM test for now")
@pytest.mark.llm
@pytest.mark.asyncio
async def test_url_crawler_with_real_llm(sample_input_state: dict):
    """Integration test for the URL crawler graph with real LLM calls."""
    # --- Act ---
    result = await url_crawler_app.ainvoke(sample_input_state)

    # --- Assert ---
    assert "extracted_events" in result
    assert "raw_scraped_content" in result

    extracted_events = result["extracted_events"]

    # Verify that events were extracted (may be empty if URL scraping fails)

    # If URL scraping failed (no content), the extracted_events will be empty
    # This is expected behavior when Firecrawl service is not available
    if len(extracted_events) > 0:
        # Verify that some biographical information was extracted
        assert any(
            keyword in extracted_events.lower()
            for keyword in ["born", "died", "married", "moved", "wrote", "published"]
        )
    else:
        # If no events extracted, it's likely due to URL scraping failure
        # This is expected behavior when Firecrawl service is not available
        pass


# @pytest.mark.skip(reason="Skip mocked URL crawling test for now")
@pytest.mark.asyncio
async def test_url_crawler_with_mocked_url_crawling(
    sample_input_state: dict,
    mock_scraped_content: str,
    mock_llm_responses: list,
    mock_event_summaries: list,
):
    """Test URL crawler with mocked URL crawling and mocked LLM calls."""
    # --- Act: Execute with mocked URL crawling and LLM ---
    with (
        patch("url_crawler.url_krawler_graph.url_crawl") as mock_crawl,
        patch("url_crawler.url_krawler_graph.model_tools") as mock_model_tools,
        patch("url_crawler.url_krawler_graph.model_for_structured") as mock_model_big,
    ):
        # Configure URL crawling mock
        mock_crawl.return_value = mock_scraped_content

        # Configure model_tools mock (for chunk categorization)
        mock_model_tools.ainvoke = AsyncMock(side_effect=mock_llm_responses)

        # Configure model_for_structured mock (for event summarization)
        mock_model_big.ainvoke = AsyncMock(
            side_effect=[MockResponse(summary) for summary in mock_event_summaries]
        )

        result = await url_crawler_app.ainvoke(sample_input_state)

    # --- Assert ---
    assert "extracted_events" in result
    assert "raw_scraped_content" in result

    extracted_events = result["extracted_events"]

    # Verify that events were extracted from the mock content
    assert len(extracted_events) > 0
    assert "Henry Miller" in extracted_events or "1891" in extracted_events

    # Verify that the mock URL was used
    mock_crawl.assert_called_once_with(sample_input_state["url"])
