# curl_cffi Integration for Full Job Descriptions

## Overview

This document describes the integration of `curl_cffi` to bypass TLS fingerprinting protections on job sites like TotalJobs.

## Problem

Job sites like TotalJobs use TLS/SSL fingerprinting to detect and block automated browsers, returning `ERR_HTTP2_PROTOCOL_ERROR` even with stealth modes in Playwright/Selenium.

## Solution

**curl_cffi** is a Python library that can impersonate real browser TLS fingerprints, allowing it to bypass these protections at the network protocol level.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Job Scraper Flow                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Search Results (Playwright)                             │
│     ├─ Works fine for search pages                          │
│     └─ Gets: title, company, location, salary, short desc   │
│                                                             │
│  2. Full Descriptions (curl_cffi)                           │
│     ├─ Uses browser TLS impersonation                       │
│     ├─ Bypasses ERR_HTTP2_PROTOCOL_ERROR                    │
│     └─ Gets: Full job description text                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Components

### DescriptionFetcher (`scrapers/description_fetcher.py`)

Handles fetching full job descriptions using curl_cffi's browser impersonation.

```python
from scrapers.description_fetcher import DescriptionFetcher

fetcher = DescriptionFetcher(max_retries=3, timeout=30)
description = fetcher.fetch_description(job_url)
```

**Features:**
- Tries multiple browser fingerprints (chrome, chrome120, chrome110, edge)
- Parses HTML with BeautifulSoup
- Handles various page layouts with multiple selectors
- Returns None on failure (graceful degradation)

### TotalJobsDetailedScraper (`scrapers/totaljobs.py`)

Enhanced scraper that uses curl_cffi for fetching full descriptions.

```python
from scrapers.totaljobs import TotalJobsDetailedScraper

scraper = TotalJobsDetailedScraper(db, headless=True)

# Method 1: Search with detailed mode
jobs = await scraper.search_jobs(
    search_term="devops",
    location="London",
    detailed=True  # Fetches full descriptions with curl_cffi
)

# Method 2: Fetch descriptions for existing jobs
jobs = await scraper.fetch_full_descriptions(jobs, max_jobs=10)
```

## Browser Impersonation

curl_cffi mimics real browser TLS fingerprints:
- **Chrome** (default)
- **Chrome 110**
- **Chrome 120**
- **Edge**
- **Safari**

The fetcher tries each browser type until one succeeds.

## Dependencies

Added to `requirements.txt`:
```
curl_cffi>=0.14.0
beautifulsoup4>=4.9.0
lxml>=4.9.0
```

## Usage Examples

### Example 1: Fetch Full Descriptions After Scraping

```python
import asyncio
from scrapers.totaljobs import TotalJobsDetailedScraper
from database.schema import JobDatabase

async def main():
    db = JobDatabase()
    scraper = TotalJobsDetailedScraper(db, headless=True)

    # Scrape jobs (basic descriptions from search results)
    await scraper.init_browser()
    jobs = await scraper.search_jobs("devops", "London", max_pages=2)
    await scraper.cleanup()

    # Fetch full descriptions for scraped jobs
    jobs = await scraper.fetch_full_descriptions(jobs)

    # Save to database
    for job in jobs:
        db.update_job_description(job.id, job.description)

asyncio.run(main())
```

### Example 2: Update Existing Jobs in Database

```python
import asyncio
from scrapers.totaljobs import TotalJobsDetailedScraper
from database.schema import JobDatabase

async def main():
    db = JobDatabase()
    scraper = TotalJobsDetailedScraper(db, headless=True)

    # Get jobs that need full descriptions
    jobs = db.get_jobs_needing_descriptions(limit=20, source="totaljobs")

    # Fetch full descriptions
    jobs = await scraper.fetch_full_descriptions(jobs)

    # Update database
    for job in jobs:
        if job.description:
            db.update_job_description(job.id, job.description)

asyncio.run(main())
```

## Performance

- **Speed**: Much faster than browser automation (no browser overhead)
- **Reliability**: Successfully bypasses TLS fingerprinting on TotalJobs
- **Rate Limiting**: Uses 0.5s delay between requests (configurable)

## Testing

Run the integration test:

```bash
python3 test_full_integration.py
```

Expected output:
```
[Test 1] Testing DescriptionFetcher standalone... PASS ✓
[Test 2] Testing database integration...          PASS ✓
[Test 3] Testing scraper integration...            PASS ✓
```

## Troubleshooting

### "No module named 'curl_cffi'"
Install dependencies:
```bash
pip install -r requirements.txt
```

### "Failed to fetch description"
- Check if the URL is accessible in a browser
- The site may have changed its HTML structure
- Try increasing `timeout` in `DescriptionFetcher`

### "ERR_HTTP2_PROTOCOL_ERROR"
This shouldn't happen with curl_cffi. If it does:
- Verify curl_cffi is installed correctly
- Check if the site has changed its protection
- Try different browser types in `BROWSER_TYPES`

## Future Enhancements

- Add support for other job boards (Indeed, Reed, etc.)
- Implement caching to avoid re-fetching descriptions
- Add retry logic with exponential backoff
- Support for residential proxies if needed

## References

- curl_cffi: https://github.com/yifeikong/curl_cffi
- TotalJobs: https://www.totaljobs.com
