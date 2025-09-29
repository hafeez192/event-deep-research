from urllib.parse import urlparse

urls = [
    "https://en.wikipedia.org/wiki/Henry_Miller",
    "https://www.britannica.com/biography/Henry-Miller",
]
used_domains = ["en.wikipedia.org", "www.britannica.com"]

# Extract domain from URL and check if it's in used_domains
domain = urlparse(urls[0]).netloc
print(domain in used_domains)
