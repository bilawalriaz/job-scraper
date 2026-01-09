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
        'whf': 'whf',
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

        # Paginate through results
        for page_num in range(1, max_pages + 1):
            params['page'] = page_num
            search_url = f"{self.BASE_URL}/jobs?{urlencode(params)}"

            if page_num == 1:
                if not await self.navigate_with_retry(search_url):
                    logger.error(f"Failed to load {search_url}")
                    return jobs
            else:
                # For subsequent pages, navigate directly
                try:
                    await self.page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                    await self.random_delay(1, 2)
                except Exception as e:
                    logger.warning(f"Failed to load page {page_num}: {e}")
                    break

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

            # Check if there's a next page
            next_button = await self.page.query_selector('[data-at="pagination-next"]')
            if not next_button or await next_button.is_disabled():
                logger.info(f"No more pages available after page {page_num}")
                break

            logger.info(f"Scraped {len(jobs)} jobs so far, moving to next page...")

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
