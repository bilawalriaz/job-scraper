"""Flask API for Job Scraper web interface."""

import os
import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path
from functools import wraps
from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory, abort
from queue import Queue
import threading
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.schema import JobDatabase, JobListing, SearchConfig
from scrapers.totaljobs import TotalJobsDetailedScraper
from scrapers.reed import ReedScraper
from scrapers.cvlibrary import CVLibraryScraper
from scrapers.indeed import IndeedScraper
from llm.processor import get_processor

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

        # Second pass: Fetch full descriptions for all sources
        if hasattr(scraper, 'fetch_full_descriptions'):
            app_logger.info(f"[{source_name}] Fetching full descriptions...")
            jobs_needing_descriptions = db.get_jobs_needing_descriptions(limit=50, source=source_name)

            if jobs_needing_descriptions:
                updated_jobs = await scraper.fetch_full_descriptions(jobs_needing_descriptions)
                updated_count = 0
                for job in updated_jobs:
                    cursor = db.conn.execute("SELECT id FROM jobs WHERE url = ?", (job.url,))
                    row = cursor.fetchone()
                    if row and job.description and len(job.description) > 200:
                        db.update_job_description(row['id'], job.description, mark_full=True)
                        updated_count += 1
                app_logger.info(f"[{source_name}] Updated {updated_count} descriptions")

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


