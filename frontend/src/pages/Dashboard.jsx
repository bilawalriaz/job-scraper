import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getStats, getJobs, getConfigs, getRateLimitStatus, resetRateLimit, getSchedulerStatus, updateSchedulerConfig, runSchedulerTask } from '../api/client';
import { Card, CardHeader, CardBody } from '../components/Card';
import Button from '../components/Button';
import Console from '../components/Console';
import Spinner from '../components/Spinner';
import { StatusBadge } from '../components/StatusBadge';
import { PlayIcon, BriefcaseIcon, LocationIcon, DollarIcon, SearchIcon, UserIcon, RefreshIcon, DownloadIcon } from '../components/Icons';

function Dashboard() {
    const [stats, setStats] = useState(null);
    const [recentJobs, setRecentJobs] = useState([]);
    const [configs, setConfigs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [rateLimitStatus, setRateLimitStatus] = useState(null);
    const [resettingRateLimit, setResettingRateLimit] = useState(false);

    // Scheduler state
    const [schedulerStatus, setSchedulerStatus] = useState(null);
    const [showSchedulerSettings, setShowSchedulerSettings] = useState(false);
    const [schedulerConfig, setSchedulerConfig] = useState({
        enabled: false,
        scrape_interval_minutes: 60,
        description_interval_minutes: 15,
        llm_interval_minutes: 10,
        scrape_enabled: true,
        description_enabled: true,
        llm_enabled: true,
    });

    const loadData = useCallback(async () => {
        try {
            const [statsData, jobsData, configsData, rateLimitData, schedulerData] = await Promise.all([
                getStats(),
                getJobs({ per_page: 10 }),
                getConfigs(),
                getRateLimitStatus(),
                getSchedulerStatus().catch(() => null)
            ]);
            setStats(statsData);
            setRecentJobs(jobsData.jobs || []);
            setConfigs(configsData.configs || []);
            setRateLimitStatus(rateLimitData);
            if (schedulerData) {
                setSchedulerStatus(schedulerData);
                setSchedulerConfig(schedulerData.config);
            }
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    // Check if any task is running
    const isAnyTaskRunning = schedulerStatus?.tasks && Object.values(schedulerStatus.tasks).some(t => t.status === 'running');

    useEffect(() => {
        loadData();
        // Poll more frequently when tasks are running
        const pollInterval = isAnyTaskRunning ? 1000 : 3000;
        const interval = setInterval(() => {
            Promise.all([
                getStats().then(setStats),
                getRateLimitStatus().then(setRateLimitStatus),
                getSchedulerStatus().then(data => {
                    setSchedulerStatus(data);
                    // Don't overwrite local config changes
                    if (!showSchedulerSettings) {
                        setSchedulerConfig(data.config);
                    }
                }).catch(() => { })
            ]).catch(console.error);
        }, pollInterval);
        return () => clearInterval(interval);
    }, [loadData, isAnyTaskRunning, showSchedulerSettings]);

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

    const handleRunTask = async (taskName) => {
        try {
            await runSchedulerTask(taskName);
        } catch (error) {
            console.error(`Failed to run task ${taskName}:`, error);
        }
    };

    const handleToggleScheduler = async () => {
        try {
            const newEnabled = !schedulerConfig.enabled;
            await updateSchedulerConfig({ enabled: newEnabled });
            setSchedulerConfig(prev => ({ ...prev, enabled: newEnabled }));
        } catch (error) {
            console.error('Failed to toggle scheduler:', error);
        }
    };

    const handleSaveSchedulerConfig = async () => {
        try {
            await updateSchedulerConfig(schedulerConfig);
            setShowSchedulerSettings(false);
        } catch (error) {
            console.error('Failed to save scheduler config:', error);
        }
    };

    // Check if any source is rate limited
    const isAnyRateLimited = rateLimitStatus && Object.values(rateLimitStatus).some(s => s.limited);

    // Get task states and counts
    const tasks = schedulerStatus?.tasks || {};
    const counts = schedulerStatus?.counts || {};

    const scrapeRunning = tasks.scrape?.status === 'running';
    const descriptionsRunning = tasks.descriptions?.status === 'running';
    const llmRunning = tasks.llm?.status === 'running';

    const partialCount = counts.partial_descriptions || 0;
    const llmPendingCount = counts.llm_pending || 0;

    // Helper to get task button text
    const getTaskButtonText = (taskName, defaultText, runningText, count) => {
        const task = tasks[taskName];
        if (task?.status === 'running') {
            const progress = task.progress || 0;
            const total = task.total || count;
            return total > 0 ? `${runningText} ${progress}/${total}` : runningText;
        }
        return count > 0 ? `${defaultText} ${count}` : defaultText;
    };

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
                <div className="page-header-actions">
                    {(llmPendingCount > 0 || llmRunning) && (
                        <Button
                            variant="secondary"
                            onClick={() => handleRunTask('llm')}
                            loading={llmRunning}
                            disabled={llmRunning}
                            style={{ marginRight: '8px' }}
                        >
                            <SearchIcon />
                            {getTaskButtonText('llm', 'Process with AI', 'Processing...', llmPendingCount)}
                        </Button>
                    )}
                    {(partialCount > 0 || descriptionsRunning) && (
                        <Button
                            variant="secondary"
                            onClick={() => handleRunTask('descriptions')}
                            loading={descriptionsRunning}
                            disabled={descriptionsRunning}
                            style={{ marginRight: '8px' }}
                        >
                            <DownloadIcon />
                            {getTaskButtonText('descriptions', 'Refresh Partial', 'Refreshing...', partialCount)}
                        </Button>
                    )}
                    <Button
                        variant="primary"
                        onClick={() => handleRunTask('scrape')}
                        loading={scrapeRunning}
                        disabled={scrapeRunning}
                    >
                        <PlayIcon />
                        {scrapeRunning ? 'Scraping...' : 'Run Scraper'}
                    </Button>
                </div>
            </div>

            {/* Task Progress */}
            {isAnyTaskRunning && (
                <div className="alert alert-info">
                    {Object.entries(tasks).filter(([, t]) => t.status === 'running').map(([name, task]) => (
                        <div key={name} style={{ marginBottom: '4px' }}>
                            <strong>{name}:</strong> {task.message || 'Running...'}
                            {task.total > 0 && (
                                <span style={{ marginLeft: '8px' }}>
                                    ({task.progress}/{task.total})
                                </span>
                            )}
                        </div>
                    ))}
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
                    {/* Scheduler Settings */}
                    <Card>
                        <CardHeader actions={
                            <button
                                onClick={handleToggleScheduler}
                                className={`toggle-switch ${schedulerConfig.enabled ? 'active' : ''}`}
                                title={schedulerConfig.enabled ? 'Disable auto-scheduling' : 'Enable auto-scheduling'}
                            >
                                <span className="toggle-slider" />
                            </button>
                        }>
                            Auto Scheduler
                        </CardHeader>
                        <CardBody>
                            {schedulerConfig.enabled ? (
                                <p className="text-muted small" style={{ marginBottom: '12px' }}>
                                    Pipeline runs automatically: Scrape every {schedulerConfig.scrape_interval_minutes}m,
                                    descriptions every {schedulerConfig.description_interval_minutes}m,
                                    AI every {schedulerConfig.llm_interval_minutes}m
                                </p>
                            ) : (
                                <p className="text-muted small" style={{ marginBottom: '12px' }}>
                                    Auto-scheduling is disabled. Use buttons above to run tasks manually.
                                </p>
                            )}

                            {showSchedulerSettings ? (
                                <div className="scheduler-settings">
                                    <div className="form-group" style={{ marginBottom: '12px' }}>
                                        <label style={{ fontSize: '0.8125rem', fontWeight: 500, display: 'block', marginBottom: '4px' }}>
                                            Scrape Interval (minutes)
                                        </label>
                                        <input
                                            type="number"
                                            min="5"
                                            value={schedulerConfig.scrape_interval_minutes}
                                            onChange={e => setSchedulerConfig(prev => ({ ...prev, scrape_interval_minutes: parseInt(e.target.value) || 60 }))}
                                            style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)' }}
                                        />
                                    </div>
                                    <div className="form-group" style={{ marginBottom: '12px' }}>
                                        <label style={{ fontSize: '0.8125rem', fontWeight: 500, display: 'block', marginBottom: '4px' }}>
                                            Description Fetch Interval (minutes)
                                        </label>
                                        <input
                                            type="number"
                                            min="5"
                                            value={schedulerConfig.description_interval_minutes}
                                            onChange={e => setSchedulerConfig(prev => ({ ...prev, description_interval_minutes: parseInt(e.target.value) || 15 }))}
                                            style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)' }}
                                        />
                                    </div>
                                    <div className="form-group" style={{ marginBottom: '12px' }}>
                                        <label style={{ fontSize: '0.8125rem', fontWeight: 500, display: 'block', marginBottom: '4px' }}>
                                            AI Processing Interval (minutes)
                                        </label>
                                        <input
                                            type="number"
                                            min="5"
                                            value={schedulerConfig.llm_interval_minutes}
                                            onChange={e => setSchedulerConfig(prev => ({ ...prev, llm_interval_minutes: parseInt(e.target.value) || 10 }))}
                                            style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)' }}
                                        />
                                    </div>
                                    <div className="d-flex gap-2" style={{ marginTop: '16px' }}>
                                        <Button variant="primary" size="sm" onClick={handleSaveSchedulerConfig} style={{ flex: 1 }}>
                                            Save
                                        </Button>
                                        <Button variant="secondary" size="sm" onClick={() => setShowSchedulerSettings(false)} style={{ flex: 1 }}>
                                            Cancel
                                        </Button>
                                    </div>
                                </div>
                            ) : (
                                <Button
                                    variant="secondary"
                                    size="sm"
                                    onClick={() => setShowSchedulerSettings(true)}
                                    style={{ width: '100%' }}
                                >
                                    Configure Intervals
                                </Button>
                            )}
                        </CardBody>
                    </Card>

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
                </div>
            </div>

            <style>{`
                .toggle-switch {
                    position: relative;
                    width: 44px;
                    height: 24px;
                    background: var(--bg-tertiary);
                    border: none;
                    border-radius: 12px;
                    cursor: pointer;
                    transition: background 0.2s;
                }
                .toggle-switch.active {
                    background: #10b981;
                }
                .toggle-slider {
                    position: absolute;
                    top: 2px;
                    left: 2px;
                    width: 20px;
                    height: 20px;
                    background: white;
                    border-radius: 50%;
                    transition: transform 0.2s;
                }
                .toggle-switch.active .toggle-slider {
                    transform: translateX(20px);
                }
                .alert-info {
                    background: rgba(59, 130, 246, 0.1);
                    border: 1px solid rgba(59, 130, 246, 0.3);
                    color: #3b82f6;
                    padding: 12px 16px;
                    border-radius: 8px;
                    margin-bottom: 16px;
                }
            `}</style>
        </>
    );
}

export default Dashboard;
