"""Database schema and operations for job scraper."""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from difflib import SequenceMatcher
import re


@dataclass
class JobListing:
    """Represents a job listing from any source."""
    title: str
    company: str
    location: str
    description: str
    salary: Optional[str] = None
    job_type: Optional[str] = None  # full-time, contract, part-time, temporary
    posted_date: Optional[str] = None
    url: str = ""
    source: str = ""  # totaljobs, indeed, etc.
    scraped_at: str = ""
    employment_type: Optional[str] = None  # permanent, contract, WHF (work from home)

    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'description': self.description,
            'salary': self.salary,
            'job_type': self.job_type,
            'posted_date': self.posted_date,
            'url': self.url,
            'source': self.source,
            'scraped_at': self.scraped_at,
            'employment_type': self.employment_type
        }


@dataclass
class SearchConfig:
    """Search configuration for automated scraping."""
    id: Optional[int] = None
    name: str = ""
    keywords: str = ""
    location: str = ""
    radius: int = 10
    employment_types: str = ""  # comma-separated: permanent,contract,whf
    enabled: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict:
        d = asdict(self)
        if self.id is None:
            d.pop('id', None)
        # Exclude timestamps from output dict
        d.pop('created_at', None)
        d.pop('updated_at', None)
        return d


class JobDatabase:
    """SQLite database for storing and analyzing job listings."""

    def __init__(self, db_path: str = "jobs.db"):
        self.db_path = db_path
        self.conn = None
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.conn = sqlite3.connect(self.db_path, timeout=30.0)
        self.conn.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrent access
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("PRAGMA foreign_keys=ON")

        # Jobs table with edit tracking
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                salary TEXT,
                job_type TEXT,
                posted_date TEXT,
                url TEXT,
                source TEXT NOT NULL,
                scraped_at TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_applied BOOLEAN DEFAULT 0,
                is_edited BOOLEAN DEFAULT 0,
                employment_type TEXT,
                notes TEXT,
                status TEXT DEFAULT 'new',
                UNIQUE(company, title, location)
            )
        """)

        # Search configs table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS search_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                keywords TEXT NOT NULL,
                location TEXT NOT NULL,
                radius INTEGER DEFAULT 10,
                employment_types TEXT DEFAULT '',
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Scraping log for rate limiting
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS scrape_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                search_config_id INTEGER,
                jobs_found INTEGER DEFAULT 0,
                jobs_added INTEGER DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                success BOOLEAN DEFAULT 1,
                error_message TEXT
            )
        """)

        # Indexes for performance
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON jobs(source);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_location ON jobs(location);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_company ON jobs(company);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_employment_type ON jobs(employment_type);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_scraped_at ON jobs(scraped_at DESC);")

        self.conn.commit()

        # Create default search configurations
        self._create_default_configs()

    def _create_default_configs(self):
        """Create default search configurations if they don't exist."""
        default_configs = [
            # Remote searches (contract, permanent, WFH)
            {'name': 'Python AI - Remote', 'keywords': 'python ai', 'location': 'Remote', 'radius': 0, 'employment_types': 'contract,permanent,wfh'},
            {'name': 'Azure AI - Remote', 'keywords': 'azure ai', 'location': 'Remote', 'radius': 0, 'employment_types': 'contract,permanent,wfh'},
            {'name': 'Azure DevOps - Remote', 'keywords': 'azure devops', 'location': 'Remote', 'radius': 0, 'employment_types': 'contract,permanent,wfh'},
            {'name': 'Python DevOps - Remote', 'keywords': 'python devops', 'location': 'Remote', 'radius': 0, 'employment_types': 'contract,permanent,wfh'},
            {'name': 'AI DevOps - Remote', 'keywords': 'ai devops', 'location': 'Remote', 'radius': 0, 'employment_types': 'contract,permanent,wfh'},
            # Manchester searches (contract, permanent only, 10 miles)
            {'name': 'Python AI - Manchester', 'keywords': 'python ai', 'location': 'Manchester', 'radius': 10, 'employment_types': 'contract,permanent'},
            {'name': 'Azure AI - Manchester', 'keywords': 'azure ai', 'location': 'Manchester', 'radius': 10, 'employment_types': 'contract,permanent'},
            {'name': 'Azure DevOps - Manchester', 'keywords': 'azure devops', 'location': 'Manchester', 'radius': 10, 'employment_types': 'contract,permanent'},
            {'name': 'Python DevOps - Manchester', 'keywords': 'python devops', 'location': 'Manchester', 'radius': 10, 'employment_types': 'contract,permanent'},
            {'name': 'AI DevOps - Manchester', 'keywords': 'ai devops', 'location': 'Manchester', 'radius': 10, 'employment_types': 'contract,permanent'},
        ]

        for config_data in default_configs:
            # Use INSERT OR IGNORE to atomically handle duplicates
            self.conn.execute("""
                INSERT OR IGNORE INTO search_configs (name, keywords, location, radius, employment_types, enabled)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (
                config_data['name'],
                config_data['keywords'],
                config_data['location'],
                config_data['radius'],
                config_data['employment_types']
            ))

        self.conn.commit()

    def _similarity_score(self, str1: str, str2: str) -> float:
        """Calculate string similarity score (0-1)."""
        # Normalize strings
        s1 = re.sub(r'[^\w\s]', '', str1.lower())
        s2 = re.sub(r'[^\w\s]', '', str2.lower())
        return SequenceMatcher(None, s1, s2).ratio()

    def _find_duplicate(self, job: JobListing) -> Optional[Dict]:
        """Find potential duplicate based on company + title + location."""
        cursor = self.conn.execute("""
            SELECT id, title, company, location, is_edited
            FROM jobs
            WHERE company = ? AND location = ?
        """, (job.company, job.location))

        for row in cursor.fetchall():
            row_dict = dict(row)
            title_similarity = self._similarity_score(job.title, row_dict['title'])
            if title_similarity > 0.85:  # High similarity threshold
                return row_dict
        return None

    def insert_job(self, job: JobListing) -> Tuple[bool, str]:
        """
        Insert a job listing with smart deduplication.
        Returns (success: bool, message: str).
        """
        try:
            # Check for existing edited duplicate
            duplicate = self._find_duplicate(job)

            if duplicate:
                if duplicate['is_edited']:
                    # Don't overwrite user-edited entries
                    return False, "Skipped (duplicate of edited entry)"
                else:
                    # Update existing unedited entry
                    self.conn.execute("""
                        UPDATE jobs SET
                            title = ?,
                            description = ?,
                            salary = ?,
                            job_type = ?,
                            posted_date = ?,
                            url = ?,
                            source = ?,
                            scraped_at = ?,
                            updated_at = CURRENT_TIMESTAMP,
                            employment_type = ?
                        WHERE id = ?
                    """, (
                        job.title, job.description, job.salary, job.job_type,
                        job.posted_date, job.url, job.source, job.scraped_at,
                        job.employment_type, duplicate['id']
                    ))
                    self.conn.commit()
                    return True, "Updated existing duplicate"

            # No duplicate found, insert new
            self.conn.execute("""
                INSERT OR IGNORE INTO jobs
                (title, company, location, description, salary, job_type,
                 posted_date, url, source, scraped_at, employment_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.title, job.company, job.location, job.description,
                job.salary, job.job_type, job.posted_date,
                job.url, job.source, job.scraped_at, job.employment_type
            ))
            self.conn.commit()
            return True, "Added new job"

        except sqlite3.IntegrityError:
            return False, "Duplicate (exact match)"
        except sqlite3.Error as e:
            print(f"Error inserting job: {e}")
            return False, f"Error: {e}"

    def insert_jobs_batch(self, jobs: List[JobListing]) -> Dict[str, int]:
        """Insert multiple jobs. Returns stats dict."""
        stats = {'added': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

        for job in jobs:
            success, message = self.insert_job(job)
            if 'Added' in message:
                stats['added'] += 1
            elif 'Updated' in message:
                stats['updated'] += 1
            elif 'Skipped' in message or 'Duplicate' in message:
                stats['skipped'] += 1
            else:
                stats['errors'] += 1

        return stats

    def get_job(self, job_id: int) -> Optional[Dict]:
        """Get a single job by ID."""
        cursor = self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_jobs(self, filters: Optional[Dict] = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Retrieve jobs with optional filters and pagination."""
        query = "SELECT * FROM jobs WHERE 1=1"
        params = []

        if filters:
            if filters.get('source'):
                query += " AND source = ?"
                params.append(filters['source'])
            if filters.get('location'):
                query += " AND location LIKE ?"
                params.append(f"%{filters['location']}%")
            if filters.get('company'):
                query += " AND company LIKE ?"
                params.append(f"%{filters['company']}%")
            if filters.get('status'):
                query += " AND status = ?"
                params.append(filters['status'])
            if filters.get('employment_type'):
                query += " AND employment_type = ?"
                params.append(filters['employment_type'])
            if filters.get('is_applied') is not None:
                query += " AND is_applied = ?"
                params.append(filters['is_applied'])
            if filters.get('search'):
                query += " AND (title LIKE ? OR description LIKE ? OR company LIKE ?)"
                search_term = f"%{filters['search']}%"
                params.extend([search_term, search_term, search_term])

        query += " ORDER BY scraped_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_jobs_count(self, filters: Optional[Dict] = None) -> int:
        """Get total count of jobs matching filters."""
        query = "SELECT COUNT(*) as count FROM jobs WHERE 1=1"
        params = []

        if filters:
            if filters.get('source'):
                query += " AND source = ?"
                params.append(filters['source'])
            if filters.get('location'):
                query += " AND location LIKE ?"
                params.append(f"%{filters['location']}%")
            if filters.get('company'):
                query += " AND company LIKE ?"
                params.append(f"%{filters['company']}%")
            if filters.get('status'):
                query += " AND status = ?"
                params.append(filters['status'])
            if filters.get('employment_type'):
                query += " AND employment_type = ?"
                params.append(filters['employment_type'])
            if filters.get('search'):
                query += " AND (title LIKE ? OR description LIKE ? OR company LIKE ?)"
                search_term = f"%{filters['search']}%"
                params.extend([search_term, search_term, search_term])

        cursor = self.conn.execute(query, params)
        return cursor.fetchone()['count']

    def update_job(self, job_id: int, updates: Dict) -> bool:
        """Update a job and mark as edited."""
        try:
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            updates['is_edited'] = 1
            updates['updated_at'] = datetime.utcnow().isoformat()

            query = f"UPDATE jobs SET {set_clause}, is_edited = 1, updated_at = ? WHERE id = ?"
            values = list(updates.values()) + [job_id]

            self.conn.execute(query, values)
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating job: {e}")
            return False

    def delete_job(self, job_id: int) -> bool:
        """Delete a job by ID."""
        try:
            self.conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error deleting job: {e}")
            return False

    def mark_applied(self, job_id: int, applied: bool = True):
        """Mark a job as applied/unapplied."""
        self.conn.execute(
            "UPDATE jobs SET is_applied = ?, is_edited = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (1 if applied else 0, job_id)
        )
        self.conn.commit()

    def set_status(self, job_id: int, status: str):
        """Set job status (new, interested, applied, rejected, etc.)."""
        valid_statuses = ['new', 'interested', 'applied', 'interviewing', 'offer', 'rejected', 'archived']
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
        self.conn.execute(
            "UPDATE jobs SET status = ?, is_edited = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, job_id)
        )
        self.conn.commit()

    def get_stats(self) -> Dict:
        """Get comprehensive statistics about stored jobs."""
        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT source) as sources,
                COUNT(DISTINCT company) as companies,
                COUNT(CASE WHEN is_applied = 1 THEN 1 END) as applied,
                COUNT(CASE WHEN is_edited = 1 THEN 1 END) as edited,
                COUNT(CASE WHEN status = 'interested' THEN 1 END) as interested,
                COUNT(CASE WHEN status = 'applied' THEN 1 END) as status_applied,
                COUNT(CASE WHEN status = 'interviewing' THEN 1 END) as interviewing,
                COUNT(CASE WHEN employment_type = 'contract' THEN 1 END) as contract,
                COUNT(CASE WHEN employment_type = 'permanent' THEN 1 END) as permanent,
                COUNT(CASE WHEN employment_type = 'WHF' OR location LIKE '%Remote%' THEN 1 END) as remote
            FROM jobs
        """)
        return dict(cursor.fetchone())

    # Search Config Methods
    def get_search_configs(self, enabled_only: bool = False) -> List[SearchConfig]:
        """Get all search configurations."""
        query = "SELECT * FROM search_configs"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY name"

        cursor = self.conn.execute(query)
        return [SearchConfig(**dict(row)) for row in cursor.fetchall()]

    def get_search_config(self, config_id: int) -> Optional[SearchConfig]:
        """Get a single search configuration."""
        cursor = self.conn.execute("SELECT * FROM search_configs WHERE id = ?", (config_id,))
        row = cursor.fetchone()
        return SearchConfig(**dict(row)) if row else None

    def create_search_config(self, config: SearchConfig) -> SearchConfig:
        """Create a new search configuration."""
        cursor = self.conn.execute("""
            INSERT INTO search_configs (name, keywords, location, radius, employment_types, enabled)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (config.name, config.keywords, config.location, config.radius, config.employment_types, config.enabled))
        self.conn.commit()
        config.id = cursor.lastrowid
        return config

    def update_search_config(self, config_id: int, config: SearchConfig) -> bool:
        """Update a search configuration."""
        try:
            self.conn.execute("""
                UPDATE search_configs SET
                    name = ?, keywords = ?, location = ?, radius = ?,
                    employment_types = ?, enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (config.name, config.keywords, config.location, config.radius,
                  config.employment_types, config.enabled, config_id))
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False

    def delete_search_config(self, config_id: int) -> bool:
        """Delete a search configuration."""
        try:
            self.conn.execute("DELETE FROM search_configs WHERE id = ?", (config_id,))
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False

    # Scrape Log Methods
    def log_scrape(self, source: str, config_id: Optional[int], jobs_found: int, jobs_added: int,
                   success: bool = True, error_message: str = None):
        """Log a scraping run."""
        self.conn.execute("""
            INSERT INTO scrape_log (source, search_config_id, jobs_found, jobs_added, completed_at, success, error_message)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """, (source, config_id, jobs_found, jobs_added, success, error_message))
        self.conn.commit()

    def get_recent_scrape_log(self, limit: int = 20) -> List[Dict]:
        """Get recent scraping logs."""
        cursor = self.conn.execute("""
            SELECT * FROM scrape_log ORDER BY started_at DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_scrape_count_last_hour(self, source: str) -> int:
        """Check how many scrapes for this source in the last hour (for rate limiting)."""
        cursor = self.conn.execute("""
            SELECT COUNT(*) as count FROM scrape_log
            WHERE source = ? AND started_at >= datetime('now', '-1 hour')
        """, (source,))
        return cursor.fetchone()['count']

    def get_jobs_needing_descriptions(self, limit: int = 100, source: str = None) -> List[JobListing]:
        """Get jobs that have short descriptions (likely from card-only scraping)."""
        query = """
            SELECT id, title, company, location, description, salary, job_type,
                   posted_date, url, source, scraped_at, employment_type
            FROM jobs
            WHERE length(description) < 500
            AND url IS NOT NULL
        """
        params = []

        if source:
            query += " AND source = ?"
            params.append(source)

        query += " ORDER BY scraped_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, params)

        jobs = []
        for row in cursor.fetchall():
            job_dict = dict(row)
            jobs.append(JobListing(
                title=job_dict['title'],
                company=job_dict['company'],
                location=job_dict['location'],
                description=job_dict['description'],
                salary=job_dict.get('salary'),
                job_type=job_dict.get('job_type'),
                posted_date=job_dict.get('posted_date'),
                url=job_dict['url'],
                source=job_dict['source'],
                scraped_at=job_dict['scraped_at'],
                employment_type=job_dict.get('employment_type')
            ))

        return jobs

    def update_job_description(self, job_id: int, description: str) -> bool:
        """Update a job's description."""
        try:
            self.conn.execute(
                "UPDATE jobs SET description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (description, job_id)
            )
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
