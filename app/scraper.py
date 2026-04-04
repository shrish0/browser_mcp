import logging
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from utils import (
    clean_text,
    extract_headings,
    extract_paragraphs,
    extract_metadata,
    requires_login,
)

logger = logging.getLogger(__name__)


class WebScraper:
    def __init__(self):
        self.user_agent = "BrowserMCP/1.0 (https://github.com/your-repo/browser-mcp)"

    def _validate_url(self, url: str) -> None:
        """Validate URL has scheme and netloc."""
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")

    def scrape_static(self, url: str) -> Optional[Dict]:
        """Scrape webpage using static requests/BeautifulSoup."""
        try:
            logger.info(f"Starting static scrape for {url}")
            headers = {"User-Agent": self.user_agent}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            if "text/html" not in response.headers.get("content-type", "").lower():
                logger.warning(f"Non-HTML content for {url}")
                return None

            soup = BeautifulSoup(response.text, "lxml")

            # Remove scripts and styles
            for tag in soup(["script", "style"]):
                tag.decompose()

            # Extract title
            title = ""
            if soup.title:
                title = clean_text(soup.title.get_text())

            # Extract other data
            headings = extract_headings(soup)
            paragraphs = extract_paragraphs(soup)
            metadata = extract_metadata(soup)

            result = {
                "title": title,
                "headings": headings,
                "paragraphs": paragraphs,
                "metadata": metadata,
            }

            if requires_login(result):
                logger.info(f"Login required for {url}")
                return {"requires_login": True}

            logger.info(f"Static scrape successful for {url}")
            return result

        except requests.RequestException:
            logger.exception("Static scrape failed for %s", url)
            return None
        except Exception:
            logger.exception("Unexpected error in static scrape for %s", url)
            return None

    def scrape_dynamic(self, url: str) -> Optional[Dict]:
        """Scrape webpage using Playwright for dynamic content."""
        try:
            logger.info(f"Starting dynamic scrape for {url}")
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)  # Additional wait for content loading
                content = page.content()
                browser.close()

            soup = BeautifulSoup(content, "lxml")

            # Remove scripts and styles
            for tag in soup(["script", "style"]):
                tag.decompose()

            # Extract title
            title = ""
            if soup.title:
                title = clean_text(soup.title.get_text())

            # Extract other data
            headings = extract_headings(soup)
            paragraphs = extract_paragraphs(soup)
            metadata = extract_metadata(soup)

            result = {
                "title": title,
                "headings": headings,
                "paragraphs": paragraphs,
                "metadata": metadata,
            }

            if requires_login(result):
                logger.info(f"Login required for {url}")
                return {"requires_login": True}

            logger.info(f"Dynamic scrape successful for {url}")
            return result

        except Exception:
            logger.exception("Dynamic scrape failed for %s", url)
            return None

    def scrape(self, url: str, use_dynamic: bool = False) -> Optional[Dict]:
        """Scrape webpage, trying static first, fallback to dynamic if enabled."""
        self._validate_url(url)

        # Try static scraping first
        result = self.scrape_static(url)
        if result is not None:
            return result

        # If static failed and dynamic is enabled, try dynamic
        if use_dynamic:
            logger.info(f"Static scrape failed, trying dynamic for {url}")
            return self.scrape_dynamic(url)

        return None
