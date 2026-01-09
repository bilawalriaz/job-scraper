# Job Scraper

A stealthy multi-site job scraper with web interface, designed for DevOps/SRE/Cloud Engineer job hunting.

## Features

### Core Functionality
- **Stealth Mode**: Advanced anti-detection with user agent rotation, browser fingerprint masking, realistic mouse/scroll behavior
- **Smart Deduplication**: Detects duplicate postings (same company + title + location) and doesn't overwrite user-edited entries
- **Rate Limiting**: Built-in rate limiting (max 10 scrapes/hour per source) to avoid blocks
- **Web Interface**: Clean HTMX + Jinja2 frontend for managing jobs and searches
- **REST API**: Full JSON API for programmatic access

### Job Management
- **CRUD Operations**: Create, read, update, delete job listings
- **Status Tracking**: Track jobs through pipeline (New → Interested → Applied → Interviewing → Offer)
- **Notes & Metadata**: Add notes, override salary, mark edited entries
- **Search & Filter**: Full-text search, filter by status, employment type, location, company

### Search Configuration
- **Multiple Keywords**: Search for multiple job types (e.g., "DevOps Engineer", "Azure Cloud Engineer")
- **Employment Types**: Filter by permanent, contract, or work-from-home
- **Location Control**: Specify location and search radius
- **Enable/Disable**: Toggle searches without deleting

## Quick Start

### Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/bilawalriaz/job-scraper.git
cd job-scraper

# Build and run
docker-compose up -d

# Access the web interface
open http://localhost:5000
```

### Manual Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the application
python api/app.py

# Access at http://localhost:5000
```

## Usage

### Web Interface

1. **Dashboard** (`/`): Overview with stats, recent jobs, active searches
2. **Jobs** (`/jobs`): Full job list with filters and pagination
3. **Search Configs** (`/configs`): Manage your automated search queries
4. **Logs** (`/logs`): View scraping history and errors

### Example Search Configurations

```
Name: DevOps London
Keywords: DevOps Engineer, Platform Engineer, SRE
Location: London
Radius: 10 miles
Employment Types: permanent,contract
Enabled: Yes

---

Name: Remote Cloud
Keywords: Azure Cloud Engineer, AWS DevOps, GCP Engineer
Location: Remote
Radius: 0
Employment Types: contract,whf
Enabled: Yes
```

### REST API

```bash
# Get all jobs
curl http://localhost:5000/api/jobs

# Get jobs with filters
curl http://localhost:5000/api/jobs?status=interested&employment_type=contract

# Get specific job
curl http://localhost:5000/api/jobs/123

# Update job
curl -X PATCH http://localhost:5000/api/jobs/123 \
  -H "Content-Type: application/json" \
  -d '{"notes": "Applied via company website"}'

# Delete job
curl -X DELETE http://localhost:5000/api/jobs/123

# Create search config
curl -X POST http://localhost:5000/api/configs \
  -H "Content-Type: application/json" \
  -d '{"name": "DevOps", "keywords": "DevOps Engineer", "location": "London"}'

# Run scraper
curl -X POST http://localhost:5000/api/scrape

# Get stats
curl http://localhost:5000/api/stats
```

## Architecture

```
job-scraper/
├── api/
│   ├── app.py              # Flask application & REST API
│   ├── templates/          # Jinja2 HTML templates
│   │   ├── base.html
│   │   ├── index.html      # Dashboard
│   │   ├── jobs.html       # Jobs list
│   │   ├── job_detail.html
│   │   ├── configs.html    # Search configurations
│   │   └── logs.html       # Scraping logs
│   └── templates/partials/ # HTMX partials
├── database/
│   └── schema.py           # Database schema & operations
├── scrapers/
│   ├── base.py             # Base scraper with stealth mode
│   └── totaljobs.py        # TotalJobs implementation
├── data/                   # SQLite database (created at runtime)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Database Schema

### Jobs Table
```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY,
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
    employment_type TEXT,
    status TEXT DEFAULT 'new',        -- new, interested, applied, interviewing, offer, rejected, archived
    is_applied BOOLEAN DEFAULT 0,
    is_edited BOOLEAN DEFAULT 0,     -- Protects from scraper updates
    notes TEXT,
    UNIQUE(company, title, location)
);
```

### Search Configs Table
```sql
CREATE TABLE search_configs (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    keywords TEXT,
    location TEXT,
    radius INTEGER,
    employment_types TEXT,
    enabled BOOLEAN
);
```

## Stealth Features

The scraper uses multiple anti-detection techniques:

1. **User Agent Rotation**: Real browser signatures from Chrome, Firefox, Safari
2. **Browser Fingerprint Masking**: Hides webdriver property, mocks plugins/languages
3. **Human-like Behavior**: Random delays, mouse movements, scroll patterns
4. **Rate Limiting**: Minimum 2-5 seconds between requests
5. **Geolocation Spoofing**: London timezone/locale

## Rate Limiting

To avoid blocking:

- **Max 10 scrapes per source per hour**
- **2-5 second delay between requests**
- **Respect 429 (Too Many Requests) responses**
- **Exponential backoff on failures**

## Adding New Job Sites

1. Create new scraper in `scrapers/` that inherits from `BaseScraper`:

```python
from scrapers.base import BaseScraper
from database.schema import JobListing

class IndeedScraper(BaseScraper):
    def get_site_name(self) -> str:
        return "indeed"

    async def search_jobs(self, search_term: str, location: str = "London"):
        # Implementation here
        pass
```

2. Add to `api/app.py` scraper selection logic

## Development

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run with debug mode
FLASK_DEBUG=1 python api/app.py

# Or with Python module
python -m api.app
```

### Database Management

```bash
# Access SQLite directly
sqlite3 data/jobs.db

# View schema
.schema

# Query jobs
SELECT * FROM jobs ORDER BY scraped_at DESC LIMIT 10;

# Update status
UPDATE jobs SET status = 'interested' WHERE id = 123;
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `data/jobs.db` | SQLite database path |
| `SECRET_KEY` | `dev-key-change-in-production` | Flask session key |

## Deployment

### Docker Compose

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Rebuild
docker-compose up -d --build
```

### Manual Deployment

```bash
# Set production secret key
export SECRET_KEY=$(openssl rand -hex 32)

# Run with gunicorn (production)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api.app:app
```

## Troubleshooting

### Scraping Not Working

1. Check logs at `/logs` for error messages
2. Verify rate limiting (max 10 scrapes/hour)
3. Try running scraper in visible mode to see what's happening
4. Check if job site has changed structure

### Database Locked

```bash
# If using Docker, restart container
docker-compose restart

# If running locally, check for other processes
lsof data/jobs.db
```

### High Memory Usage

Playwright browsers can use 200-500MB each. The scraper cleans up after each run.

## Legal & Ethical

- **Respect robots.txt** and terms of service
- **Don't overload servers** - use built-in rate limiting
- **For personal use only** - not for commercial scraping
- **Attribution** - This tool helps you find jobs, not to harvest data

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - feel free to use for personal job hunting.

## Roadmap

- [ ] Add Indeed scraper
- [ ] Add Reed scraper
- [ ] Add LinkedIn scraper
- [ ] Export to CSV/Excel
- [ ] Email notifications for new matches
- [ ] Salary analysis and trends
- [ ] Skills extraction and ranking
- [ ] Application tracker integration

## Support

For issues or questions:
- GitHub Issues: https://github.com/bilawalriaz/job-scraper/issues
- Documentation: https://github.com/bilawalriaz/job-scraper/wiki
