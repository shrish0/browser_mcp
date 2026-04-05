import logging
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from exceptions import LoginRequiredError, NotFoundError, RedirectError, ScraperError
from utils import (
    clean_text,
    extract_headings,
    extract_paragraphs,
    extract_metadata,
    extract_interactive_elements,
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

    def _is_login_url(self, url: str) -> bool:
        """Detect common login/auth URL paths."""
        lower_url = url.lower()
        return any(
            term in lower_url
            for term in ["/login", "/signin", "/sign-in", "/auth", "/authenticate", "/oauth", "/session"]
        )

    def scrape_static(self, url: str) -> Optional[Dict]:
        """Scrape webpage using static requests/BeautifulSoup."""
        try:
            logger.info(f"Starting static scrape for {url}")
            headers = {"User-Agent": self.user_agent}
            response = requests.get(
                url, headers=headers, timeout=10, allow_redirects=True
            )

            # Check if URL changed (redirect occurred)
            is_redirect = response.url != url
            if is_redirect and self._is_login_url(response.url):
                logger.info(
                    f"URL changed from {url} to {response.url} - redirect detected (likely login)"
                )
                raise RedirectError(
                    error_message="Redirected to a login or authentication page",
                    status_code=response.status_code,
                    details={"redirect_url": response.url, "source_url": url},
                )
                raise RedirectError(
                    error_message="Redirected to a login or authentication page",
                    status_code=response.status_code,
                    details={"redirect_url": response.url, "source_url": url},
                )

            # Check for redirect chains that indicate login/auth required
            if len(response.history) > 0:
                # If redirected, check if it's to a login page
                final_url = response.url.lower()
                if any(
                    term in final_url for term in ["login", "auth", "signin", "sign-in"]
                ):
                    logger.info(f"Redirect to login detected for {url}")
                    raise RedirectError(
                        error_message="Redirected to a login or authentication page",
                        status_code=response.status_code,
                        details={"redirect_url": response.url, "source_url": url},
                    )

            # Check HTTP status codes before raising
            if response.status_code == 401:
                logger.info(f"Unauthorized (401) for {url}")
                raise LoginRequiredError(
                    error_message="Unauthorized access - login required",
                    status_code=401,
                    details={"url": url},
                )
            elif response.status_code == 403:
                logger.info(f"Forbidden (403) for {url}")
                raise LoginRequiredError(
                    error_message="Forbidden access - login required",
                    status_code=403,
                    details={"url": url},
                )
            elif response.status_code == 404:
                logger.warning(f"Not found (404) for {url}")
                if is_redirect:
                    raise NotFoundError(
                        error_message="Page not found",
                        status_code=404,
                        details={"url": url, "redirect_url": response.url},
                    )
                # If the requested URL itself is a 404 page, return it for inspection.
            elif response.status_code >= 400:
                logger.warning(f"HTTP error {response.status_code} for {url}")
                raise ScraperError(
                    error_message=f"HTTP {response.status_code} - {response.reason}",
                    status_code=response.status_code,
                    details={"url": url},
                )

            if not (response.status_code == 404 and not is_redirect):
                response.raise_for_status()

            if "text/html" not in response.headers.get("content-type", "").lower():
                logger.warning(f"Non-HTML content for {url}")
                raise ScraperError(
                    error_message="Unsupported non-HTML content",
                    status_code=415,
                    details={"url": url},
                )

            soup = BeautifulSoup(response.text, "html.parser")

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
            interactive_elements = extract_interactive_elements(soup)

            result = {
                "title": title,
                "headings": headings,
                "paragraphs": paragraphs,
                "metadata": metadata,
                "interactive_elements": interactive_elements,
                "raw_html": response.text,
            }

            # Heuristic: If no content at all (empty title, no headings, no paragraphs),
            # it's likely a JavaScript-rendered SPA that needs authentication
            if (
                not title
                and not headings
                and not paragraphs
                and not metadata.get("description")
            ):
                logger.info(f"No readable content for {url} - likely protected SPA")
                if is_redirect:
                    raise LoginRequiredError(
                        error_message="No readable content - likely protected or login-required page",
                        status_code=401,
                        details={"url": url},
                    )

            if requires_login(result) and is_redirect:
                logger.info(f"Login required for {url}")
                raise LoginRequiredError(
                    error_message="Login required",
                    status_code=401,
                    details={"url": url},
                )

            logger.info(f"Static scrape successful for {url}")
            return result

        except requests.RequestException as e:
            logger.exception("Static scrape failed for %s: %s", url, e)
            raise ScraperError(
                error_message="Network error while scraping page",
                status_code=502,
                details={"url": url, "reason": str(e)},
            )
        except Exception as exc:
            logger.exception("Unexpected error in static scrape for %s", url)
            raise ScraperError(
                error_message="Unexpected error while scraping page",
                status_code=500,
                details={"url": url, "reason": str(exc)},
            )

    def scrape_dynamic(self, url: str) -> Optional[Dict]:
        """Scrape webpage using Playwright for dynamic content."""
        try:
            logger.info(f"Starting dynamic scrape for {url}")
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)  # Additional wait for content loading
                final_url = page.url
                content = page.content()
                browser.close()

            if final_url != url and self._is_login_url(final_url):
                logger.info(
                    f"URL changed from {url} to {final_url} - redirect detected (likely login)"
                )
                raise RedirectError(
                    error_message="Redirected to a login or authentication page",
                    status_code=302,
                    details={"redirect_url": final_url, "source_url": url},
                )

            soup = BeautifulSoup(content, "html.parser")

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
            interactive_elements = extract_interactive_elements(soup)

            result = {
                "title": title,
                "headings": headings,
                "paragraphs": paragraphs,
                "metadata": metadata,
                "interactive_elements": interactive_elements,
                "raw_html": content,
            }

            if requires_login(result) and final_url != url:
                logger.info(f"Login required for {url}")
                raise LoginRequiredError(
                    error_message="Login required",
                    status_code=401,
                    details={"url": url},
                )

            logger.info(f"Dynamic scrape successful for {url}")
            return result

        except Exception as exc:
            logger.exception("Dynamic scrape failed for %s", url)
            raise ScraperError(
                error_message="Dynamic scraping failed",
                status_code=502,
                details={"url": url, "reason": str(exc)},
            )

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

        raise ScraperError(
            error_message="Unable to scrape webpage",
            status_code=502,
            details={"url": url},
        )
