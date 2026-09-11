from __future__ import annotations
from urllib.parse import urlparse
from ddgs import DDGS

BLOCKED_DOMAINS = {
    "facebook.com", "instagram.com", "youtube.com", "tiktok.com",
    "pinterest.com", "olx.ua", "prom.ua"  # marketplace listing pages are noisy; product subdomains may still appear
}


def _clean_url(url: str) -> str | None:
    if not url or not url.startswith(("http://", "https://")):
        return None
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if not host:
        return None
    # allow *.prom.ua product pages, reject only root prom.ua
    if host in BLOCKED_DOMAINS and host != "prom.ua":
        return None
    if host == "prom.ua":
        return None
    return url.split("#")[0]


def discover_urls(queries: list[str], max_results_per_query: int = 20) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    with DDGS() as ddgs:
        for q in queries:
            try:
                for item in ddgs.text(q, region="ua-uk", max_results=max_results_per_query):
                    u = _clean_url(item.get("href") or item.get("url") or "")
                    if u and u not in seen:
                        seen.add(u)
                        found.append(u)
            except Exception as e:
                print(f"[DISCOVERY] query failed: {q!r}: {e}")
    return found
