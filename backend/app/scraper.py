import logging
import os
import time
import random
import urllib.parse
import asyncio
import functools
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright
except Exception:
    async_playwright = None

SEEK_BASE_URL = os.getenv("SEEK_BASE_URL", "https://www.seek.com.au")
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
]


def _search_url(role: str, location: str, page: int) -> str:
    return f"{SEEK_BASE_URL}/jobs?keywords={urllib.parse.quote_plus(role or '')}&location={urllib.parse.quote_plus(location or '')}&page={page}"


def _parse_job_cards(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/job/" not in href and "/jobs/" not in href:
            continue
        full = urllib.parse.urljoin(SEEK_BASE_URL, href)
        title = (a.get_text() or "").strip() or a.get("aria-label", "").strip()
        if not title:
            continue
        results.append({"ad_url": full, "source_subject": title})
    # dedupe
    seen = set()
    out = []
    for r in results:
        if r["ad_url"] in seen:
            continue
        seen.add(r["ad_url"])
        out.append(r)
    return out


def _fetch_with_requests(url: str, timeout: int = 15) -> str:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": SEEK_BASE_URL + "/",
        "Connection": "keep-alive",
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code == 403:
        raise RuntimeError("403")
    resp.raise_for_status()
    return resp.text


async def _fetch_with_requests_async(url: str, timeout: int = 15) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, functools.partial(_fetch_with_requests, url, timeout))


async def _fetch_with_playwright_async(url: str, timeout: int = 30000) -> str:
    """
    Playwright expects timeout in milliseconds. This helper accepts either:
      - milliseconds (>=1000) or
      - seconds (small ints like 15) -> will be converted to ms.
    """
    if async_playwright is None:
        raise RuntimeError("playwright async API not installed")

    # convert seconds (<1000) to milliseconds
    timeout_ms = int(timeout) if int(timeout) >= 1000 else int(float(timeout) * 1000)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=random.choice(USER_AGENTS))
        await page.goto(url, timeout=timeout_ms)
        html = await page.content()
        await browser.close()
        return html


async def fetch_seek_page(role: str, location: str, page: int, timeout: int = 15) -> List[Dict]:
    url = _search_url(role, location, page)
    await asyncio.sleep(random.uniform(0.8, 1.6))
    try:
        html = await _fetch_with_requests_async(url, timeout=timeout)
    except Exception as e:
        if "403" in str(e) or async_playwright is not None:
            try:
                html = await _fetch_with_playwright_async(url, timeout=timeout)
            except Exception as e2:
                raise RuntimeError(f"Both requests and Playwright failed: {e2}") from e2
        else:
            raise
    return _parse_job_cards(html)


async def scrape_seek(role: str, location: str, pages: int = 1, delay: float = 1.0) -> List[Dict]:
    all_jobs: List[Dict] = []
    seen = set()
    for p in range(1, pages + 1):
        jobs = await fetch_seek_page(role, location, p)
        if not jobs:
            break
        new_found = 0
        for j in jobs:
            url = j.get("ad_url")
            if not url or url in seen:
                continue
            seen.add(url)
            all_jobs.append(j)
            new_found += 1
        await asyncio.sleep(delay)
        if new_found == 0:
            break
    return all_jobs

# filepath: c:\Users\danbr\OneDrive\Documents\Seek Scraper App\backend\tools\test_scraper.py
import asyncio
from app import scraper

async def main():
    jobs = await scraper.scrape_seek(role="Electrician", location="Adelaide", pages=1)
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j)

if __name__ == "__main__":
    asyncio.run(main())

