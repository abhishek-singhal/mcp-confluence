import os
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from fastmcp import FastMCP

TOKEN = os.getenv("CONFLUENCE_PERSONAL_TOKEN")
BASE_URL = os.getenv("CONFLUENCE_URL")

mcp = FastMCP("mcp-confluence", version="1.0.0")

@mcp.tool(
    "get_confluence_page_content",
    description="Fetch a Confluence page by URL and return title and cleaned text content."
)
def get_confluence_page_content(page_url: str) -> dict[str, str]:
    """Fetch a Confluence page by URL and return title and cleaned text content."""
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": "Mozilla/5.0",
    }

    auth_headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    response = requests.get(
        page_url,
        headers={**headers, **auth_headers},
        timeout=30,
        allow_redirects=True,
    )
    response.raise_for_status()

    content_type = (response.headers.get("Content-Type") or "").lower()
    if "html" not in content_type:
        raise RuntimeError(f"Expected HTML response, got: {content_type}")

    soup = BeautifulSoup(response.text, "html.parser")

    title_node = soup.select_one("#title-text") or soup.select_one("h1") or soup.title
    title = title_node.get_text(" ", strip=True) if title_node else ""

    content_node = (
        soup.select_one("#main-content")
        or soup.select_one(".wiki-content")
        or soup.select_one("#content")
    )
    content = content_node.get_text("\n", strip=True) if content_node else ""

    return {
        "url": response.url,
        "title": title,
        "content": content,
    }


@mcp.tool(
    "search_confluence",
    description="Search Confluence pages by query, space key and optional max results.",
)
def search_confluence_html(
    query: str, space_key: str, max_results: int = 20
) -> list[dict[str, str]]:
    """Parse Confluence search HTML and return only result titles and URLs."""
    search_url = f"{BASE_URL}/dosearchsite.action"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": "Mozilla/5.0",
    }
    cql_parts = ["type=page", f'text~"{query}"']
    if space_key:
        cql_parts.append(f'space="{space_key}"')

    params = {
        "queryString": query,
        "cql": " AND ".join(cql_parts),
    }

    # If your environment supports PAT in Bearer auth, keep this; otherwise use session cookies.
    auth_headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    response = requests.get(
        search_url,
        params=params,
        headers={**headers, **auth_headers},
        timeout=30,
        allow_redirects=True,
    )
    response.raise_for_status()

    content_type = (response.headers.get("Content-Type") or "").lower()
    if "html" not in content_type:
        raise RuntimeError(f"Expected HTML response, got: {content_type}")

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict[str, str]] = []
    seen = set()

    # Confluence search cards usually contain links under h3/h4 headings.
    for a_tag in soup.select(
        "h3 a[href], h4 a[href], .search-result a[href], a.search-result-link"
    ):
        title = a_tag.get_text(" ", strip=True)
        href = a_tag.get("href")
        if not title or not href:
            continue

        url = urljoin(BASE_URL, href)
        # Keep only likely content pages and avoid nav/profile links.
        if (
            "/pages/" not in url
            and "viewpage.action" not in url
            and "/display/" not in url
        ):
            continue

        key = (title, url)
        if key in seen:
            continue
        seen.add(key)
        results.append({"title": title, "url": url})

        if len(results) >= max_results:
            break

    return results


def main():
    mcp.run()


if __name__ == "__main__":
    main()
