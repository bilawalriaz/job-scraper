const API_BASE = '/api';

/**
 * Generic fetch wrapper with error handling
 */
async function fetchAPI(endpoint, options = {}) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
        ...options,
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'Request failed' }));
        throw new Error(error.error || 'Request failed');
    }

    return response.json();
}

// Stats
export async function getStats() {
    return fetchAPI('/stats');
}

// Jobs
export async function getJobs(params = {}) {
    const query = new URLSearchParams();
    if (params.page) query.set('page', params.page);
    if (params.per_page) query.set('per_page', params.per_page);
    if (params.status) query.set('status', params.status);
    if (params.employment_type) query.set('employment_type', params.employment_type);
    if (params.source) query.set('source', params.source);
    if (params.search) query.set('search', params.search);

    const queryString = query.toString();
    return fetchAPI(`/jobs${queryString ? `?${queryString}` : ''}`);
}

export async function getJob(id) {
    return fetchAPI(`/jobs/${id}`);
}

export async function updateJob(id, data) {
    return fetchAPI(`/jobs/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    });
}

export async function deleteJob(id) {
    return fetchAPI(`/jobs/${id}`, {
        method: 'DELETE',
    });
}

// Configs
export async function getConfigs() {
    return fetchAPI('/configs');
}

export async function createConfig(data) {
    return fetchAPI('/configs', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function updateConfig(id, data) {
    return fetchAPI(`/configs/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    });
}

export async function deleteConfig(id) {
    return fetchAPI(`/configs/${id}`, {
        method: 'DELETE',
    });
}

// Scraper
export async function runScraper(configIds = []) {
    return fetchAPI('/scrape', {
        method: 'POST',
        body: JSON.stringify({ config_ids: configIds }),
    });
}

// Logs
export async function getLogs() {
    return fetchAPI('/logs');
}

// Rate Limit
export async function getRateLimitStatus() {
    return fetchAPI('/rate-limit');
}

export async function resetRateLimit(source = null) {
    return fetchAPI('/rate-limit/reset', {
        method: 'POST',
        body: JSON.stringify({ source }),
    });
}

// Console logs (for initial load)
export async function getConsoleLogs() {
    return fetchAPI('/console-logs');
}

/**
 * Create an EventSource for streaming console logs
 * Returns a cleanup function
 */
export function streamConsoleLogs(onMessage, onError) {
    const eventSource = new EventSource(`${API_BASE}/console-logs/stream`);

    eventSource.onmessage = (event) => {
        try {
            const log = JSON.parse(event.data);
            onMessage(log);
        } catch (e) {
            console.error('Failed to parse log:', e);
        }
    };

    eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        if (onError) onError(error);
    };

    // Return cleanup function
    return () => eventSource.close();
}

/**
 * Refresh job descriptions for partial listings
 */
export async function refreshDescriptions(options = {}) {
    return fetchAPI('/refresh-descriptions', {
        method: 'POST',
        body: JSON.stringify(options),
    });
}

/**
 * Get count of jobs needing full descriptions by source
 */
export async function getRefreshStatus() {
    return fetchAPI('/jobs/refresh-status');
}

/**
 * Process job descriptions with LLM
 */
export async function processWithLLM(options = {}) {
    return fetchAPI('/llm/process', {
        method: 'POST',
        body: JSON.stringify(options),
    });
}

/**
 * Get LLM processing status
 */
export async function getLLMStatus() {
    return fetchAPI('/llm/status');
}

// =============================================================================
// SCHEDULER API
// =============================================================================

/**
 * Get scheduler status and task states
 */
export async function getSchedulerStatus() {
    return fetchAPI('/scheduler/status');
}

/**
 * Update scheduler configuration
 */
export async function updateSchedulerConfig(config) {
    return fetchAPI('/scheduler/config', {
        method: 'POST',
        body: JSON.stringify(config),
    });
}

/**
 * Manually run a scheduler task
 */
export async function runSchedulerTask(taskName) {
    return fetchAPI(`/scheduler/run/${taskName}`, {
        method: 'POST',
    });
}
