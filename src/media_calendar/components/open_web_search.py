"""Light-touch open-web search helpers for review-first discovery sweeps."""

from __future__ import annotations

from datetime import date
from typing import Callable, Dict, List, Optional, Sequence
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from media_calendar.components.source_fetcher import DEFAULT_USER_AGENT

SearchApi = Callable[[str], str]

_DEFAULT_QUERY_TEMPLATES = [
    {
        "template": "documentary fund applications {year}",
        "category": "funding_round",
        "source_type": "fund",
    },
    {
        "template": "documentary lab applications {year}",
        "category": "lab_application",
        "source_type": "lab",
    },
    {
        "template": "film festival submissions {year}",
        "category": "festival_submission",
        "source_type": "festival",
    },
    {
        "template": "screen industry fellowship applications {year}",
        "category": "fellowship",
        "source_type": "fellowship",
    },
    {
        "template": "co-production market submissions {year}",
        "category": "industry_forum",
        "source_type": "market",
    },
]
_BLOCKED_HOST_TOKENS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "youtu.be",
}


def build_open_web_queries(current_date: date) -> List[Dict[str, str]]:
    """Build a small, cost-capped set of search queries for current/next year."""

    years = [current_date.year, current_date.year + 1]
    queries: List[Dict[str, str]] = []

    for year in years:
        for template in _DEFAULT_QUERY_TEMPLATES:
            queries.append(
                {
                    "query": template["template"].format(year=year),
                    "category": template["category"],
                    "source_type": template["source_type"],
                }
            )

    return queries


def search_open_web(
    query_specs: Sequence[Dict[str, str]],
    *,
    max_results_per_query: int = 3,
    max_results_total: int = 12,
    search_api: SearchApi | None = None,
) -> List[Dict[str, object]]:
    """Search the web with a narrow query set and return deduplicated results."""

    active_search_api = search_api or _default_search_api
    deduped: Dict[str, Dict[str, object]] = {}

    for query_spec in query_specs:
        query = query_spec["query"]
        body = active_search_api(query)

        for index, result in enumerate(_parse_bing_rss_results(body), start=1):
            url = str(result["url"])
            if _is_blocked_result(url):
                continue

            normalized_url = _normalize_url(url)
            existing = deduped.get(normalized_url)
            enriched = {
                **result,
                "query": query,
                "query_category": query_spec["category"],
                "query_source_type": query_spec["source_type"],
                "rank": index,
            }
            if existing is None:
                deduped[normalized_url] = enriched
                if len(deduped) >= max_results_total:
                    return list(deduped.values())
            elif index < int(existing["rank"]):
                deduped[normalized_url] = enriched

            if index >= max_results_per_query:
                break

    return list(deduped.values())


def _default_search_api(query: str) -> str:
    encoded_query = quote_plus(query)
    url = f"https://www.bing.com/search?format=rss&q={encoded_query}"
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _parse_bing_rss_results(payload: str) -> List[Dict[str, str]]:
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return []

    results: List[Dict[str, str]] = []
    for item in root.findall("./channel/item"):
        title = _item_text(item, "title")
        link = _item_text(item, "link")
        description = _item_text(item, "description")
        if not link:
            continue
        results.append(
            {
                "title": title or link,
                "url": link,
                "snippet": description or "",
            }
        )
    return results


def _item_text(item, tag: str) -> Optional[str]:
    node = item.find(tag)
    if node is None or node.text is None:
        return None
    return node.text.strip()


def _normalize_url(url: str) -> str:
    return url.rstrip("/").lower()


def _is_blocked_result(url: str) -> bool:
    normalized = _normalize_url(url)
    return any(token in normalized for token in _BLOCKED_HOST_TOKENS)
