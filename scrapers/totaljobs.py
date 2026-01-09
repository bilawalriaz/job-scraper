"""TotalJobs scraper with stealth mode."""

import re
import logging
from typing import List, Optional
from urllib.parse import urlencode

from scrapers.base import BaseScraper
from scrapers.description_fetcher import DescriptionFetcher
from database.schema import JobListing

logger = logging.getLogger('scrapers.totaljobs')


class TotalJobsScraper(BaseScraper):
    """Scraper for TotalJobs.co.uk with anti-detection measures."""

    BASE_URL = "https://www.totaljobs.com"

    # Employment type mappings matching TotalJobs expectations
    EMPLOYMENT_TYPES = {
        'permanent': 'permanent',
        'perm': 'permanent',
        'contract': 'contract',
        'temp': 'temporary',
        'temporary': 'temporary',
        'whf': 'whf',           # TotalJobs uses 'whf' not 'wfh'
        'wfh': 'whf',           # Standard alias maps to TotalJobs 'whf'
        'work from home': 'whf',
        'remote': 'whf',
        'home': 'whf',
    }

    def get_site_name(self) -> str:
        return "totaljobs"

    def _normalize_employment_type(self, emp_type: str) -> Optional[str]:
        """Normalize employment type to match site expectations."""
        if not emp_type:
            return None
        normalized = emp_type.lower().strip()
        return self.EMPLOYMENT_TYPES.get(normalized, None)

    async def search_jobs(self,
                         search_term: str,
                         location: str = "London",
                         radius: int = 10,
                         employment_types: Optional[str] = None,
                         max_pages: int = 5,
                         save_incrementally: bool = True) -> List[JobListing]:
        """
        Search for jobs on TotalJobs with pagination support.

        Args:
            search_term: Keywords to search for
            location: Location to search in
            radius: Search radius in miles (max 30)
            employment_types: Comma-separated employment types (e.g., "contract,permanent,whf")
            max_pages: Maximum number of pages to scrape
            save_incrementally: If True, save each job to DB as it's scraped
        """
        jobs = []
        stats = {'added': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

        # Cap radius at 30 miles (site limitation)
        radius = min(radius, 30)

        # Build search URL
        params = {
            'q': search_term,
            'l': location,
            'radius': radius,
            's': '1',  # sort by relevance
        }

        # Add employment type filter if specified
        if employment_types:
            # Take the first valid employment type
            for et in employment_types.split(','):
                normalized = self._normalize_employment_type(et.strip())
                if normalized:
                    params['employment'] = normalized
                    logger.info(f"Using employment type filter: {normalized}")
                    break

        logger.info(f"Searching with params: {params}")

        # Load first page
        search_url = f"{self.BASE_URL}/jobs?{urlencode(params)}"
        if not await self.navigate_with_retry(search_url):
            logger.error(f"Failed to load {search_url}")
            return jobs

        # Paginate through results by clicking Next button
        for page_num in range(1, max_pages + 1):
            # Wait for job listings to load
            try:
                await self.page.wait_for_selector('[data-at="job-item"]', timeout=10000)
            except:
                logger.info(f"No more jobs found on page {page_num}")
                break

            # Extract job cards
            job_cards = await self.page.query_selector_all('[data-at="job-item"]')
            logger.info(f"Found {len(job_cards)} job cards on page {page_num}")

            if not job_cards:
                logger.info("No more job cards found, stopping pagination")
                break

            for card in job_cards:
                try:
                    job_data = await self._extract_job_data(card)
                    if job_data:
                        jobs.append(job_data)
                        # Save immediately if incremental saving is enabled
                        if save_incrementally:
                            success, message = self.save_job(job_data)
                            if 'Added' in message:
                                stats['added'] += 1
                                logger.info(f"Saved: {job_data.title} at {job_data.company}")
                            elif 'Updated' in message:
                                stats['updated'] += 1
                            elif 'Skipped' in message or 'Duplicate' in message:
                                stats['skipped'] += 1
                            else:
                                stats['errors'] += 1
                except Exception as e:
                    logger.error(f"Error extracting job: {e}")
                    continue

            # Log progress after each page
            if save_incrementally:
                logger.info(f"Page {page_num} complete - Total: {len(jobs)} scraped, {stats['added']} added, {stats['skipped']} skipped")

            # Check if there's a next page button - try multiple selectors
            next_button = (
                await self.page.query_selector('[data-at="pagination-next"]') or
                await self.page.query_selector('a[aria-label="Next"]') or
                await self.page.query_selector('li.pagination-next a') or
                await self.page.query_selector('a.next')
            )

            if not next_button:
                logger.info(f"No next page button found, stopping at page {page_num}")
                break

            # Check if button is disabled
            is_disabled = False
            class_list = await next_button.get_attribute('class') or ''
            aria_disabled = await next_button.get_attribute('aria-disabled')

            if 'disabled' in class_list.lower() or aria_disabled == 'true':
                logger.info(f"Next button is disabled, stopping at page {page_num}")
                break

            # Click next button to navigate naturally (avoids anti-bot detection)
            logger.info(f"Clicking next button to go to page {page_num + 1}...")
            try:
                # Scroll button into view
                await next_button.scroll_into_view_if_needed()
                await self.random_delay(0.5, 1)

                # Get the href before clicking (fallback if click doesn't trigger nav)
                next_href = await next_button.get_attribute('href')

                # Try clicking the button first
                try:
                    await next_button.click(force=True, timeout=5000)
                    # Wait for navigation to complete
                    await self.page.wait_for_load_state('domcontentloaded', timeout=10000)
                except Exception as click_error:
                    # Click failed, try direct URL navigation
                    logger.info(f"Click failed ({click_error}), trying direct URL navigation")
                    if next_href:
                        if next_href.startswith('http'):
                            await self.page.goto(next_href, wait_until='domcontentloaded', timeout=15000)
                        else:
                            await self.page.goto(f"{self.BASE_URL}{next_href}", wait_until='domcontentloaded', timeout=15000)
                    else:
                        raise

                # Wait for job cards to appear (confirmation of page load)
                await self.page.wait_for_selector('[data-at="job-item"]', timeout=15000)

                logger.info(f"Successfully navigated to page {page_num + 1}")
            except Exception as e:
                error_msg = str(e)
                # Check for transient network errors that shouldn't stop pagination
                transient_errors = ['HTTP2_PROTOCOL_ERROR', 'ERR_CONNECTION_', 'ERR_NETWORK_', 'net::']
                is_transient = any(err in error_msg for err in transient_errors)
                if is_transient:
                    logger.warning(f"Transient network error on page {page_num + 1}: {e}")
                    logger.info("Stopping pagination due to network issues (not a pagination bug)")
                else:
                    logger.warning(f"Failed to navigate to page {page_num + 1}: {e}")
                break

        logger.info(f"Total jobs scraped: {len(jobs)}")
        if save_incrementally:
            logger.info(f"Final stats - Added: {stats['added']}, Updated: {stats['updated']}, Skipped: {stats['skipped']}")
        return jobs

    async def _extract_job_data(self, card) -> JobListing:
        """Extract data from a job card element."""
        scraped_at = self._get_timestamp()

        # Title and URL
        title_elem = await card.query_selector('[data-at="job-item-title"]')
        title = await title_elem.inner_text() if title_elem else "N/A"
        url = await title_elem.get_attribute('href') if title_elem else ""

        # Full URL if needed
        if url and not url.startswith('http'):
            url = f"{self.BASE_URL}{url}"

        # Company
        company_elem = await card.query_selector('[data-at="job-item-company-name"]')
        company = await company_elem.inner_text() if company_elem else "N/A"

        # Location
        location_elem = await card.query_selector('[data-at="job-item-location"]')
        location = await location_elem.inner_text() if location_elem else "N/A"

        # Salary
        salary_elem = await card.query_selector('[data-at="job-item-salary-info"]')
        salary = await salary_elem.inner_text() if salary_elem else None

        # Job type
        type_elem = await card.query_selector('[data-at="job-item-job-type"]')
        job_type = await type_elem.inner_text() if type_elem else None

        # Employment type badges (contract, permanent, etc)
        emp_type_elem = await card.query_selector('[data-at="job-item-employment-type"]')
        employment_type = await emp_type_elem.inner_text() if emp_type_elem else None

        # If no employment type found, try to infer from other elements
        if not employment_type:
            # Check for remote/work from home indicators
            location_lower = location.lower() if location else ""
            if 'remote' in location_lower or 'home' in location_lower:
                employment_type = 'WHF'
            elif job_type:
                job_type_lower = job_type.lower()
                if 'contract' in job_type_lower:
                    employment_type = 'contract'
                elif 'permanent' in job_type_lower or 'perm' in job_type_lower:
                    employment_type = 'permanent'

        # Posted date
        posted_elem = await card.query_selector('[data-at="job-item-timeago"]')
        posted_date = await posted_elem.inner_text() if posted_elem else None

        # Description
        desc_elem = await card.query_selector('[data-at="jobcard-content"]')
        description = await desc_elem.inner_text() if desc_elem else ""

        # Clean up description
        description = ' '.join(description.split()) if description else ""

        return JobListing(
            title=title.strip(),
            company=company.strip(),
            location=location.strip(),
            description=description.strip(),
            salary=salary.strip() if salary else None,
            job_type=job_type.strip() if job_type else None,
            posted_date=posted_date.strip() if posted_date else None,
            url=url,
            source=self.get_site_name(),
            scraped_at=scraped_at,
            employment_type=employment_type.strip() if employment_type else None
        )

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat()


class TotalJobsDetailedScraper(TotalJobsScraper):
    """Enhanced scraper that navigates to each job page for full details."""

    async def _dismiss_overlays(self) -> bool:
        """
        Dismiss cookie consent and login modals that block job description access.
        Returns True if any overlay was dismissed.
        """
        dismissed_any = False

        # List of selectors for cookie consent buttons (common patterns)
        cookie_selectors = [
            'button:has-text("Accept")',
            'button:has-text("Accept All")',
            'button:has-text("I Agree")',
            'button:has-text("Accept Cookies")',
            'button:has-text("Continue")',
            '#onetrust-accept-btn-handler',
            '.accept-cookies',
            '[data-testid="cookie-accept"]',
            'button[aria-label="Accept cookies"]',
        ]

        # Try to dismiss cookie banner
        for selector in cookie_selectors:
            try:
                button = await self.page.query_selector(selector)
                if button:
                    # Check if button is visible
                    is_visible = await button.is_visible()
                    if is_visible:
                        logger.info(f"Dismissing cookie banner with selector: {selector}")
                        await button.click(timeout=3000)
                        await self.random_delay(0.5, 1.0)
                        dismissed_any = True
                        break
            except:
                continue

        # Wait a bit for any animations
        await self.random_delay(0.5, 1.0)

        # List of selectors for close buttons on modals/popups
        close_selectors = [
            'button[aria-label="Close"]',
            'button[aria-label="close"]',
            'button.close',
            'button.modal-close',
            '.close-button',
            '[data-testid="close"]',
            'button:has-text("Close")',
            'button:has-text("×")',
            'button:has-text("✕")',
            '.modal button[aria-label*="close"]',
            'dialog button[aria-label="close"]',
        ]

        # Try to close login modal or other overlays
        for selector in close_selectors:
            try:
                button = await self.page.query_selector(selector)
                if button:
                    is_visible = await button.is_visible()
                    if is_visible:
                        logger.info(f"Closing modal with selector: {selector}")
                        await button.click(timeout=3000)
                        await self.random_delay(0.5, 1.0)
                        dismissed_any = True
                        break
            except:
                continue

        # Also try pressing Escape key to close modals
        try:
            # Look for any modal/dialog overlay
            has_modal = await self.page.query_selector('.modal, dialog, [role="dialog"], .overlay')
            if has_modal:
                logger.info("Pressing Escape to close modal")
                await self.page.keyboard.press('Escape')
                await self.random_delay(0.5, 1.0)
                dismissed_any = True
        except:
            pass

        if dismissed_any:
            # Wait for overlays to disappear
            await self.random_delay(1.0, 1.5)

        return dismissed_any

    async def _get_job_description_from_page(self) -> Optional[str]:
        """
        Extract job description from a job detail page.
        Tries multiple selectors to handle different page layouts and obfuscated class names.
        """
        # First, dismiss any overlays that might be blocking the content
        await self._dismiss_overlays()

        # Try multiple selectors in order of preference
        selectors = [
            '[data-at="job-description"]',  # Standard selector
            '[data-genesis-element="TEXT"]',  # Obfuscated class names
            'span[data-genesis-element="TEXT"]',  # More specific
        ]

        # Also try by class pattern (job-ad-display-*)
        try:
            elements = await self.page.query_selector_all('[class*="job-ad-display"]')
            if elements:
                # Look for the largest text block (likely the description)
                largest_elem = None
                largest_text = ""
                for elem in elements:
                    text = await elem.inner_text()
                    if len(text) > len(largest_text):
                        largest_text = text
                        largest_elem = elem
                if largest_elem and len(largest_text) > 200:  # Reasonable description length
                    return largest_text
        except:
            pass

        # Try standard selectors
        for selector in selectors:
            try:
                elem = await self.page.query_selector(selector)
                if elem:
                    text = await elem.inner_text()
                    if text and len(text) > 50:  # Minimum reasonable description length
                        return text
            except:
                continue

        return None

    async def search_jobs(self,
                         search_term: str,
                         location: str = "London",
                         radius: int = 10,
                         employment_types: Optional[str] = None,
                         max_jobs: int = 100,
                         max_pages: int = 5,
                         detailed: bool = False,
                         save_incrementally: bool = True) -> List[JobListing]:
        """
        Search with option to fetch full job details.

        Args:
            search_term: Keywords to search for
            location: Location to search in
            radius: Search radius in miles (max 30)
            employment_types: Comma-separated employment types
            max_jobs: Maximum number of jobs to return
            max_pages: Maximum number of pages to scrape
            detailed: Whether to fetch full descriptions
            save_incrementally: If True, save each job to DB as it's scraped
        """
        # First get all basic listings with pagination (saves incrementally)
        jobs = await super().search_jobs(
            search_term=search_term,
            location=location,
            radius=radius,
            employment_types=employment_types,
            max_pages=max_pages,
            save_incrementally=save_incrementally
        )

        logger.info(f"Found {len(jobs)} jobs across all pages")

        if not detailed or len(jobs) > max_jobs:
            return jobs[:max_jobs]

        # Fetch detailed descriptions for subset using curl_cffi
        logger.info(f"Fetching detailed info for {min(len(jobs), max_jobs)} jobs using curl_cffi...")

        # Initialize the description fetcher with TLS impersonation
        fetcher = DescriptionFetcher(max_retries=3, timeout=30)
        detailed_jobs = []

        for i, job in enumerate(jobs[:max_jobs]):
            if not job.url:
                detailed_jobs.append(job)
                continue

            try:
                logger.info(f"[{i+1}/{min(len(jobs), max_jobs)}] Fetching: {job.title}")

                # Use curl_cffi to fetch the description
                description = fetcher.fetch_description(job.url)

                if description:
                    job.description = description
                    logger.info(f"Got description ({len(description)} chars)")
                else:
                    logger.warning(f"Could not extract description for {job.title}")

                detailed_jobs.append(job)

                # Small delay between requests
                import asyncio
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error fetching details for {job.title}: {e}")
                detailed_jobs.append(job)

        return detailed_jobs

    async def fetch_full_descriptions(self, jobs: List[JobListing], max_jobs: int = None) -> List[JobListing]:
        """
        Fetch full descriptions for a list of jobs using curl_cffi.

        Uses curl_cffi's browser TLS impersonation to bypass anti-bot protections
        that block Playwright/Selenium (like ERR_HTTP2_PROTOCOL_ERROR).

        Args:
            jobs: List of jobs to fetch descriptions for
            max_jobs: Maximum number of jobs to process (None = all)
        """
        if max_jobs:
            jobs = jobs[:max_jobs]

        logger.info(f"Fetching full descriptions for {len(jobs)} jobs using curl_cffi...")

        # Initialize the description fetcher with TLS impersonation
        fetcher = DescriptionFetcher(max_retries=3, timeout=30)

        for i, job in enumerate(jobs):
            if not job.url:
                logger.warning(f"Skipping {job.title} - no URL")
                continue

            try:
                logger.info(f"[{i+1}/{len(jobs)}] Fetching: {job.title}")

                # Use curl_cffi to fetch the description
                description = fetcher.fetch_description(job.url)

                if description:
                    job.description = description
                    logger.info(f"Updated description for {job.title} ({len(description)} chars)")
                else:
                    logger.warning(f"Could not extract description for {job.title}")

                # Small delay between requests (curl_cffi is fast, no need for long delays)
                import asyncio
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error fetching details for {job.title}: {e}")

        logger.info(f"Completed fetching descriptions for {len(jobs)} jobs")
        return jobs
