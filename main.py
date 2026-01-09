#!/usr/bin/env python3
"""Main orchestrator for parallel job scraping across multiple sites."""

import asyncio
import argparse
from typing import List, Dict
from database.schema import JobDatabase
from scrapers.totaljobs import TotalJobsDetailedScraper


# Search configurations
DEFAULT_SEARCHES = [
]


class JobScraperOrchestrator:
    """Orchestrates parallel scraping across multiple job sites."""

    def __init__(self, db_path: str = "jobs.db"):
        self.db = JobDatabase(db_path)
        self.scrapers = []

    async def scrape_all(self, searches: List[Dict], headless: bool = True,
                         detailed: bool = False) -> Dict[str, int]:
        """Run all scrapers in parallel for all searches."""
        results = {}

        # For now, just TotalJobs
        # Add more scrapers here as they're implemented (Indeed, Reed, etc.)
        for search in searches:
            scraper = TotalJobsDetailedScraper(self.db, headless=headless)

            try:
                count = await scraper.scrape_and_store(
                    search_term=search['term'],
                    location=search['location']
                )

                key = f"{search['term']} in {search['location']}"
                results[key] = count

            except Exception as e:
                print(f"Error scraping {search}: {e}")
                results[f"{search['term']}"] = 0

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
    parser.add_argument('--headless', action='store_true', default=True, help='Run headless')
    parser.add_argument('--visible', action='store_false', dest='headless', help='Run visible (for debugging)')
    parser.add_argument('--detailed', action='store_true', help='Fetch full job details (slower)')
    parser.add_argument('--stats', action='store_true', help='Show database stats only')
    parser.add_argument('--db', type=str, default='jobs.db', help='Database path')

    args = parser.parse_args()

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

    results = await orchestrator.scrape_all(
        searches=searches,
        headless=args.headless,
        detailed=args.detailed
    )

    orchestrator.print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
