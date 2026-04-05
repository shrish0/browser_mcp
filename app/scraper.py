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

    def _urls_are_different(self, url1: str, url2: str) -> bool:
        """Check if two URLs are fundamentally different (ignoring scheme, www, and trailing slashes)."""
        parsed1 = urlparse(url1)
        parsed2 = urlparse(url2)
        
        netloc1 = parsed1.netloc.replace("www.", "").lower()
        netloc2 = parsed2.netloc.replace("www.", "").lower()
        
        path1 = parsed1.path.rstrip('/')
        path2 = parsed2.path.rstrip('/')
        
        return netloc1 != netloc2 or path1 != path2

    def _is_login_url(self, url: str) -> bool:
        """Detect common login/auth URL paths."""
        lower_url = url.lower()
        return any(
            term in lower_url
            for term in [
                "/login",
                "/signin",
                "/sign-in",
                "/auth",
                "/authenticate",
                "/oauth",
                "/session",
                "/register",
                "/signup",
                "/sign-up",
            ]
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
            # If the URL changed significantly, we raise an exception to prevent AI from operating on wrong page
            is_redirect = self._urls_are_different(url, response.url)
            if is_redirect:
                logger.info(
                    f"URL changed significantly from {url} to {response.url} - redirect detected"
                )
                raise RedirectError(
                    error_message="Redirected to a different page (likely login or missing page)",
                    status_code=302,
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
                raise NotFoundError(
                    error_message="Page not found",
                    status_code=404,
                    details={"url": url, "redirect_url": response.url if is_redirect else None},
                )
            elif response.status_code >= 400:
                logger.warning(f"HTTP error {response.status_code} for {url}")
                raise ScraperError(
                    error_message=f"HTTP {response.status_code} - {response.reason}",
                    status_code=response.status_code,
                    details={"url": url},
                )

            if response.status_code != 404: # Already handled
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
            # it's likely a JavaScript-rendered SPA that needs authentication or JS execution
            if (
                not title
                and not headings
                and not paragraphs
                and not metadata.get("description")
            ):
                logger.info(f"No readable content for {url} - likely protected SPA or requires JS")
                # Removed 'if is_redirect' here so it properly fails and falls back to dynamic
                raise ScraperError(
                    error_message="No readable content - likely JavaScript SPA or protected page",
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

        except ScraperError:
            raise
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

            final_url = page.url
            if self._urls_are_different(url, final_url):
                logger.info(
                    f"URL changed significantly from {url} to {final_url} - redirect detected"
                )
                raise RedirectError(
                    error_message="Redirected to a different page (likely login or missing page)",
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

        except ScraperError:
            raise
        except Exception as exc:
            logger.exception("Dynamic scrape failed for %s", url)
            raise ScraperError(
                error_message="Dynamic scraping failed",
                status_code=502,
                details={"url": url, "reason": str(exc)},
            )

    def scrape(self, url: str, use_dynamic: bool = False) -> Optional[Dict]:
        """Scrape webpage. Uses dynamic scraping if requested, otherwise tries static."""
        self._validate_url(url)

        if use_dynamic:
            logger.info(f"Dynamic scraping requested for {url}")
            return self.scrape_dynamic(url)

        # Try static scraping
        return self.scrape_static(url)
