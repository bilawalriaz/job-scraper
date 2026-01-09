"""TotalJobs scraper with stealth mode."""

import re
import logging
from typing import List, Optional
from urllib.parse import urlencode

from scrapers.base import BaseScraper
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
                         max_pages: int = 5) -> List[JobListing]:
        """
        Search for jobs on TotalJobs with pagination support.

        Args:
            search_term: Keywords to search for
            location: Location to search in
            radius: Search radius in miles (max 30)
            employment_types: Comma-separated employment types (e.g., "contract,permanent,whf")
            max_pages: Maximum number of pages to scrape
        """
        jobs = []

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
                except Exception as e:
                    logger.error(f"Error extracting job: {e}")
                    continue

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

    async def search_jobs(self,
                         search_term: str,
                         location: str = "London",
                         radius: int = 10,
                         employment_types: Optional[str] = None,
                         max_jobs: int = 100,
                         max_pages: int = 5,
                         detailed: bool = False) -> List[JobListing]:
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
        """
        # First get all basic listings with pagination
        jobs = await super().search_jobs(
            search_term=search_term,
            location=location,
            radius=radius,
            employment_types=employment_types,
            max_pages=max_pages
        )

        logger.info(f"Found {len(jobs)} jobs across all pages")

        if not detailed or len(jobs) > max_jobs:
            return jobs[:max_jobs]

        # Fetch detailed descriptions for subset
        logger.info(f"Fetching detailed info for {min(len(jobs), max_jobs)} jobs...")
        detailed_jobs = []

        for i, job in enumerate(jobs[:max_jobs]):
            if not job.url:
                detailed_jobs.append(job)
                continue

            try:
                logger.info(f"[{i+1}/{min(len(jobs), max_jobs)}] Fetching: {job.title}")

                if await self.navigate_with_retry(job.url):
                    await self.page.wait_for_selector('[data-at="job-description"]', timeout=8000)

                    desc_elem = await self.page.query_selector('[data-at="job-description"]')
                    if desc_elem:
                        job.description = await desc_elem.inner_text()

                    detailed_jobs.append(job)
                    await self.random_delay(2, 4)

            except Exception as e:
                logger.error(f"Error fetching details for {job.title}: {e}")
                detailed_jobs.append(job)

        return detailed_jobs

    async def fetch_full_descriptions(self, jobs: List[JobListing], max_jobs: int = None) -> List[JobListing]:
        """
        Fetch full descriptions for a list of jobs.
        Useful for second-pass scraping after deduplication.

        Args:
            jobs: List of jobs to fetch descriptions for
            max_jobs: Maximum number of jobs to process (None = all)
        """
        if max_jobs:
            jobs = jobs[:max_jobs]

        logger.info(f"Fetching full descriptions for {len(jobs)} jobs...")

        for i, job in enumerate(jobs):
            if not job.url:
                logger.warning(f"Skipping {job.title} - no URL")
                continue

            try:
                logger.info(f"[{i+1}/{len(jobs)}] Fetching: {job.title}")

                if await self.navigate_with_retry(job.url):
                    await self.page.wait_for_selector('[data-at="job-description"]', timeout=8000)

                    desc_elem = await self.page.query_selector('[data-at="job-description"]')
                    if desc_elem:
                        job.description = await desc_elem.inner_text()
                        logger.info(f"Updated description for {job.title} ({len(job.description)} chars)")
                    else:
                        logger.warning(f"No description element found for {job.title}")

                    await self.random_delay(1, 2)  # Shorter delay for second pass

            except Exception as e:
                logger.error(f"Error fetching details for {job.title}: {e}")

        logger.info(f"Completed fetching descriptions for {len(jobs)} jobs")
        return jobs
