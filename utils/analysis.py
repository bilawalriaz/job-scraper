#!/usr/bin/env python3
"""Analysis utilities for job data."""

import json
from typing import List, Dict
from collections import Counter
from database.schema import JobDatabase


class JobAnalyzer:
    """Analyze job listings for insights."""

    def __init__(self, db: JobDatabase):
        self.db = db

    def find_salary_info(self, location: str = None) -> List[Dict]:
        """Find jobs with salary information."""
        filters = {}
        if location:
            filters['location'] = location

        jobs = self.db.get_jobs(filters, limit=500)
        return [j for j in jobs if j.get('salary')]

    def top_companies(self, limit: int = 20) -> List[tuple]:
        """Get companies with most job postings."""
        jobs = self.db.get_jobs(limit=1000)
        companies = [j['company'] for j in jobs]
        return Counter(companies).most_common(limit)

    def keyword_trends(self, keyword: str = None) -> Dict:
        """Find trending skills/keywords in descriptions."""
        if keyword:
            jobs = self.db.search_description(keyword)
        else:
            jobs = self.db.get_jobs(limit=500)

        # Extract potential skill keywords
        tech_keywords = [
            'python', 'azure', 'aws', 'kubernetes', 'docker', 'terraform',
            'ansible', 'jenkins', 'gitlab', 'ci/cd', 'github', 'linux',
            'sql', 'postgres', 'redis', 'elasticsearch', 'grafana',
            'prometheus', 'helm', 'argocd', 'vault', 'consul',
            'microservices', 'serverless', 'iac', 'cicd'
        ]

        keyword_counts = Counter()
        for job in jobs:
            desc = job.get('description', '').lower()
            for kw in tech_keywords:
                if kw in desc:
                    keyword_counts[kw] += 1

        return dict(keyword_counts.most_common(20))

    def remote_vs_onsite(self) -> Dict:
        """Compare remote vs onsite jobs."""
        jobs = self.db.get_jobs(limit=500)

        remote = [j for j in jobs if 'remote' in j.get('location', '').lower() or
                  'remote' in j.get('description', '').lower()]

        return {
            'total': len(jobs),
            'remote': len(remote),
            'onsite': len(jobs) - len(remote),
            'remote_percentage': round(len(remote) / len(jobs) * 100, 1) if jobs else 0
        }

    def export_for_analysis(self, output_file: str = "jobs_export.json"):
        """Export all jobs to JSON for external analysis."""
        jobs = self.db.get_jobs(limit=5000)

        with open(output_file, 'w') as f:
            json.dump(jobs, f, indent=2)

        print(f"Exported {len(jobs)} jobs to {output_file}")

    def show_applications_pipeline(self):
        """Show jobs in application pipeline (not yet applied)."""
        jobs = self.db.get_jobs({'is_applied': False}, limit=100)

        print(f"\n{'='*60}")
        print(f"APPLICATION PIPELINE - {len(jobs)} jobs to review")
        print(f"{'='*60}\n")

        for i, job in enumerate(jobs[:20], 1):
            print(f"{i}. {job['title']} at {job['company']}")
            print(f"   Location: {job['location']} | Source: {job['source']}")
            if job['salary']:
                print(f"   Salary: {job['salary']}")
            print(f"   URL: {job['url']}")
            print()

    def match_score(self, job: Dict, required_skills: List[str]) -> float:
        """Calculate match score based on skill requirements."""
        desc = job.get('description', '').lower()
        title = job.get('title', '').lower()

        matches = sum(1 for skill in required_skills if skill.lower() in desc or skill.lower() in title)
        return round(matches / len(required_skills) * 100, 1) if required_skills else 0

    def rank_by_fit(self, required_skills: List[str], limit: int = 50) -> List[Dict]:
        """Rank jobs by how well they match required skills."""
        jobs = self.db.get_jobs({'is_applied': False}, limit=limit)

        ranked = []
        for job in jobs:
            score = self.match_score(job, required_skills)
            if score > 0:
                job['match_score'] = score
                ranked.append(job)

        return sorted(ranked, key=lambda x: x['match_score'], reverse=True)
