#!/usr/bin/env python3
"""CLI for job analysis utilities."""

import argparse
import asyncio
from database.schema import JobDatabase
from utils.analysis import JobAnalyzer


def main():
    parser = argparse.ArgumentParser(description="Analyze job listings")
    parser.add_argument('--db', type=str, default='jobs.db', help='Database path')
    parser.add_argument('--stats', action='store_true', help='Show database stats')
    parser.add_argument('--top-companies', action='store_true', help='Show top companies')
    parser.add_argument('--salary', action='store_true', help='Show jobs with salary info')
    parser.add_argument('--keywords', '--trends', action='store_true', help='Show keyword trends')
    parser.add_argument('--remote', action='store_true', help='Show remote vs onsite stats')
    parser.add_argument('--pipeline', action='store_true', help='Show application pipeline')
    parser.add_argument('--rank', action='store_true', help='Rank jobs by skill match')
    parser.add_argument('--skills', type=str, help='Comma-separated skills for ranking (e.g., "azure,kubernetes,terraform")')
    parser.add_argument('--export', type=str, help='Export jobs to JSON file')

    args = parser.parse_args()

    db = JobDatabase(args.db)
    analyzer = JobAnalyzer(db)

    if args.stats:
        stats = db.get_stats()
        print("\nDATABASE STATS:")
        for k, v in stats.items():
            print(f"  {k}: {v}")

    elif args.top_companies:
        print("\nTOP COMPANIES:")
        for i, (company, count) in enumerate(analyzer.top_companies(20), 1):
            print(f"  {i}. {company}: {count} jobs")

    elif args.salary:
        jobs = analyzer.find_salary_info()
        print(f"\nJOBS WITH SALARY INFO: {len(jobs)}")
        for i, job in enumerate(jobs[:30], 1):
            print(f"  {i}. {job['title']} at {job['company']}")
            print(f"     Salary: {job['salary']} | Location: {job['location']}")

    elif args.keywords or args.trends:
        trends = analyzer.keyword_trends()
        print("\nKEYWORD TRENDS:")
        for kw, count in trends.items():
            print(f"  {kw}: {count} mentions")

    elif args.remote:
        stats = analyzer.remote_vs_onsite()
        print("\nREMOTE VS ONSITE:")
        for k, v in stats.items():
            print(f"  {k}: {v}")

    elif args.pipeline:
        analyzer.show_applications_pipeline()

    elif args.rank and args.skills:
        skills = [s.strip() for s in args.skills.split(',')]
        ranked = analyzer.rank_by_fit(skills)

        print(f"\nJOBS RANKED BY FIT (skills: {', '.join(skills)})")
        for i, job in enumerate(ranked[:20], 1):
            print(f"\n  {i}. {job['title']} at {job['company']} - Match: {job['match_score']}%")
            print(f"     Location: {job['location']} | Source: {job['source']}")
            print(f"     URL: {job['url']}")

    elif args.export:
        analyzer.export_for_analysis(args.export)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
