"""Base scraper class with stealth mode for job sites."""

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from datetime import datetime

from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from database.schema import JobListing, JobDatabase
from scrapers.description_fetcher import DescriptionFetcher

logger = logging.getLogger('scrapers.base')


class BaseScraper(ABC):
    """Abstract base class for job site scrapers with stealth capabilities."""

    # Rate limiting: minimum seconds between requests
    MIN_DELAY_BETWEEN_REQUESTS = 2.0
    MAX_DELAY_BETWEEN_REQUESTS = 5.0

    # Maximum retries for failed requests
    MAX_RETRIES = 3

    # User agent rotation - real browser signatures (updated 2024)
    USER_AGENTS = [
        # Windows Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        # Mac Safari
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Windows Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        # Mac Firefox
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        # Linux Chrome
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    # Viewport sizes to rotate through
    VIEWPORTS = [
        {'width': 1920, 'height': 1080},
        {'width': 1366, 'height': 768},
        {'width': 1440, 'height': 900},
        {'width': 1536, 'height': 864},
    ]

    def __init__(self, db: JobDatabase, headless: bool = True):
        self.db = db
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.last_request_time = 0

    async def init_browser(self):
        """Initialize browser with stealth settings."""
        self.playwright = await async_playwright().start()

        # Launch browser with anti-detection settings
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
                '--disable-features=VizDisplayCompositor',
            ]
        )

        # Create context with realistic browser fingerprint
        self.context = await self.browser.new_context(
            user_agent=random.choice(self.USER_AGENTS),
            viewport=random.choice(self.VIEWPORTS),
            locale='en-GB',
            timezone_id='Europe/London',
            geolocation={'latitude': 51.5074, 'longitude': -0.1278},  # London
            permissions=['geolocation'],
            # Accept languages
            extra_http_headers={
                'Accept-Language': 'en-GB,en;q=0.9,en-US;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            },
        )

        # Inject scripts to hide automation - comprehensive stealth
        await self.context.add_init_script("""
            // Hide webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin' }
                ]
            });

            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-GB', 'en', 'en-US']
            });

            // Override permissions API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Mock chrome object (for detection)
            if (!window.chrome) {
                window.chrome = {};
            }
            window.chrome.runtime = {};

            // Mock navigator.connection
            navigator.connection = {
                effectiveType: '4g',
                rtt: 50,
                downlink: 10,
                saveData: false
            };

            // Hide automation indicators
            delete navigator.__proto__.webdriver;

            // Mock performance
            Object.defineProperty(window.performance, 'memory', {
                value: {
                    totalJSHeapSize: 50000000,
                    usedJSHeapSize: 40000000,
                    jsHeapSizeLimit: 2000000000
                }
            });
        """)

        self.page = await self.context.new_page()

        # Set realistic timeouts
        self.page.set_default_timeout(30000)
        self.page.set_default_navigation_timeout(30000)

    async def _rate_limit_delay(self):
        """Apply rate limiting between requests."""
        now = time.time()
        time_since_last = now - self.last_request_time

        if time_since_last < self.MIN_DELAY_BETWEEN_REQUESTS:
            delay = self.MIN_DELAY_BETWEEN_REQUESTS - time_since_last + random.uniform(0.5, 1.5)
            await asyncio.sleep(delay)
        else:
            await asyncio.sleep(random.uniform(0.5, 1.5))

        self.last_request_time = time.time()

    async def random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Add random human-like delay."""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    async def human_like_scroll(self, count: int = 3):
        """Scroll like a human being would."""
        for _ in range(count):
            await self.page.evaluate(f"window.scrollBy(0, {random.randint(200, 500)})")
            await self.random_delay(0.2, 0.6)

    async def human_like_mouse_move(self):
        """Simulate human-like mouse movements."""
        try:
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            await self.page.mouse.move(x, y)
        except:
            pass

    async def navigate_with_retry(self, url: str, max_retries: int = None) -> bool:
        """Navigate with retry logic and delays between requests."""
        if max_retries is None:
            max_retries = self.MAX_RETRIES

        await self._rate_limit_delay()

        for attempt in range(max_retries):
            try:
                response = await self.page.goto(url, wait_until='domcontentloaded')

                if response and response.status == 200:
                    # Random human-like behavior
                    await asyncio.sleep(random.uniform(1, 2))
                    await self.human_like_scroll(2)
                    await self.human_like_mouse_move()
                    return True
                elif response and response.status == 429:
                    wait_time = (attempt + 1) * 30
                    print(f"[!] Site rate limited (429). Waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                elif response and response.status == 403:
                    print(f"[!] Access forbidden (403). IP may be blocked.")
                    return False
                else:
                    status = response.status if response else 'unknown'
                    print(f"[!] Got status {status}, retrying...")
                    await asyncio.sleep(5)

            except Exception as e:
                print(f"[!] Navigation error (attempt {attempt + 1}): {e}")
                await asyncio.sleep(5)

        return False

    @abstractmethod
    async def search_jobs(self, search_term: str, location: str = "London") -> List[JobListing]:
        """Search for jobs on this platform. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def get_site_name(self) -> str:
        """Return the name of this job site."""
        pass

    def save_job(self, job: JobListing) -> Tuple[bool, str]:
        """Save a single job to the database immediately."""
        return self.db.insert_job(job)

    async def scrape_and_store(self, search_term: str, location: str = "London",
                               save_incrementally: bool = True) -> int:
        """Main method: scrape jobs and store in database.

        Args:
            search_term: Keywords to search for
            location: Location to search in
            save_incrementally: If True, jobs are saved as they're scraped (default)
        """
        await self.init_browser()

        try:
            print(f"[*] Starting scrape on {self.get_site_name()} for '{search_term}' in {location}")

            # Jobs are saved incrementally during search_jobs if save_incrementally=True
            jobs = await self.search_jobs(search_term, location)

            print(f"[*] Found {len(jobs)} jobs")

            if not save_incrementally:
                # Only do batch insert if not saving incrementally
                stats = self.db.insert_jobs_batch(jobs)
                added = stats.get('added', 0)
                print(f"[*] Added {added} new jobs to database")
                print(f"    Updated: {stats.get('updated', 0)}, Skipped: {stats.get('skipped', 0)}")
                return added
            else:
                # Jobs already saved during scraping - just report what we found
                print(f"[*] Jobs were saved incrementally during scraping")
                return len(jobs)

        finally:
            await self.cleanup()

    async def fetch_full_descriptions(self, jobs: List[JobListing], max_jobs: int = None) -> List[JobListing]:
        """
        Fetch full descriptions for a list of jobs using curl_cffi.

        Uses curl_cffi's browser TLS impersonation to bypass anti-bot protections.
        This method is inherited by all scrapers.

        Args:
            jobs: List of jobs to fetch descriptions for
            max_jobs: Maximum number of jobs to process (None = all)

        Returns:
            List of jobs with updated descriptions
        """
        if max_jobs:
            jobs = jobs[:max_jobs]

        source = self.get_site_name()
        logger.info(f"[{source}] Fetching full descriptions for {len(jobs)} jobs using curl_cffi...")

        # Initialize the description fetcher with TLS impersonation
        fetcher = DescriptionFetcher(max_retries=3, timeout=30)

        for i, job in enumerate(jobs):
            if not job.url:
                logger.warning(f"[{source}] Skipping {job.title} - no URL")
                continue

            try:
                logger.info(f"[{source}] [{i+1}/{len(jobs)}] Fetching: {job.title}")

                # Use curl_cffi to fetch the description
                description = fetcher.fetch_description(job.url, source=source)

                if description:
                    job.description = description
                    logger.info(f"[{source}] Updated description for {job.title} ({len(description)} chars)")
                else:
                    logger.warning(f"[{source}] Could not extract description for {job.title}")

                # Small delay between requests
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"[{source}] Error fetching details for {job.title}: {e}")

        logger.info(f"[{source}] Completed fetching descriptions for {len(jobs)} jobs")
        return jobs

    async def cleanup(self):
        """Clean up browser resources."""
        try:
            if self.page:
                await self.page.close()
        except:
            pass

        try:
            if self.context:
                await self.context.close()
        except:
            pass

        try:
            if self.browser:
                await self.browser.close()
        except:
            pass

        try:
            if self.playwright:
                await self.playwright.stop()
        except:
            pass