@app.route('/api/refresh-descriptions', methods=['POST'])
@async_wrapper
async def api_refresh_descriptions():
    """
    API: Refresh job descriptions for partial listings.
    Fetches full descriptions from original job URLs.
    """
    db = get_db()
    data = request.get_json() or {}
    source = data.get('source')  # Filter by source (e.g., 'totaljobs')
    limit = int(data.get('limit', 1000))  # Max number of jobs to refresh (default: all)
    job_id = data.get('job_id')  # Refresh a specific job by ID

    app_logger.info(f"Description refresh requested (source: {source}, limit: {limit}, job_id: {job_id})")

    # Check rate limiting
    if source:
        rate_status = db.get_rate_limit_status().get(source, {})
        if rate_status.get('limited', False):
            app_logger.warning(f"Rate limited for {source}")
            return jsonify({
                'success': False,
                'error': f'Rate limited for {source}. Please try again later.'
            }), 429

    # Get jobs to refresh
    jobs_to_refresh = []

    if job_id:
        # Refresh a specific job
        job_dict = db.get_job(int(job_id))
        if not job_dict:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        jobs_to_refresh.append(JobListing(
            title=job_dict['title'],
            company=job_dict['company'],
            location=job_dict['location'],
            description=job_dict['description'],
            url=job_dict['url'],
            source=job_dict['source'],
            scraped_at=job_dict['scraped_at'],
            employment_type=job_dict.get('employment_type')
        ))
    else:
        # Get all jobs needing full descriptions
        jobs_to_refresh = db.get_jobs_needing_descriptions(limit=limit, source=source)

    if not jobs_to_refresh:
        return jsonify({
            'success': True,
            'message': 'No jobs need refreshing',
            'updated': 0
        })

    app_logger.info(f"Refreshing {len(jobs_to_refresh)} job descriptions...")

    # Determine which scraper to use based on source
    source_to_refresh = source or jobs_to_refresh[0].source
    scraper_class = AVAILABLE_SCRAPERS.get(source_to_refresh)

    if not scraper_class:
        app_logger.error(f"No scraper available for source: {source_to_refresh}")
        return jsonify({
            'success': False,
            'error': f'No scraper available for source: {source_to_refresh}'
        }), 400

    scraper = None
    updated_count = 0
    failed_count = 0

    try:
        scraper = scraper_class(db, headless=True)
        app_logger.info(f"Initializing {source_to_refresh} scraper...")
        await scraper.init_browser()

        # Check if scraper has fetch_full_descriptions method
        if not hasattr(scraper, 'fetch_full_descriptions'):
            app_logger.error(f"Scraper for {source_to_refresh} doesn't support fetching full descriptions")
            return jsonify({
                'success': False,
                'error': f'Scraper for {source_to_refresh} does not support description refresh'
            }), 400

        # Fetch full descriptions
        updated_jobs = await scraper.fetch_full_descriptions(jobs_to_refresh)

        # Update descriptions in database
        for job in updated_jobs:
            # Find job ID by matching URL
            cursor = db.conn.execute("SELECT id FROM jobs WHERE url = ?", (job.url,))
            row = cursor.fetchone()
            if row:
                success = db.update_job_description(row['id'], job.description, mark_full=True)
                if success:
                    updated_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1
                app_logger.warning(f"Could not find job in database with URL: {job.url}")

        app_logger.info(f"Refresh complete: {updated_count} updated, {failed_count} failed")

        return jsonify({
            'success': True,
            'updated': updated_count,
            'failed': failed_count,
            'message': f'Refreshed {updated_count} job descriptions'
        })

    except Exception as e:
        app_logger.error(f"Failed to refresh descriptions: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        if scraper:
            app_logger.info("Cleaning up scraper...")
            await scraper.cleanup()


@app.route('/api/jobs/refresh-status', methods=['GET'])
def api_refresh_status():
    """
    API: Get count of jobs needing full descriptions by source.
    Useful for showing a refresh button or badge in the UI.
    """
    db = get_db()
    partial_counts = db.get_partial_description_count()
    return jsonify(partial_counts)


# LLM Processing Endpoints
@app.route('/api/llm/process', methods=['POST'])
def api_llm_process():
    """
    API: Process job descriptions with LLM.
    Cleans descriptions, extracts tags and entities.
    """
    db = get_db()
    data = request.get_json() or {}
    limit = int(data.get('limit', 10))
    job_id = data.get('job_id')  # Process specific job

    app_logger.info(f"LLM processing requested (limit: {limit}, job_id: {job_id})")

    try:
        processor = get_processor()
    except ValueError as e:
        app_logger.error(f"LLM processor init failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

    # Get jobs to process
    if job_id:
        job = db.get_job(int(job_id))
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        jobs_to_process = [job]
    else:
        jobs_to_process = db.get_jobs_needing_llm_processing(limit=limit)

    if not jobs_to_process:
        return jsonify({
            'success': True,
            'message': 'No jobs need LLM processing',
            'processed': 0,
            'failed': 0
        })

    app_logger.info(f"Processing {len(jobs_to_process)} jobs with LLM...")

    def progress_callback(current, total, title):
        app_logger.info(f"[LLM] Processing {current}/{total}: {title[:50]}...")

    stats = processor.process_jobs_batch(jobs_to_process, progress_callback)

    # Update database with results
    for job in jobs_to_process:
        if 'llm_result' in job:
            result = job['llm_result']
            
            # Update LLM data
            db.update_job_llm_data(
                job['id'],
                result['cleaned_description'],
                result['tags'],
                result['entities']
            )
            
            # Also update missing job fields from extracted entities
            try:
                entities = json.loads(result['entities']) if isinstance(result['entities'], str) else result['entities']
                updates = {}
                
                # Fill in location if missing/unknown
                if (not job.get('location') or job.get('location', '').lower() in ['unknown', 'not specified', '']) and entities.get('locations'):
                    updates['location'] = entities['locations'][0]
                
                # Fill in salary if missing/unknown
                if (not job.get('salary') or job.get('salary', '').lower() in ['unknown', 'not specified', '']) and entities.get('salary_info'):
                    updates['salary'] = entities['salary_info']
                
                # Apply updates if any
                if updates:
                    db.update_job(job['id'], updates)
                    app_logger.info(f"[LLM] Updated job {job['id']} fields: {list(updates.keys())}")
            except Exception as e:
                app_logger.warning(f"[LLM] Failed to update job fields from entities: {e}")

    app_logger.info(f"LLM processing complete: {stats['processed']} processed, {stats['failed']} failed")

    return jsonify({
        'success': True,
        'processed': stats['processed'],
        'failed': stats['failed'],
        'skipped': stats['skipped'],
        'message': f"Processed {stats['processed']} jobs with LLM"
    })


@app.route('/api/llm/status', methods=['GET'])
def api_llm_status():
    """
    API: Get LLM processing status.
    Returns count of pending jobs and rate limit status.
    """
    db = get_db()
    processing_count = db.get_llm_processing_count()

    try:
        processor = get_processor()
        rate_status = processor.get_rate_limit_status()
    except ValueError:
        rate_status = {'error': 'LLM processor not initialized'}

    return jsonify({
        'pending': processing_count['pending'],
        'processed': processing_count['processed'],
        'total': processing_count['total'],
        'rate_limit': rate_status
    })


# React Frontend Serving
# These routes serve the built React app for all non-API routes
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """Serve React frontend for all non-API routes."""
    # Skip if path starts with api/ (handled by other routes)
    if path.startswith('api/'):
        return abort(404)
    
    # Serve static files directly if they exist
    if path and os.path.exists(os.path.join(FRONTEND_DIR, path)):
        return send_from_directory(FRONTEND_DIR, path)
    
    # For all other routes, serve index.html (SPA routing)
    return send_from_directory(FRONTEND_DIR, 'index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
