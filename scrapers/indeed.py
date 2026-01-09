"""Indeed scraper with stealth mode."""

import logging
from typing import List, Optional
from urllib.parse import urlencode

from scrapers.base import BaseScraper
from database.schema import JobListing

logger = logging.getLogger('scrapers.indeed')


class IndeedScraper(BaseScraper):
    """Scraper for Indeed.co.uk with anti-detection measures.

    Note: Indeed has aggressive anti-bot measures. This scraper uses
    extra stealth techniques but may still get blocked occasionally.
    """

    BASE_URL = "https://uk.indeed.com"

    # Employment type mappings for Indeed
    EMPLOYMENT_TYPES = {
        'permanent': 'permanent',
        'perm': 'permanent',
        'contract': 'contract',
        'temp': 'temporary',
        'temporary': 'temporary',
        'part-time': 'parttime',
        'part time': 'parttime',
        'full-time': 'fulltime',
        'full time': 'fulltime',
    }

    def get_site_name(self) -> str:
        return "indeed"

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
        Search for jobs on Indeed with pagination support.

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

        # Build search URL
        # https://uk.indeed.com/jobs?q=python+developer&l=london&radius=10
        params = {
            'q': search_term,
            'l': location,
            'radius': radius,
            'sort': 'date',  # Sort by date to get newest first
        }

        # Add job type filter if specified
        if employment_types:
            for et in employment_types.split(','):
                normalized = self._normalize_employment_type(et.strip())
                if normalized:
                    params['jt'] = normalized
                    break

        logger.info(f"Searching Indeed with params: {params}")

        search_url = f"{self.BASE_URL}/jobs?{urlencode(params)}"
        if not await self.navigate_with_retry(search_url):
            logger.error(f"Failed to load {search_url}")
            return jobs

        for page_num in range(1, max_pages + 1):
            # Wait for job listings to load - Indeed uses various selectors
            try:
                await self.page.wait_for_selector('.job_seen_beacon, .jobsearch-ResultsList > li, [data-jk]', timeout=10000)
            except:
                logger.info(f"No more jobs found on page {page_num}")
                break

            # Add extra delay on Indeed to avoid detection
            await self.random_delay(1, 2)
            await self.human_like_scroll(2)

            # Extract job cards
            job_cards = await self.page.query_selector_all('.job_seen_beacon, [data-jk]')
            logger.info(f"Found {len(job_cards)} job cards on page {page_num}")

            if not job_cards:
                # Try alternate selector
                job_cards = await self.page.query_selector_all('.jobsearch-ResultsList > li')
                logger.info(f"Found {len(job_cards)} job cards using alternate selector")

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

            # Check for next page - Indeed uses various pagination selectors
            next_button = (
                await self.page.query_selector('a[data-testid="pagination-page-next"]') or
                await self.page.query_selector('a[aria-label="Next Page"]') or
                await self.page.query_selector('.np[data-pp]') or
                await self.page.query_selector('nav[aria-label="pagination"] a:last-child')
            )

            if not next_button:
                logger.info(f"No next page button found, stopping at page {page_num}")
                break

            # Check if disabled
            aria_disabled = await next_button.get_attribute('aria-disabled')
            if aria_disabled == 'true':
                logger.info(f"Next button is disabled, stopping at page {page_num}")
                break

            # Navigate to next page with extra care for Indeed
            logger.info(f"Navigating to page {page_num + 1}...")
            try:
                await self.random_delay(2, 4)  # Extra delay for Indeed

                next_href = await next_button.get_attribute('href')
                if next_href:
                    if not next_href.startswith('http'):
                        next_href = f"{self.BASE_URL}{next_href}"
                    await self.page.goto(next_href, wait_until='domcontentloaded', timeout=15000)
                else:
                    await next_button.click()
                    await self.page.wait_for_load_state('domcontentloaded', timeout=10000)

                await self.random_delay(1, 2)
            except Exception as e:
                logger.warning(f"Failed to navigate to page {page_num + 1}: {e}")
                break

        logger.info(f"Total jobs scraped from Indeed: {len(jobs)}")
        if save_incrementally:
            logger.info(f"Final stats - Added: {stats['added']}, Updated: {stats['updated']}, Skipped: {stats['skipped']}")
        return jobs

    async def _extract_job_data(self, card) -> Optional[JobListing]:
        """Extract data from an Indeed job card element."""
        scraped_at = self._get_timestamp()

        try:
            # Title and URL - Indeed uses various structures
            title_elem = (
                await card.query_selector('h2.jobTitle a') or
                await card.query_selector('.jobTitle a') or
                await card.query_selector('a[data-jk]') or
                await card.query_selector('h2 a')
            )
            if not title_elem:
                return None

            title = await title_elem.inner_text()
            url = await title_elem.get_attribute('href')
            if url and not url.startswith('http'):
                url = f"{self.BASE_URL}{url}"

            # Job key for Indeed-specific URL building
            job_key = await card.get_attribute('data-jk')
            if job_key and not url:
                url = f"{self.BASE_URL}/viewjob?jk={job_key}"

            # Company
            company_elem = (
                await card.query_selector('[data-testid="company-name"]') or
                await card.query_selector('.companyName') or
                await card.query_selector('.company')
            )
            company = await company_elem.inner_text() if company_elem else "Unknown"

            # Location
            location_elem = (
                await card.query_selector('[data-testid="text-location"]') or
                await card.query_selector('.companyLocation') or
                await card.query_selector('.location')
            )
            location = await location_elem.inner_text() if location_elem else "Unknown"

            # Salary - Indeed often hides this or puts it in metadata
            salary_elem = (
                await card.query_selector('[data-testid="attribute_snippet_testid"]') or
                await card.query_selector('.salary-snippet-container') or
                await card.query_selector('.metadata.salary-snippet-container')
            )
            salary = None
            if salary_elem:
                salary_text = await salary_elem.inner_text()
                # Check if it's actually a salary (contains £ or numbers)
                if '£' in salary_text or any(c.isdigit() for c in salary_text):
                    salary = salary_text

            # Description snippet
            desc_elem = (
                await card.query_selector('.job-snippet') or
                await card.query_selector('[data-testid="jobDescriptionText"]') or
                await card.query_selector('.jobCardShelfContainer')
            )
            description = await desc_elem.inner_text() if desc_elem else ""

            # Posted date
            posted_elem = (
                await card.query_selector('.date') or
                await card.query_selector('[data-testid="myJobsStateDate"]') or
                await card.query_selector('.job-snippet .date')
            )
            posted_date = await posted_elem.inner_text() if posted_elem else None

            # Employment type from metadata
            employment_type = None
            metadata_elems = await card.query_selector_all('.metadata div, .jobMetaDataGroup')
            for meta in metadata_elems:
                meta_text = await meta.inner_text()
                meta_lower = meta_text.lower()
                if 'contract' in meta_lower:
                    employment_type = 'contract'
                    break
                elif 'permanent' in meta_lower:
                    employment_type = 'permanent'
                    break
                elif 'temporary' in meta_lower or 'temp' in meta_lower:
                    employment_type = 'temporary'
                    break

            # Check for remote indicators
            if not employment_type:
                location_lower = location.lower() if location else ""
                if 'remote' in location_lower or 'home' in location_lower or 'hybrid' in location_lower:
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
            logger.error(f"Error parsing Indeed job card: {e}")
            return None

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
