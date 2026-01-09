#!/usr/bin/env python3
"""Main orchestrator for parallel job scraping across multiple sites."""

import asyncio
import argparse
from typing import List, Dict, Optional
from database.schema import JobDatabase
from scrapers.totaljobs import TotalJobsDetailedScraper
from scrapers.reed import ReedScraper
from scrapers.indeed import IndeedScraper
from scrapers.cvlibrary import CVLibraryScraper


# Available scrapers
AVAILABLE_SCRAPERS = {
    'totaljobs': TotalJobsDetailedScraper,
    'reed': ReedScraper,
    'indeed': IndeedScraper,
    'cvlibrary': CVLibraryScraper,
}

# Search configurations
DEFAULT_SEARCHES = [
]


class JobScraperOrchestrator:
    """Orchestrates parallel scraping across multiple job sites."""

    def __init__(self, db_path: str = "jobs.db"):
        self.db = JobDatabase(db_path)

    async def scrape_source(self, source_name: str, search: Dict, headless: bool = True) -> Dict:
        """Scrape a single source for a single search."""
        if source_name not in AVAILABLE_SCRAPERS:
            return {'source': source_name, 'error': f'Unknown source: {source_name}'}

        scraper_class = AVAILABLE_SCRAPERS[source_name]
        scraper = scraper_class(self.db, headless=headless)
        result = {'source': source_name, 'search': f"{search['term']} in {search['location']}", 'found': 0}

        try:
            await scraper.init_browser()
            jobs = await scraper.search_jobs(
                search_term=search['term'],
                location=search['location'],
                save_incrementally=True
            )
            result['found'] = len(jobs)
        except Exception as e:
            result['error'] = str(e)
            print(f"[{source_name}] Error: {e}")
        finally:
            await scraper.cleanup()

        return result

    async def scrape_all(self, searches: List[Dict], headless: bool = True,
                         sources: Optional[List[str]] = None) -> Dict[str, int]:
        """Run scrapers in parallel for all searches."""
        results = {}

        # Use specified sources or all available
        active_sources = sources if sources else list(AVAILABLE_SCRAPERS.keys())

        # Filter to valid sources
        active_sources = [s for s in active_sources if s in AVAILABLE_SCRAPERS]

        if not active_sources:
            print("No valid sources specified")
            return results

        print(f"Scraping from: {', '.join(active_sources)}")

        # Create tasks for all source/search combinations
        tasks = []
        for search in searches:
            for source in active_sources:
                tasks.append(self.scrape_source(source, search, headless))

        # Run all tasks in parallel
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        for task_result in task_results:
            if isinstance(task_result, Exception):
                print(f"Task failed: {task_result}")
                continue
            if isinstance(task_result, dict):
                key = f"[{task_result['source']}] {task_result.get('search', 'unknown')}"
                results[key] = task_result.get('found', 0)
                if 'error' in task_result:
                    results[key] = f"Error: {task_result['error']}"

        return results

    def print_results(self, results: Dict[str, int]):
        """Print scraping results."""
        print("\n" + "="*60)
        print("SCRAPING RESULTS")
        print("="*60)

        for search, count in results.items():
            print(f"  {search}: {count} new jobs")

        stats = self.db.get_stats()
        print("\nDATABASE STATS:")
        print(f"  Total jobs: {stats['total']}")
        print(f"  Sources: {stats['sources']}")
        print(f"  Companies: {stats['companies']}")
        print(f"  Applied: {stats['applied']}")
        print("="*60 + "\n")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Job Scraper Automation")
    parser.add_argument('--search', type=str, help='Search term (default: use preset searches)')
    parser.add_argument('--location', type=str, default='London', help='Job location')
    parser.add_argument('--sources', type=str, help='Comma-separated list of sources (e.g., reed,totaljobs). Available: ' + ', '.join(AVAILABLE_SCRAPERS.keys()))
    parser.add_argument('--headless', action='store_true', default=True, help='Run headless')
    parser.add_argument('--visible', action='store_false', dest='headless', help='Run visible (for debugging)')
    parser.add_argument('--detailed', action='store_true', help='Fetch full job details (slower)')
    parser.add_argument('--stats', action='store_true', help='Show database stats only')
    parser.add_argument('--db', type=str, default='jobs.db', help='Database path')
    parser.add_argument('--list-sources', action='store_true', help='List available sources')

    args = parser.parse_args()

    # List sources mode
    if args.list_sources:
        print("\nAvailable sources:")
        for source in AVAILABLE_SCRAPERS.keys():
            print(f"  - {source}")
        return

    orchestrator = JobScraperOrchestrator(db_path=args.db)

    # Stats only mode
    if args.stats:
        stats = orchestrator.db.get_stats()
        print("\nDATABASE STATS:")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        return

    # Single search mode
    if args.search:
        searches = [{'term': args.search, 'location': args.location}]
    # Default searches mode
    else:
        searches = DEFAULT_SEARCHES

    if not searches:
        print("No searches specified. Use --search 'term' or add to DEFAULT_SEARCHES")
        return

    # Parse sources
    sources = None
    if args.sources:
        sources = [s.strip().lower() for s in args.sources.split(',')]

    results = await orchestrator.scrape_all(
        searches=searches,
        headless=args.headless,
        sources=sources
    )

    orchestrator.print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
