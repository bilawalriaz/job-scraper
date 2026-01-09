"""Flask API for Job Scraper web interface."""

import os
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response, stream_with_context, send_from_directory, abort
from queue import Queue
import threading
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.schema import JobDatabase, JobListing, SearchConfig
from scrapers.totaljobs import TotalJobsDetailedScraper
from scrapers.reed import ReedScraper
from scrapers.cvlibrary import CVLibraryScraper
from scrapers.indeed import IndeedScraper

# Available scrapers configuration
AVAILABLE_SCRAPERS = {
    'totaljobs': TotalJobsDetailedScraper,
    'reed': ReedScraper,
    'cvlibrary': CVLibraryScraper,
    'indeed': IndeedScraper,
}


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['DB_PATH'] = os.environ.get('DB_PATH', 'data/jobs.db')

# Frontend build directory (React app)
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')

# Ensure data directory exists
Path(app.config['DB_PATH']).parent.mkdir(parents=True, exist_ok=True)

# Console log buffer for SSE streaming
log_buffer = []
log_buffer_lock = threading.Lock()
MAX_LOG_ENTRIES = 100


class LogHandler(logging.Handler):
    """Custom logging handler to capture logs into buffer."""

    def emit(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'message': self.format(record)
        }
        with log_buffer_lock:
            log_buffer.append(log_entry)
            if len(log_buffer) > MAX_LOG_ENTRIES:
                log_buffer.pop(0)


# Setup custom log handler
log_handler = LogHandler()
log_handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))

# Add handler to relevant loggers
scrapers_logger = logging.getLogger('scrapers')
scrapers_logger.addHandler(log_handler)
scrapers_logger.setLevel(logging.INFO)

app_logger = logging.getLogger('job_scraper_app')
app_logger.addHandler(log_handler)
app_logger.setLevel(logging.INFO)


def get_db():
    """Get database instance."""
    return JobDatabase(app.config['DB_PATH'])


def async_wrapper(coro):
    """Wrapper to run async functions in Flask."""
    @wraps(coro)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            loop.close()
    wrapper.__name__ = coro.__name__ + "_wrapped"
    return wrapper


# Legacy Template Routes (moved to /legacy/ prefix)
# These are kept for backward compatibility if frontend is not built
@app.route('/legacy/')
def index():
    """Dashboard home (legacy template)."""
    db = get_db()
    stats = db.get_stats()
    recent_jobs = db.get_jobs(limit=10)
    configs = db.get_search_configs(enabled_only=True)
    logs = db.get_recent_scrape_log(limit=5)
    return render_template('index.html', stats=stats, recent_jobs=recent_jobs, configs=configs, logs=logs)


@app.route('/legacy/jobs')
def jobs_list():
    """Jobs list page with filters (legacy template)."""
    db = get_db()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 25))
    offset = (page - 1) * per_page

    filters = {}
    if request.args.get('search'):
        filters['search'] = request.args.get('search')
    if request.args.get('status'):
        filters['status'] = request.args.get('status')
    if request.args.get('employment_type'):
        filters['employment_type'] = request.args.get('employment_type')
    if request.args.get('source'):
        filters['source'] = request.args.get('source')

    jobs = db.get_jobs(filters=filters, limit=per_page, offset=offset)
    total = db.get_jobs_count(filters=filters)
    total_pages = (total + per_page - 1) // per_page

    return render_template('jobs.html',
                         jobs=jobs,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         filters=filters)


@app.route('/legacy/jobs/<int:job_id>')
def job_detail(job_id):
    """Job detail page (legacy template)."""
    db = get_db()
    job = db.get_job(job_id)
    if not job:
        return redirect(url_for('jobs_list'))
    return render_template('job_detail.html', job=job)


@app.route('/legacy/configs')
def configs_list():
    """Search configurations page (legacy template)."""
    db = get_db()
    configs = db.get_search_configs()
    return render_template('configs.html', configs=configs)


