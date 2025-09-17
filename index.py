import requests
import re

FIRECRAWL_API_URL = "http://localhost:3002/v0/scrape"
# TARGET_URL = "https://en.wikipedia.org/wiki/Henry_Miller"
TARGET_URL = "https://www.britannica.com/biography/Henry-Miller"


def scrape_page_content(url):
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
    except requests.exceptions.RequestException:
        return None


def remove_markdown_links(markdown_text):
    """Removes Markdown links, keeping only display text."""
    return re.sub(r"\[(.*?)\]\(.*?\)", r"\1", markdown_text)


if __name__ == "__main__":
    if content := scrape_page_content(TARGET_URL):
        print("--- CLEANED CONTENT ---")
        print(remove_markdown_links(content))
