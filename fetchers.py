from __future__ import annotations
import time
from urllib.parse import urlparse
import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)

class Fetcher:
    def __init__(self, timeout: int = 20, domain_delay: float = 2.0, use_playwright: bool = True):
        self.timeout = timeout
        self.domain_delay = domain_delay
        self.use_playwright = use_playwright
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
        })
        self._last_request: dict[str, float] = {}

    def _pace(self, url: str):
        host = urlparse(url).netloc.lower()
        last = self._last_request.get(host, 0.0)
        wait = self.domain_delay - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_request[host] = time.time()

    def fetch(self, url: str) -> tuple[str, str]:
        self._pace(url)
        try:
            r = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            r.raise_for_status()
            html = r.text
            if len(html) > 1200:
                return html, "requests"
        except Exception as e:
            print(f"[FETCH] requests failed {url}: {e}")

        if not self.use_playwright:
            return "", "failed"
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=UA, locale="uk-UA")
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
                page.wait_for_timeout(1200)
                html = page.content()
                browser.close()
                return html, "playwright"
        except Exception as e:
            print(f"[FETCH] playwright failed {url}: {e}")
            return "", "failed"