@app.route('/legacy/logs')
def logs_list():
    """Scraping logs page (legacy template)."""
    db = get_db()
    logs = db.get_recent_scrape_log(limit=50)
    return render_template('logs.html', logs=logs)



# HTMX Endpoints
@app.route('/htmx/stats')
def htmx_stats():
    """HTMX partial for stats."""
    db = get_db()
    stats = db.get_stats()
    return render_template('partials/stats.html', stats=stats)


@app.route('/htmx/jobs')
def htmx_jobs():
    """HTMX partial for jobs list."""
    db = get_db()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 25))
    offset = (page - 1) * per_page

    filters = {}
    if request.args.get('search'):
        filters['search'] = request.args.get('search')
    if request.args.get('status'):
        filters['status'] = request.args.get('status')
    if request.args.get('employment_type'):
        filters['employment_type'] = request.args.get('employment_type')

    jobs = db.get_jobs(filters=filters, limit=per_page, offset=offset)
    total = db.get_jobs_count(filters=filters)
    total_pages = (total + per_page - 1) // per_page

    return render_template('partials/jobs_table.html',
                         jobs=jobs,
                         page=page,
                         total_pages=total_pages,
                         total=total)


@app.route('/htmx/jobs/<int:job_id>/status', methods=['PUT'])
def htmx_update_status(job_id):
    """HTMX update job status."""
    db = get_db()
    new_status = request.form.get('status')
    try:
        db.set_status(job_id, new_status)
        job = db.get_job(job_id)
        return render_template('partials/job_status.html', job=job)
    except ValueError as e:
        return f"<div class='error'>{str(e)}</div>"


@app.route('/htmx/jobs/<int:job_id>/applied', methods=['PUT'])
def htmx_toggle_applied(job_id):
    """HTMX toggle applied status."""
    db = get_db()
    job = db.get_job(job_id)
    new_status = not job.get('is_applied', False)
    db.mark_applied(job_id, new_status)
    job = db.get_job(job_id)
    return render_template('partials/job_actions.html', job=job)


