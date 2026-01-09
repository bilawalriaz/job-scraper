"""Fetch full job descriptions using curl_cffi to bypass TLS fingerprinting."""

import json
import logging
import re
from typing import Optional
from urllib.parse import urlparse
from curl_cffi import requests
from bs4 import BeautifulSoup
import html

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

    # Site-specific selectors for job descriptions
    SITE_SELECTORS = {
        'totaljobs': [
            '[data-at="job-description"]',
            '[data-genesis-element="TEXT"]',
            'span[data-genesis-element="TEXT"]',
            '[class*="job-ad-display"]',
        ],
        'reed': [
            '[data-qa="job-description"]',
            '.job-description',
            '.description',
            '[itemprop="description"]',
            '.job-details-description',
            '#job-description',
        ],
        'indeed': [
            '#jobDescriptionText',
            '.jobsearch-jobDescriptionText',
            '[data-testid="jobDescriptionText"]',
            '.job-description',
            '#jobDescription',
        ],
        'cvlibrary': [
            '.job-description',
            '.job__description',
            '[class*="job-description"]',
            '.vacancy-description',
            '#job-description',
        ],
    }

    def __init__(self, max_retries: int = 3, timeout: int = 30):
        """
        Initialize the description fetcher.

        Args:
            max_retries: Number of times to retry with different browsers
            timeout: Request timeout in seconds
        """
        self.max_retries = max_retries
        self.timeout = timeout

    def _detect_source(self, url: str) -> Optional[str]:
        """Detect which job site a URL belongs to."""
        if not url:
            return None
        domain = urlparse(url).netloc.lower()
        if 'totaljobs' in domain:
            return 'totaljobs'
        elif 'reed' in domain:
            return 'reed'
        elif 'indeed' in domain:
            return 'indeed'
        elif 'cv-library' in domain or 'cvlibrary' in domain:
            return 'cvlibrary'
        return None

    def fetch_description(self, url: str, source: str = None) -> Optional[str]:
        """
        Fetch full job description from a job URL.

        Args:
            url: The job listing URL
            source: The job site source (auto-detected if not provided)

        Returns:
            The job description text, or None if fetching failed
        """
        if not url:
            logger.warning("No URL provided")
            return None

        # Auto-detect source from URL if not provided
        if not source:
            source = self._detect_source(url)
            logger.debug(f"Auto-detected source: {source}")

        for browser in self.BROWSER_TYPES:
            try:
                logger.debug(f"Trying to fetch {url} with {browser}")

                response = requests.get(
                    url,
                    impersonate=browser,
                    headers=self.DEFAULT_HEADERS,
                    timeout=self.timeout,
                    allow_redirects=True
                )

                if response.status_code == 200:
                    # Parse HTML and extract description
                    description = self._extract_description(response.text, source)
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

    def _extract_from_json_ld(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract job description from JSON-LD structured data.

        Many job sites include Schema.org JobPosting markup which contains
        the full description in a standardized format.
        """
        try:
            # Find all JSON-LD script tags
            scripts = soup.find_all('script', type='application/ld+json')

            for script in scripts:
                try:
                    data = json.loads(script.string)

                    # Handle both single object and array of objects
                    if isinstance(data, list):
                        for item in data:
                            if item.get('@type') == 'JobPosting' and item.get('description'):
                                desc = item['description']
                                # Clean HTML entities and tags
                                desc = self._clean_description(desc)
                                if len(desc) > 200:
                                    logger.debug("Found description in JSON-LD array")
                                    return desc
                    elif isinstance(data, dict):
                        # Could be JobPosting directly or nested in @graph
                        if data.get('@type') == 'JobPosting' and data.get('description'):
                            desc = self._clean_description(data['description'])
                            if len(desc) > 200:
                                logger.debug("Found description in JSON-LD object")
                                return desc
                        # Check @graph array
                        if '@graph' in data:
                            for item in data['@graph']:
                                if item.get('@type') == 'JobPosting' and item.get('description'):
                                    desc = self._clean_description(item['description'])
                                    if len(desc) > 200:
                                        logger.debug("Found description in JSON-LD @graph")
                                        return desc
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.debug(f"Error parsing JSON-LD: {e}")
                    continue
        except Exception as e:
            logger.debug(f"Error searching for JSON-LD: {e}")

        return None

    def _clean_description(self, desc: str) -> str:
        """Clean HTML tags and entities from description text."""
        if not desc:
            return ""

        # Decode HTML entities
        desc = html.unescape(desc)

        # Remove HTML tags but preserve text
        soup = BeautifulSoup(desc, 'lxml')
        text = soup.get_text(separator=' ', strip=True)

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def _extract_description(self, html_content: str, source: str = None) -> Optional[str]:
        """
        Extract job description from HTML.

        Extraction order:
        1. JSON-LD structured data (most reliable - standard Schema.org format)
        2. Site-specific CSS selectors
        3. Generic CSS selectors
        4. Fallback to largest text block

        Args:
            html_content: The HTML content
            source: The job site source for site-specific selectors

        Returns:
            The description text or None
        """
        soup = BeautifulSoup(html_content, 'lxml')

        # 1. Try JSON-LD structured data first (most reliable)
        json_ld_desc = self._extract_from_json_ld(soup)
        if json_ld_desc:
            logger.info(f"Extracted description from JSON-LD ({len(json_ld_desc)} chars)")
            return json_ld_desc

        # 2. Get site-specific selectors if available
        selectors = self.SITE_SELECTORS.get(source, []) if source else []

        # 3. Add generic fallback selectors
        generic_selectors = [
            '[data-at="job-description"]',
            '[class*="job-description"]',
            '[class*="jobDescription"]',
            '.description',
            '#description',
        ]
        selectors = selectors + [s for s in generic_selectors if s not in selectors]

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
                        logger.info(f"Extracted description from selector '{selector}' ({len(largest_text)} chars)")
                        return largest_text
            except Exception as e:
                logger.debug(f"Error with selector '{selector}': {e}")
                continue

        # 4. Fallback: try to find the largest text block in the body
        try:
            body = soup.find('body')
            if body:
                # Remove script and style elements
                for script in body(['script', 'style', 'nav', 'header', 'footer']):
                    script.decompose()

                # Get all text
                text = body.get_text(separator=' ', strip=True)
                if len(text) > 500:  # Reasonable minimum for a job page
                    logger.info(f"Extracted description from body fallback ({len(text)} chars)")
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
