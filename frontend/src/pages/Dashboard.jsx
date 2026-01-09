import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getStats, getJobs, getConfigs, runScraper, getRateLimitStatus, resetRateLimit } from '../api/client';
import { Card, CardHeader, CardBody } from '../components/Card';
import Button from '../components/Button';
import Console from '../components/Console';
import Spinner from '../components/Spinner';
import { StatusBadge } from '../components/StatusBadge';
import { PlayIcon, BriefcaseIcon, LocationIcon, DollarIcon, SearchIcon, UserIcon, RefreshIcon } from '../components/Icons';

function Dashboard() {
    const [stats, setStats] = useState(null);
    const [recentJobs, setRecentJobs] = useState([]);
    const [configs, setConfigs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [scraping, setScraping] = useState(false);
    const [scrapeResult, setScrapeResult] = useState(null);
    const [rateLimitStatus, setRateLimitStatus] = useState(null);
    const [resettingRateLimit, setResettingRateLimit] = useState(false);

    const loadData = useCallback(async () => {
        try {
            const [statsData, jobsData, configsData, rateLimitData] = await Promise.all([
                getStats(),
                getJobs({ per_page: 10 }),
                getConfigs(),
                getRateLimitStatus()
            ]);
            setStats(statsData);
            setRecentJobs(jobsData.jobs || []);
            setConfigs(configsData.configs || []);
            setRateLimitStatus(rateLimitData);
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadData();
        // Refresh stats and rate limits every 5 seconds for near real-time updates
        const interval = setInterval(() => {
            Promise.all([
                getStats().then(setStats),
                getRateLimitStatus().then(setRateLimitStatus)
            ]).catch(console.error);
        }, 5000);
        return () => clearInterval(interval);
    }, [loadData]);

    const handleRunScraper = async () => {
        setScraping(true);
        setScrapeResult(null);
        try {
            const result = await runScraper();
            setScrapeResult(result);
            // Reload data after scraping
            loadData();
        } catch (error) {
            setScrapeResult({ error: error.message });
        } finally {
            setScraping(false);
        }
    };

    const handleResetRateLimit = async () => {
        setResettingRateLimit(true);
        try {
            const result = await resetRateLimit();
            setRateLimitStatus(result.status);
        } catch (error) {
            console.error('Failed to reset rate limit:', error);
        } finally {
            setResettingRateLimit(false);
        }
    };

    // Check if any source is rate limited
    const isAnyRateLimited = rateLimitStatus && Object.values(rateLimitStatus).some(s => s.limited);

    if (loading) {
        return (
            <div className="loading-state">
                <Spinner size={40} />
            </div>
        );
    }

    return (
        <>
            {/* Page Header */}
            <div className="page-header">
                <div>
                    <h1 className="page-title">Dashboard</h1>
                    <p className="page-subtitle">Monitor your job search activity</p>
                </div>
                <Button variant="primary" onClick={handleRunScraper} loading={scraping} disabled={scraping}>
                    <PlayIcon />
                    Run Scraper
                </Button>
            </div>

            {/* Scrape Result */}
            {scrapeResult && (
                <div className={`alert ${scrapeResult.error ? 'alert-error' : 'alert-success'}`}>
                    {scrapeResult.error ? (
                        `Error: ${scrapeResult.error}`
                    ) : (
                        `Scraping complete! Found ${scrapeResult.total_found || 0} jobs, added ${scrapeResult.total_added || 0} new jobs.`
                    )}
                </div>
            )}

            {/* Rate Limit Warning */}
            {isAnyRateLimited && (
                <div className="alert alert-error d-flex justify-between align-center">
                    <span>Rate limit reached for some sources. Wait or reset to continue scraping.</span>
                    <Button
                        variant="secondary"
                        size="sm"
                        onClick={handleResetRateLimit}
                        loading={resettingRateLimit}
                        style={{ marginLeft: '16px' }}
                    >
                        <RefreshIcon size={14} /> Reset Rate Limits
                    </Button>
                </div>
            )}

            {/* Console */}
            <Console />

            {/* Rate Limit Status */}
            {rateLimitStatus && (
                <div className="rate-limit-bar">
                    {Object.entries(rateLimitStatus).map(([source, status]) => (
                        <div key={source} className={`rate-limit-item ${status.limited ? 'limited' : ''}`}>
                            <span className="rate-limit-source">{source}</span>
                            <span className="rate-limit-count">{status.remaining}/{status.limit}</span>
                        </div>
                    ))}
                    <button
                        className="rate-limit-reset"
                        onClick={handleResetRateLimit}
                        disabled={resettingRateLimit}
                        title="Reset all rate limits"
                    >
                        <RefreshIcon size={12} />
                    </button>
                </div>
            )}

            {/* Stats Grid */}
            <div className="stats-grid">
                <div className="stat-card">
                    <div className="stat-value">{stats?.total_jobs || 0}</div>
                    <div className="stat-label">Total Jobs</div>
                </div>
                <div className="stat-card">
                    <div className="stat-value">{stats?.new_jobs || 0}</div>
                    <div className="stat-label">New Jobs</div>
                </div>
                <div className="stat-card">
                    <div className="stat-value">{stats?.applied_jobs || 0}</div>
                    <div className="stat-label">Applied</div>
                </div>
                <div className="stat-card">
                    <div className="stat-value">{stats?.active_configs || 0}</div>
                    <div className="stat-label">Active Searches</div>
                </div>
            </div>

            {/* Main Content */}
            <div className="main-sidebar-layout" style={{ marginTop: '48px' }}>
                {/* Recent Jobs */}
                <div className="main-content">
                    <Card>
                        <CardHeader actions={<Link to="/jobs" style={{ fontSize: '0.875rem', fontWeight: 600 }}>View All</Link>}>
                            Recent Jobs
                        </CardHeader>
                        <CardBody noPadding>
                            {recentJobs.length > 0 ? (
                                recentJobs.map(job => (
                                    <div key={job.id} className="job-item">
                                        <div className="d-flex justify-between" style={{ marginBottom: '8px' }}>
                                            <h6 style={{ fontWeight: 600, fontSize: '0.9375rem', margin: 0 }}>
                                                <Link to={`/jobs/${job.id}`} style={{ color: 'var(--text-primary)' }}>
                                                    {job.title}
                                                </Link>
                                            </h6>
                                            <StatusBadge status={job.status} />
                                        </div>
                                        <div className="text-muted small d-flex align-center gap-4">
                                            <BriefcaseIcon />
                                            <span>{job.company}</span>
                                            <span style={{ marginLeft: '8px' }}><LocationIcon /></span>
                                            <span>{job.location}</span>
                                            {job.salary && (
                                                <>
                                                    <span style={{ marginLeft: '8px' }}><DollarIcon /></span>
                                                    <span>{job.salary}</span>
                                                </>
                                            )}
                                        </div>
                                    </div>
                                ))
                            ) : (
                                <div className="empty-state">
                                    <UserIcon />
                                    <p>No jobs yet. Run the scraper to get started.</p>
                                </div>
                            )}
                        </CardBody>
                    </Card>
                </div>

                {/* Sidebar */}
                <div className="sidebar">
                    {/* Active Searches */}
                    <Card>
                        <CardHeader>Active Searches</CardHeader>
                        <CardBody noPadding>
                            {configs.length > 0 ? (
                                configs.map(config => (
                                    <div key={config.id} className="config-item">
                                        <div className="d-flex justify-between align-center" style={{ marginBottom: '8px' }}>
                                            <h6 style={{ fontWeight: 600, fontSize: '0.9375rem', margin: 0 }}>{config.name}</h6>
                                            <span className="status-badge" style={{ background: 'rgba(16, 185, 129, 0.12)', color: '#10b981' }}>
                                                Active
                                            </span>
                                        </div>
                                        <p className="text-muted small" style={{ marginBottom: '4px' }}>
                                            <code>{config.keywords}</code> in {config.location}
                                        </p>
                                        {config.employment_types && (
                                            <p className="small text-muted" style={{ margin: 0 }}>
                                                Type: {config.employment_types}
                                            </p>
                                        )}
                                    </div>
                                ))
                            ) : (
                                <div className="empty-state" style={{ padding: '40px 24px' }}>
                                    <SearchIcon size={40} />
                                    <p style={{ fontSize: '0.875rem' }}>No active searches configured</p>
                                </div>
                            )}
                        </CardBody>
                        <div style={{ padding: '20px 24px', borderTop: '1px solid var(--border-color)' }}>
                            <Button to="/configs" variant="secondary" style={{ width: '100%', justifyContent: 'center' }}>
                                Manage Searches
                            </Button>
                        </div>
                    </Card>

                    {/* Recent Activity */}
                    <Card>
                        <CardHeader>Recent Activity</CardHeader>
                        <CardBody>
                            <p className="text-muted small">Activity tracking coming soon...</p>
                        </CardBody>
                    </Card>
                </div>
            </div>
        </>
    );
}

export default Dashboard;