@app.route('/htmx/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
def htmx_edit_job(job_id):
    """HTMX edit job form."""
    db = get_db()
    job = db.get_job(job_id)

    if request.method == 'POST':
        updates = {}
        if request.form.get('notes'):
            updates['notes'] = request.form.get('notes')
        if request.form.get('salary'):
            updates['salary'] = request.form.get('salary')
        db.update_job(job_id, updates)
        job = db.get_job(job_id)
        return render_template('partials/job_detail_content.html', job=job)

    return render_template('partials/job_edit_form.html', job=job)


@app.route('/htmx/jobs/<int:job_id>', methods=['DELETE'])
def htmx_delete_job(job_id):
    """HTMX delete job."""
    db = get_db()
    db.delete_job(job_id)
    return "<div class='success'>Job deleted</div>"


@app.route('/htmx/configs')
def htmx_configs():
    """HTMX partial for configs list."""
    db = get_db()
    configs = db.get_search_configs()
    return render_template('partials/configs_table.html', configs=configs)


@app.route('/htmx/recent-activity')
def htmx_recent_activity():
    """HTMX partial for recent activity."""
    db = get_db()
    logs = db.get_recent_scrape_log(limit=10)
    return render_template('partials/recent_activity.html', logs=logs)


@app.route('/htmx/configs/new', methods=['GET'])
def htmx_new_config_form():
    """HTMX form for new config."""
    return render_template('partials/config_form.html', config=None)


@app.route('/htmx/configs', methods=['POST'])
def htmx_create_config():
    """HTMX create config."""
    db = get_db()
    config = SearchConfig(
        name=request.form.get('name'),
        keywords=request.form.get('keywords'),
        location=request.form.get('location'),
        radius=int(request.form.get('radius', 10)),
        employment_types=request.form.get('employment_types', ''),
        enabled=request.form.get('enabled') == 'on'
    )
    db.create_search_config(config)
    configs = db.get_search_configs()
    return render_template('partials/configs_table.html', configs=configs)


@app.route('/htmx/configs/<int:config_id>/edit', methods=['GET'])
def htmx_edit_config_form(config_id):
    """HTMX edit config form."""
    db = get_db()
    config = db.get_search_config(config_id)
    return render_template('partials/config_form.html', config=config)


@app.route('/htmx/configs/<int:config_id>', methods=['POST', 'DELETE'])
def htmx_update_config(config_id):
    """HTMX update/delete config."""
    db = get_db()

    if request.method == 'DELETE':
        db.delete_search_config(config_id)
        configs = db.get_search_configs()
        return render_template('partials/configs_table.html', configs=configs)

    config = SearchConfig(
        name=request.form.get('name'),
        keywords=request.form.get('keywords'),
        location=request.form.get('location'),
        radius=int(request.form.get('radius', 10)),
        employment_types=request.form.get('employment_types', ''),
        enabled=request.form.get('enabled') == 'on'
    )
    db.update_search_config(config_id, config)
    configs = db.get_search_configs()
    return render_template('partials/configs_table.html', configs=configs)


@app.route('/htmx/scrape', methods=['POST'])
@async_wrapper
async def htmx_scrape():
    """HTMX trigger scrape."""
    db = get_db()
    config_id = request.form.get('config_id')

    app_logger.info(f"Starting scrape (config_id: {config_id})")

    # Rate limiting check
    last_hour_count = db.get_scrape_count_last_hour('totaljobs')
    if last_hour_count >= 10:
        app_logger.warning("Rate limited: Max 10 scrapes per hour")
        return render_template('partials/scrape_result.html',
                             success=False,
                             message="Rate limited: Max 10 scrapes per hour")

    # Run scraper
    configs = db.get_search_configs(enabled_only=True)
    if config_id:
        configs = [c for c in configs if c.id == int(config_id)]

    if not configs:
        app_logger.warning("No enabled configs found for scraping")
        return render_template('partials/scrape_result.html',
                             success=False,
                             message="No enabled search configurations found")

    results = []
    total_found = 0
    total_added = 0

    scraper = None
    try:
        scraper = TotalJobsDetailedScraper(db, headless=True)
        app_logger.info("Initializing browser...")
        await scraper.init_browser()

        for config in configs:
            app_logger.info(f"Scraping config: {config.name} (keywords: {config.keywords}, location: {config.location})")

            try:
                # Jobs are saved incrementally as they're scraped
                jobs = await scraper.search_jobs(
                    search_term=config.keywords,
                    location=config.location,
                    radius=config.radius,
                    employment_types=config.employment_types or None,
                    max_pages=20,  # Scrape up to 20 pages per config (500 jobs)
                    save_incrementally=True
                )

                jobs_found = len(jobs)
                app_logger.info(f"Scraped {jobs_found} jobs for {config.name} (saved incrementally)")

                total_found += jobs_found
                total_added += jobs_found  # All scraped jobs were saved

                db.log_scrape('totaljobs', config.id, jobs_found, jobs_found)

                results.append({
                    'config': config.name,
                    'found': jobs_found,
                    'added': jobs_found
                })

            except Exception as e:
                app_logger.error(f"Error scraping {config.name}: {str(e)}")
                db.log_scrape('totaljobs', config.id, 0, 0, success=False, error_message=str(e))
                results.append({
                    'config': config.name,
                    'error': str(e)
                })

        # Second pass: Fetch full descriptions for jobs with short descriptions
        app_logger.info("Starting second pass: fetching full descriptions...")
        jobs_needing_descriptions = db.get_jobs_needing_descriptions(limit=200, source='totaljobs')

        if jobs_needing_descriptions:
            app_logger.info(f"Fetching full descriptions for {len(jobs_needing_descriptions)} jobs...")

            updated_jobs = await scraper.fetch_full_descriptions(jobs_needing_descriptions)

            # Update descriptions in database
            for job in updated_jobs:
                # Find job ID by matching URL
                cursor = db.conn.execute("SELECT id FROM jobs WHERE url = ?", (job.url,))
                row = cursor.fetchone()
                if row:
                    db.update_job_description(row['id'], job.description)

            app_logger.info(f"Updated descriptions for {len(updated_jobs)} jobs")
        else:
            app_logger.info("No jobs need full descriptions")

    except Exception as e:
        app_logger.error(f"Failed to initialize scraper: {str(e)}")
        return render_template('partials/scrape_result.html',
                             success=False,
                             message=f"Failed to initialize browser: {str(e)}")
    finally:
        if scraper:
            app_logger.info("Cleaning up browser resources...")
            await scraper.cleanup()

    app_logger.info(f"Scrape complete: {total_found} found, {total_added} added")

    return render_template('partials/scrape_result.html',
                         success=total_found > 0 or total_added == 0,
                         results=results,
                         total_found=total_found,
                         total_added=total_added)


# JSON API Endpoints
@app.route('/api/jobs', methods=['GET'])
def api_jobs():
    """API: Get jobs."""
    db = get_db()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    offset = (page - 1) * per_page

    filters = {}
    for key in ['search', 'status', 'employment_type', 'source']:
        if request.args.get(key):
            filters[key] = request.args.get(key)

    jobs = db.get_jobs(filters=filters, limit=per_page, offset=offset)
    total = db.get_jobs_count(filters=filters)
    total_pages = (total + per_page - 1) // per_page

    return jsonify({
        'jobs': jobs,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages
    })


@app.route('/api/jobs/<int:job_id>', methods=['GET'])
def api_job_detail(job_id):
    """API: Get job detail."""
    db = get_db()
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(job)


@app.route('/api/jobs/<int:job_id>', methods=['PATCH', 'PUT'])
def api_update_job(job_id):
    """API: Update job."""
    db = get_db()
    data = request.get_json() or request.form.to_dict()
    if db.update_job(job_id, data):
        return jsonify({'success': True})
    return jsonify({'error': 'Update failed'}), 400


@app.route('/api/jobs/<int:job_id>', methods=['DELETE'])
def api_delete_job(job_id):
    """API: Delete job."""
    db = get_db()
    if db.delete_job(job_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Delete failed'}), 400


@app.route('/api/configs', methods=['GET'])
def api_configs():
    """API: Get search configs."""
    db = get_db()
    configs = db.get_search_configs()
    return jsonify({'configs': [c.to_dict() for c in configs]})


@app.route('/api/configs', methods=['POST'])
def api_create_config():
    """API: Create config."""
    db = get_db()
    data = request.get_json() or request.form.to_dict()
    config = SearchConfig(
        name=data.get('name'),
        keywords=data.get('keywords'),
        location=data.get('location'),
        radius=int(data.get('radius', 10)),
        employment_types=data.get('employment_types', ''),
        enabled=data.get('enabled', True)
    )
    created = db.create_search_config(config)
    return jsonify(created.to_dict())


@app.route('/api/configs/<int:config_id>', methods=['DELETE'])
def api_delete_config(config_id):
    """API: Delete config."""
    db = get_db()
    if db.delete_search_config(config_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Delete failed'}), 400


async def scrape_source(source_name: str, configs: list, db_path: str) -> dict:
    """Scrape a single source. Runs in parallel with other sources."""
    # Each parallel task needs its own DB connection
    db = JobDatabase(db_path)
    scraper_class = AVAILABLE_SCRAPERS[source_name]
    scraper = None
    result = {'source': source_name, 'found': 0, 'added': 0}

    try:
        scraper = scraper_class(db, headless=True)
        app_logger.info(f"[{source_name}] Initializing browser...")
        await scraper.init_browser()

        for config in configs:
            app_logger.info(f"[{source_name}] Scraping: {config.name}")
            try:
                jobs = await scraper.search_jobs(
                    config.keywords,
                    config.location,
                    radius=config.radius,
                    employment_types=config.employment_types or None,
                    max_pages=10,
                    save_incrementally=True
                )
                jobs_found = len(jobs)
                result['found'] += jobs_found
                result['added'] += jobs_found
                db.log_scrape(source_name, config.id, jobs_found, jobs_found)

            except Exception as e:
                app_logger.error(f"[{source_name}] Error scraping {config.name}: {e}")
                db.log_scrape(source_name, config.id, 0, 0, success=False, error_message=str(e))

        # Second pass for TotalJobs: Fetch full descriptions
        if source_name == 'totaljobs' and hasattr(scraper, 'fetch_full_descriptions'):
            app_logger.info(f"[{source_name}] Fetching full descriptions...")
            jobs_needing_descriptions = db.get_jobs_needing_descriptions(limit=50, source='totaljobs')

            if jobs_needing_descriptions:
                updated_jobs = await scraper.fetch_full_descriptions(jobs_needing_descriptions)
                for job in updated_jobs:
                    cursor = db.conn.execute("SELECT id FROM jobs WHERE url = ?", (job.url,))
                    row = cursor.fetchone()
                    if row:
                        db.update_job_description(row['id'], job.description)
                app_logger.info(f"[{source_name}] Updated {len(updated_jobs)} descriptions")

    except Exception as e:
        app_logger.error(f"[{source_name}] Failed: {e}")
        result['error'] = str(e)
    finally:
        if scraper:
            await scraper.cleanup()
        db.close()

    app_logger.info(f"[{source_name}] Complete: {result['found']} jobs found")
    return result


@app.route('/api/scrape', methods=['POST'])
@async_wrapper
async def api_scrape():
    """API: Trigger scrape across all job sources IN PARALLEL."""
    db = get_db()
    data = request.get_json() or {}
    config_id = data.get('config_id')
    sources = data.get('sources', list(AVAILABLE_SCRAPERS.keys()))

    app_logger.info(f"API scrape requested (sources: {sources})")

    # Get enabled configs
    configs = db.get_search_configs(enabled_only=True)
    if config_id:
        configs = [c for c in configs if c.id == config_id]

    if not configs:
        app_logger.warning("No enabled configs found")
        return jsonify({'error': 'No enabled configurations found'}), 400

    # Filter out rate-limited and invalid sources
    valid_sources = []
    skipped_results = []

    for source_name in sources:
        if source_name not in AVAILABLE_SCRAPERS:
            app_logger.warning(f"Unknown source: {source_name}")
            continue

        rate_status = db.get_rate_limit_status().get(source_name, {})
        if rate_status.get('limited', False):
            app_logger.warning(f"Rate limited for {source_name}, skipping")
            skipped_results.append({'source': source_name, 'error': 'Rate limited'})
            continue

        valid_sources.append(source_name)

    if not valid_sources:
        return jsonify({
            'success': False,
            'error': 'All sources are rate limited',
            'results': skipped_results
        }), 429

    # Run all scrapers in PARALLEL
    app_logger.info(f"Starting parallel scrape of {len(valid_sources)} sources: {valid_sources}")

    # Convert configs to dicts for passing to parallel tasks
    config_dicts = [{'id': c.id, 'name': c.name, 'keywords': c.keywords,
                     'location': c.location, 'radius': c.radius,
                     'employment_types': c.employment_types} for c in configs]

    # Create config objects for each task (can't share across threads)
    class ConfigObj:
        def __init__(self, d):
            self.id = d['id']
            self.name = d['name']
            self.keywords = d['keywords']
            self.location = d['location']
            self.radius = d['radius']
            self.employment_types = d['employment_types']

    config_objs = [ConfigObj(d) for d in config_dicts]

    # Run all sources in parallel
    tasks = [scrape_source(source, config_objs, app.config['DB_PATH']) for source in valid_sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    final_results = skipped_results.copy()
    total_found = 0
    total_added = 0

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            final_results.append({
                'source': valid_sources[i],
                'error': str(result)
            })
        else:
            final_results.append(result)
            total_found += result.get('found', 0)
            total_added += result.get('added', 0)

    app_logger.info(f"Parallel scrape complete: {total_found} jobs found across all sources")

    return jsonify({
        'success': True,
        'total_found': total_found,
        'total_added': total_added,
        'results': final_results
    })


@app.route('/api/stats', methods=['GET'])
def api_stats():
    """API: Get stats formatted for frontend."""
    db = get_db()
    raw_stats = db.get_stats()
    configs = db.get_search_configs(enabled_only=True)

    # Get count of new jobs (status='new')
    cursor = db.conn.execute("SELECT COUNT(*) as count FROM jobs WHERE status = 'new'")
    new_count = cursor.fetchone()['count']

    return jsonify({
        'total_jobs': raw_stats.get('total', 0),
        'new_jobs': new_count,
        'applied_jobs': raw_stats.get('applied', 0),
        'active_configs': len(configs),
        # Also include raw stats for other uses
        **raw_stats
    })


@app.route('/api/logs', methods=['GET'])
def api_logs():
    """API: Get scrape logs."""
    db = get_db()
    limit = int(request.args.get('limit', 50))
    return jsonify({'logs': db.get_recent_scrape_log(limit=limit)})


@app.route('/api/rate-limit', methods=['GET'])
def api_rate_limit_status():
    """API: Get rate limit status for all sources."""
    db = get_db()
    return jsonify(db.get_rate_limit_status())


@app.route('/api/sources', methods=['GET'])
def api_sources():
    """API: Get available scraper sources."""
    return jsonify({
        'sources': list(AVAILABLE_SCRAPERS.keys())
    })


@app.route('/api/rate-limit/reset', methods=['POST'])
def api_rate_limit_reset():
    """API: Reset rate limit for a source or all sources."""
    db = get_db()
    data = request.get_json() or {}
    source = data.get('source')  # None means reset all

    cleared = db.reset_rate_limit(source)
    app_logger.info(f"Rate limit reset: cleared {cleared} entries" + (f" for {source}" if source else " for all sources"))

    return jsonify({
        'success': True,
        'cleared': cleared,
        'source': source or 'all',
        'status': db.get_rate_limit_status()
    })


@app.route('/api/console-logs/stream')
def stream_console_logs():
    """SSE endpoint for streaming console logs."""
    import json as json_mod

    def generate():
        client_last_index = len(log_buffer)
        while True:
            with log_buffer_lock:
                buffer_len = len(log_buffer)
                if buffer_len > client_last_index:
                    # Send new logs
                    for i in range(client_last_index, buffer_len):
                        log_entry = log_buffer[i]
                        json_str = json_mod.dumps(log_entry)
                        yield f"data: {json_str}\n\n"
                    client_last_index = buffer_len
            import time
            time.sleep(0.5)  # Send updates every 0.5 seconds
    return Response(stream_with_context(generate()),
                   mimetype='text/event-stream',
                   headers={'Cache-Control': 'no-cache',
                           'Connection': 'keep-alive',
                           'X-Accel-Buffering': 'no'})


@app.route('/api/console-logs', methods=['GET'])
def get_console_logs():
    """API: Get current console logs (non-streaming)."""
    with log_buffer_lock:
        return jsonify(log_buffer[-50:])  # Return last 50 logs


# React Frontend Serving
# These routes serve the built React app for all non-API routes
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """Serve React frontend for all non-API routes."""
    # Skip if path starts with api/, htmx/, or legacy/ (handled by other routes)
    if path.startswith('api/') or path.startswith('htmx/') or path.startswith('legacy'):
        return abort(404)
    
    # Check if frontend build exists
    if not os.path.exists(FRONTEND_DIR):
        # Fallback to legacy template routes if frontend not built
        return redirect(url_for('index'))
    
    # Serve static files directly if they exist
    if path and os.path.exists(os.path.join(FRONTEND_DIR, path)):
        return send_from_directory(FRONTEND_DIR, path)
    
    # For all other routes, serve index.html (SPA routing)
    return send_from_directory(FRONTEND_DIR, 'index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
