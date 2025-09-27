import re
from typing import List

import requests
import tiktoken

FIRECRAWL_API_URL = "http://localhost:3002/v0/scrape"


async def url_crawl(url: str) -> str:
    """Crawls a URL and returns its content. For this example, returns dummy text."""
    # print(f"--- FAKE CRAWLING: {url} ---")
    # if "wikipedia" in url:
    #     return "Henry Miller was an American novelist, short story writer and essayist. He was born in Yorkville, NYC on December 26, 1891. He moved to Paris in 1930. He wrote tropic of cancer, part of his series of novels about his life."

    content = await scrape_page_content(url)
    if content is None:
        return ""
    return remove_markdown_links(content)


async def scrape_page_content(url):
    """Scrapes URL using Firecrawl API and returns Markdown content."""
    try:
        response = requests.post(
            FIRECRAWL_API_URL,
            json={
                "url": url,
                "pageOptions": {"onlyMainContent": True},
                "formats": ["markdown"],
            },
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("data", {}).get("markdown")
    except Exception as e:
        print(f"Error scraping page content: {e}")
        return None


def remove_markdown_links(markdown_text):
    """Removes Markdown links, keeping only display text."""
    return re.sub(r"\[(.*?)\]\(.*?\)", r"\1", markdown_text)


def chunk_text_by_tokens(
    text: str, chunk_size: int = 2000, overlap_size: int = 20
) -> List[str]:
    """Splits text into token-based, overlapping chunks."""
    if not text:
        return []

    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    print("--- TOKENS ---")
    print(len(tokens))
    print("--- TOKENS ---")
    chunks = []
    start_index = 0
    while start_index < len(tokens):
        end_index = start_index + chunk_size
        chunk_tokens = tokens[start_index:end_index]
        chunks.append(encoding.decode(chunk_tokens))
        start_index += chunk_size - overlap_size

    print(f"""<delete>
    CHUNKED TEXT ---
    Chunks:{len(chunks)}
    Tokens: {len(tokens)}
    Text: {len(text)}
    ---
    """)
    return chunks


tokenizer = tiktoken.get_encoding("cl100k_base")


def count_tokens(messages: List[str]) -> int:
    """Counts the total tokens in a list of messages."""
    return sum(len(tokenizer.encode(msg)) for msg in messages)
