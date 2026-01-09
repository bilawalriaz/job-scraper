"""TotalJobs scraper with stealth mode."""

import re
from typing import List
from urllib.parse import urlencode

from scrapers.base import BaseScraper
from database.schema import JobListing


class TotalJobsScraper(BaseScraper):
    """Scraper for TotalJobs.co.uk with anti-detection measures."""

    BASE_URL = "https://www.totaljobs.com"

    def get_site_name(self) -> str:
        return "totaljobs"

    async def search_jobs(self, search_term: str, location: str = "London") -> List[JobListing]:
        """Search for jobs on TotalJobs."""
        jobs = []

        # Build search URL
        params = {
            'q': search_term,
            'l': location,
            'radius': 10,  # 10 miles
            's': '1',  # sort by relevance
        }
        search_url = f"{self.BASE_URL}/jobs?{urlencode(params)}"

        if not await self.navigate_with_retry(search_url):
            print(f"Failed to load {search_url}")
            return jobs

        # Wait for job listings to load - updated selector
        await self.page.wait_for_selector('[data-at="job-item"]', timeout=10000)

        # Extract job cards - updated selector
        job_cards = await self.page.query_selector_all('[data-at="job-item"]')
        print(f"[*] Found {len(job_cards)} job cards on page")

        for card in job_cards:
            try:
                job_data = await self._extract_job_data(card)
                if job_data:
                    jobs.append(job_data)
            except Exception as e:
                print(f"Error extracting job: {e}")
                continue

        return jobs

    async def _extract_job_data(self, card) -> JobListing:
        """Extract data from a job card element."""
        scraped_at = self._get_timestamp()

        # Title and URL - Updated to use data-at attributes
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

        # Job type - Not always present
        type_elem = await card.query_selector('[data-at="job-item-job-type"]')
        job_type = await type_elem.inner_text() if type_elem else None

        # Posted date
        posted_elem = await card.query_selector('[data-at="job-item-timeago"]')
        posted_date = await posted_elem.inner_text() if posted_elem else None

        # Description - Try multiple selectors for description
        desc_elem = await card.query_selector('[data-at="jobcard-content"]')
        description = await desc_elem.inner_text() if desc_elem else ""

        # Clean up description (remove excess whitespace)
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
            scraped_at=scraped_at
        )

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat()


class TotalJobsDetailedScraper(TotalJobsScraper):
    """Enhanced scraper that navigates to each job page for full details."""

    async def search_jobs(self, search_term: str, location: str = "London",
                         max_jobs: int = 50, detailed: bool = False) -> List[JobListing]:
        """Search with option to fetch full job details."""
        # First get basic listings
        jobs = await super().search_jobs(search_term, location)

        if not detailed or len(jobs) > max_jobs:
            return jobs[:max_jobs]

        # Fetch detailed descriptions for subset
        print(f"[*] Fetching detailed info for {min(len(jobs), max_jobs)} jobs...")
        detailed_jobs = []

        for i, job in enumerate(jobs[:max_jobs]):
            if not job.url:
                detailed_jobs.append(job)
                continue

            try:
                print(f"  [{i+1}/{min(len(jobs), max_jobs)}] Fetching: {job.title}")

                if await self.navigate_with_retry(job.url):
                    # Wait for job detail content - updated selector
                    await self.page.wait_for_selector('[data-at="job-description"]', timeout=8000)

                    # Get full description - updated selector
                    desc_elem = await self.page.query_selector('[data-at="job-description"]')
                    if desc_elem:
                        job.description = await desc_elem.inner_text()

                    detailed_jobs.append(job)
                    await self.random_delay(2, 4)  # Respectful delay

            except Exception as e:
                print(f"    Error fetching details: {e}")
                detailed_jobs.append(job)  # Keep what we have

        return detailed_jobs
