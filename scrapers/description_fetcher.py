"""Fetch full job descriptions using curl_cffi to bypass TLS fingerprinting."""

import logging
from typing import Optional
from curl_cffi import requests
from bs4 import BeautifulSoup

logger = logging.getLogger('scrapers.description_fetcher')


class DescriptionFetcher:
    """
    Fetch full job descriptions using curl_cffi for TLS fingerprint bypass.

    This uses curl_cffi which can impersonate real browser TLS fingerprints,
    allowing it to bypass protections like TotalJobs' ERR_HTTP2_PROTOCOL_ERROR.
    """

    # Default headers to look like a real browser
    DEFAULT_HEADERS = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-GB,en;q=0.9,en-US;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }

    # Browser impersonations to try (in order of preference)
    BROWSER_TYPES = ['chrome', 'chrome120', 'chrome110', 'edge']

    def __init__(self, max_retries: int = 3, timeout: int = 30):
        """
        Initialize the description fetcher.

        Args:
            max_retries: Number of times to retry with different browsers
            timeout: Request timeout in seconds
        """
        self.max_retries = max_retries
        self.timeout = timeout

    def fetch_description(self, url: str) -> Optional[str]:
        """
        Fetch full job description from a job URL.

        Args:
            url: The job listing URL

        Returns:
            The job description text, or None if fetching failed
        """
        if not url:
            logger.warning("No URL provided")
            return None

        for browser in self.BROWSER_TYPES:
            try:
                logger.debug(f"Trying to fetch {url} with {browser}")

                response = requests.get(
                    url,
                    impersonate=browser,
                    headers=self.DEFAULT_HEADERS,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    # Parse HTML and extract description
                    description = self._extract_description(response.text)
                    if description:
                        logger.info(f"Successfully fetched description ({len(description)} chars) using {browser}")
                        return description
                    else:
                        logger.warning(f"Got 200 but couldn't extract description with {browser}")
                else:
                    logger.warning(f"Got status {response.status_code} with {browser}")

            except Exception as e:
                logger.warning(f"Error with {browser}: {e}")
                continue

        logger.error(f"Failed to fetch description from {url} after trying all browsers")
        return None

    def _extract_description(self, html: str) -> Optional[str]:
        """
        Extract job description from HTML.

        Tries multiple selectors to handle different page layouts.

        Args:
            html: The HTML content

        Returns:
            The description text or None
        """
        soup = BeautifulSoup(html, 'lxml')

        # Try different selectors in order of preference
        selectors = [
            '[data-at="job-description"]',
            '[data-genesis-element="TEXT"]',
            'span[data-genesis-element="TEXT"]',
            '[class*="job-ad-display"]',
        ]

        for selector in selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    # Get the largest text block (likely the description)
                    largest_text = ""
                    for elem in elements:
                        text = elem.get_text(separator=' ', strip=True)
                        if len(text) > len(largest_text):
                            largest_text = text

                    # Only return if it's a reasonable length
                    if len(largest_text) > 200:
                        return largest_text
            except Exception as e:
                logger.debug(f"Error with selector '{selector}': {e}")
                continue

        # If no selector worked, try to find the largest text block in the body
        try:
            body = soup.find('body')
            if body:
                # Remove script and style elements
                for script in body(['script', 'style', 'nav', 'header', 'footer']):
                    script.decompose()

                # Get all text
                text = body.get_text(separator=' ', strip=True)
                if len(text) > 500:  # Reasonable minimum for a job page
                    return text
        except Exception as e:
            logger.debug(f"Error extracting from body: {e}")

        return None

    def fetch_multiple(self, urls: list[str]) -> dict[str, Optional[str]]:
        """
        Fetch descriptions for multiple URLs.

        Args:
            urls: List of URLs to fetch

        Returns:
            Dictionary mapping URL to description (or None if failed)
        """
        results = {}
        for url in urls:
            results[url] = self.fetch_description(url)
        return results
