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

// =============================================================================
// CV MANAGEMENT API
// =============================================================================

/**
 * Upload a CV file (DOCX)
 */
export async function uploadCV(file) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/cv/upload`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'Upload failed' }));
        throw new Error(error.error || 'Upload failed');
    }

    return response.json();
}

/**
 * Get the active CV
 */
export async function getCV() {
    return fetchAPI('/cv');
}

/**
 * Delete a CV
 */
export async function deleteCV(cvId) {
    return fetchAPI(`/cv/${cvId}`, {
        method: 'DELETE',
    });
}

// =============================================================================
// VOICE PROFILE API
// =============================================================================

/**
 * Get the active voice profile
 */
export async function getVoiceProfile() {
    return fetchAPI('/voice-profile');
}

/**
 * Save or update the voice profile
 */
export async function saveVoiceProfile(data) {
    return fetchAPI('/voice-profile', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

// =============================================================================
// JOB MATCHING API
// =============================================================================

/**
 * Match CV against a specific job
 */
export async function matchJobToCV(jobId) {
    return fetchAPI(`/match/job/${jobId}`, {
        method: 'POST',
    });
}

/**
 * Batch match CV against multiple jobs
 */
export async function batchMatchJobs(options = {}) {
    return fetchAPI('/match/analyze', {
        method: 'POST',
        body: JSON.stringify(options),
    });
}

/**
 * Get match results for the active CV
 */
export async function getMatchResults(filters = {}) {
    const query = new URLSearchParams();
    if (filters.min_score) query.set('min_score', filters.min_score);
    if (filters.recommendation) query.set('recommendation', filters.recommendation);
    if (filters.limit) query.set('limit', filters.limit);

    const queryString = query.toString();
    return fetchAPI(`/match/results${queryString ? `?${queryString}` : ''}`);
}

/**
 * Get match result for a specific job
 */
export async function getJobMatch(jobId) {
    return fetchAPI(`/match/job/${jobId}`);
}

// =============================================================================
// DOCUMENT GENERATION API
// =============================================================================

/**
 * Generate tailored CV for a job
 */
export async function generateCV(jobId) {
    return fetchAPI(`/generate/cv/${jobId}`, {
        method: 'POST',
    });
}

/**
 * Generate cover letter for a job
 */
export async function generateCoverLetter(jobId) {
    return fetchAPI(`/generate/cover-letter/${jobId}`, {
        method: 'POST',
    });
}

/**
 * Get all generated documents
 */
export async function getDocuments(jobId = null) {
    const query = jobId ? `?job_id=${jobId}` : '';
    return fetchAPI(`/documents${query}`);
}

/**
 * Download a generated document
 */
export function downloadDocument(docId) {
    window.open(`${API_BASE}/documents/${docId}/download`, '_blank');
}

/**
 * Delete a generated document
 */
export async function deleteDocument(docId) {
    return fetchAPI(`/documents/${docId}`, {
        method: 'DELETE',
    });
}
