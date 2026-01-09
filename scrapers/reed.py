"""Reed.co.uk scraper with stealth mode."""

import logging
from typing import List, Optional
from urllib.parse import urlencode

from scrapers.base import BaseScraper
from database.schema import JobListing

logger = logging.getLogger('scrapers.reed')


class ReedScraper(BaseScraper):
    """Scraper for Reed.co.uk with anti-detection measures."""

    BASE_URL = "https://www.reed.co.uk"

    # Employment type mappings for Reed
    EMPLOYMENT_TYPES = {
        'permanent': 'permanent',
        'perm': 'permanent',
        'contract': 'contract',
        'temp': 'temp',
        'temporary': 'temp',
        'part-time': 'part-time',
        'part time': 'part-time',
    }

    def get_site_name(self) -> str:
        return "reed"

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
        Search for jobs on Reed with pagination support.

        Args:
            search_term: Keywords to search for
            location: Location to search in
            radius: Search radius in miles
            employment_types: Comma-separated employment types
            max_pages: Maximum number of pages to scrape
            save_incrementally: If True, save each job to DB as it's scraped
        """
        jobs = []
        stats = {'added': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

        # Build search URL using query parameters (more reliable than slug format)
        # https://www.reed.co.uk/jobs?keywords=python+developer&location=london&proximity=10
        params = {
            'keywords': search_term,
            'location': location,
            'proximity': radius,
        }

        logger.info(f"Searching Reed for '{search_term}' in {location}")

        # Load first page
        search_url = f"{self.BASE_URL}/jobs?{urlencode(params)}"
        if not await self.navigate_with_retry(search_url):
            logger.error(f"Failed to load {search_url}")
            return jobs

        for page_num in range(1, max_pages + 1):
            # Wait for job listings to load
            try:
                await self.page.wait_for_selector('article[data-qa="job-card"]', timeout=10000)
            except:
                logger.info(f"No more jobs found on page {page_num}")
                break

            # Extract job cards
            job_cards = await self.page.query_selector_all('article[data-qa="job-card"]')
            logger.info(f"Found {len(job_cards)} job cards on page {page_num}")

            if not job_cards:
                logger.info("No more job cards found, stopping pagination")
                break

            for card in job_cards:
                try:
                    job_data = await self._extract_job_data(card)
                    if job_data:
                        jobs.append(job_data)
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

            if save_incrementally:
                logger.info(f"Page {page_num} complete - Total: {len(jobs)} scraped, {stats['added']} added, {stats['skipped']} skipped")

            # Check for next page - Reed uses text-based "Next" link with pageno parameter
            # Try multiple approaches to find the next page link
            next_button = None

            # Method 1: Look for link containing "Next" text
            all_links = await self.page.query_selector_all('a')
            for link in all_links:
                text = await link.inner_text()
                if text.strip().lower() == 'next':
                    next_button = link
                    break

            # Method 2: Look for pagination links by data attributes
            if not next_button:
                next_button = await self.page.query_selector('a[data-qa="pagination-next"]')

            # Method 3: Look for link with pageno parameter for next page
            if not next_button:
                next_page_num = page_num + 1
                next_button = await self.page.query_selector(f'a[href*="pageno={next_page_num}"]')

            if not next_button:
                logger.info(f"No next page button found, stopping at page {page_num}")
                break

            # Navigate to next page
            logger.info(f"Navigating to page {page_num + 1}...")
            try:
                next_href = await next_button.get_attribute('href')
                if next_href:
                    if not next_href.startswith('http'):
                        next_href = f"{self.BASE_URL}{next_href}"
                    await self.page.goto(next_href, wait_until='domcontentloaded', timeout=15000)
                    await self.random_delay(1, 2)
                else:
                    await next_button.click()
                    await self.page.wait_for_load_state('domcontentloaded', timeout=10000)
            except Exception as e:
                logger.warning(f"Failed to navigate to page {page_num + 1}: {e}")
                break

        logger.info(f"Total jobs scraped from Reed: {len(jobs)}")
        if save_incrementally:
            logger.info(f"Final stats - Added: {stats['added']}, Updated: {stats['updated']}, Skipped: {stats['skipped']}")
        return jobs

    async def _extract_job_data(self, card) -> Optional[JobListing]:
        """Extract data from a Reed job card element."""
        scraped_at = self._get_timestamp()

        try:
            # Title and URL
            title_elem = await card.query_selector('h2 a, h3 a, [data-qa="job-card-title"] a')
            if not title_elem:
                return None

            title = await title_elem.inner_text()
            url = await title_elem.get_attribute('href')
            if url and not url.startswith('http'):
                url = f"{self.BASE_URL}{url}"

            # Company
            company_elem = await card.query_selector('[data-qa="job-card-company"], .job-card__company')
            company = await company_elem.inner_text() if company_elem else "Unknown"

            # Location
            location_elem = await card.query_selector('[data-qa="job-card-location"], .job-card__location')
            location = await location_elem.inner_text() if location_elem else "Unknown"

            # Salary
            salary_elem = await card.query_selector('[data-qa="job-card-salary"], .job-card__salary')
            salary = await salary_elem.inner_text() if salary_elem else None

            # Description/snippet
            desc_elem = await card.query_selector('[data-qa="job-card-description"], .job-card__description')
            description = await desc_elem.inner_text() if desc_elem else ""

            # Posted date
            posted_elem = await card.query_selector('[data-qa="job-card-posted-date"], .job-card__posted-by')
            posted_date = await posted_elem.inner_text() if posted_elem else None

            # Try to determine employment type from badges or text
            employment_type = None
            type_elem = await card.query_selector('[data-qa="job-card-contract-type"]')
            if type_elem:
                type_text = await type_elem.inner_text()
                type_lower = type_text.lower()
                if 'contract' in type_lower:
                    employment_type = 'contract'
                elif 'permanent' in type_lower or 'perm' in type_lower:
                    employment_type = 'permanent'
                elif 'temp' in type_lower:
                    employment_type = 'temporary'

            # Check for remote indicators
            if not employment_type:
                location_lower = location.lower() if location else ""
                if 'remote' in location_lower or 'home' in location_lower or 'wfh' in location_lower:
                    employment_type = 'WFH'

            return JobListing(
                title=title.strip(),
                company=company.strip(),
                location=location.strip(),
                description=description.strip(),
                salary=salary.strip() if salary else None,
                job_type=None,
                posted_date=posted_date.strip() if posted_date else None,
                url=url,
                source=self.get_site_name(),
                scraped_at=scraped_at,
                employment_type=employment_type
            )
        except Exception as e:
            logger.error(f"Error parsing Reed job card: {e}")
            return None

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
