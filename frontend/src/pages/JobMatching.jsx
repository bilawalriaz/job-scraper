import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getCV, getMatchResults, batchMatchJobs } from '../api/client';
import { Card, CardHeader, CardBody } from '../components/Card';
import { Table, TableHead, TableBody, TableRow, TableHeader, TableCell } from '../components/Table';
import Button from '../components/Button';
import Spinner from '../components/Spinner';
import { PlayIcon, RefreshIcon } from '../components/Icons';

function MatchScoreBadge({ score, recommendation }) {
    let bgColor, textColor;

    if (score >= 80) {
        bgColor = '#dcfce7';
        textColor = '#166534';
    } else if (score >= 60) {
        bgColor = '#fef9c3';
        textColor = '#854d0e';
    } else if (score >= 40) {
        bgColor = '#fed7aa';
        textColor = '#9a3412';
    } else {
        bgColor = '#fee2e2';
        textColor = '#991b1b';
    }

    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '3rem',
                height: '2rem',
                borderRadius: 'var(--radius-md)',
                background: bgColor,
                color: textColor,
                fontWeight: 700,
                fontSize: '0.875rem'
            }}>
                {Math.round(score)}
            </span>
            {recommendation && (
                <span style={{
                    fontSize: '0.75rem',
                    color: recommendation === 'Apply' ? '#166534' :
                           recommendation === 'Consider' ? '#854d0e' : '#6b7280'
                }}>
                    {recommendation}
                </span>
            )}
        </div>
    );
}

function MatchDetails({ match }) {
    const [expanded, setExpanded] = useState(false);

    return (
        <>
            <TableRow
                onClick={() => setExpanded(!expanded)}
                style={{ cursor: 'pointer' }}
            >
                <TableCell>
                    <Link
                        to={`/jobs/${match.job_id}`}
                        style={{ color: 'var(--text-primary)', fontWeight: 500 }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        {match.title}
                    </Link>
                </TableCell>
                <TableCell>{match.company}</TableCell>
                <TableCell>{match.location}</TableCell>
                <TableCell>
                    <MatchScoreBadge
                        score={match.match_score}
                        recommendation={match.recommendation}
                    />
                </TableCell>
                <TableCell>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        {match.skills_matched?.length || 0} matched
                    </span>
                </TableCell>
            </TableRow>
            {expanded && (
                <TableRow>
                    <TableCell colSpan={5} style={{ background: 'var(--bg-secondary)', padding: '1rem' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                            <div>
                                <h4 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem', color: '#166534' }}>
                                    Skills Matched
                                </h4>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
                                    {(match.skills_matched || []).map((skill, i) => (
                                        <span key={i} style={{
                                            background: '#dcfce7',
                                            color: '#166534',
                                            padding: '0.125rem 0.5rem',
                                            borderRadius: 'var(--radius-full)',
                                            fontSize: '0.75rem'
                                        }}>
                                            {skill}
                                        </span>
                                    ))}
                                </div>
                            </div>
                            <div>
                                <h4 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem', color: '#991b1b' }}>
                                    Skills Missing
                                </h4>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
                                    {(match.skills_missing || []).map((skill, i) => (
                                        <span key={i} style={{
                                            background: '#fee2e2',
                                            color: '#991b1b',
                                            padding: '0.125rem 0.5rem',
                                            borderRadius: 'var(--radius-full)',
                                            fontSize: '0.75rem'
                                        }}>
                                            {skill}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </div>
                        {match.tailoring_tips?.length > 0 && (
                            <div style={{ marginTop: '1rem' }}>
                                <h4 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                                    Tailoring Tips
                                </h4>
                                <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                                    {match.tailoring_tips.map((tip, i) => (
                                        <li key={i}>{tip}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </TableCell>
                </TableRow>
            )}
        </>
    );
}

function JobMatching() {
    const [cv, setCV] = useState(null);
    const [matches, setMatches] = useState([]);
    const [stats, setStats] = useState({});
    const [loading, setLoading] = useState(true);
    const [analyzing, setAnalyzing] = useState(false);
    const [filter, setFilter] = useState({ min_score: 0, recommendation: '' });

    const loadData = useCallback(async () => {
        try {
            const [cvData, matchData] = await Promise.all([
                getCV(),
                getMatchResults(filter)
            ]);
            setCV(cvData.cv);
            setMatches(matchData.matches || []);
            setStats(matchData.stats || {});
        } catch (error) {
            console.error('Failed to load data:', error);
        } finally {
            setLoading(false);
        }
    }, [filter]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const handleAnalyze = async () => {
        setAnalyzing(true);
        try {
            await batchMatchJobs({ limit: 50 });
            await loadData();
        } catch (error) {
            console.error('Analysis failed:', error);
            alert('Analysis failed: ' + error.message);
        } finally {
            setAnalyzing(false);
        }
    };

    if (loading) {
        return (
            <div className="loading-state">
                <Spinner size={40} />
            </div>
        );
    }

    if (!cv) {
        return (
            <>
                <div className="page-header">
                    <div>
                        <h1 className="page-title">Job Matching</h1>
                        <p className="page-subtitle">Find jobs that match your skills</p>
                    </div>
                </div>
                <Card>
                    <CardBody>
                        <div className="empty-state">
                            <p style={{ marginBottom: '1rem' }}>You need to upload your CV first</p>
                            <Link to="/cv">
                                <Button variant="primary">Upload CV</Button>
                            </Link>
                        </div>
                    </CardBody>
                </Card>
            </>
        );
    }

    return (
        <>
            {/* Page Header */}
            <div className="page-header">
                <div>
                    <h1 className="page-title">Job Matching</h1>
                    <p className="page-subtitle">
                        {stats.total || 0} jobs analyzed | Avg score: {Math.round(stats.avg_score || 0)}
                    </p>
                </div>
                <Button
                    variant="primary"
                    onClick={handleAnalyze}
                    loading={analyzing}
                    disabled={analyzing}
                >
                    <PlayIcon /> Analyze New Jobs
                </Button>
            </div>

            {/* Stats Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
                <Card>
                    <CardBody style={{ textAlign: 'center', padding: '1rem' }}>
                        <div style={{ fontSize: '2rem', fontWeight: 700, color: '#166534' }}>
                            {stats.apply_count || 0}
                        </div>
                        <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Apply</div>
                    </CardBody>
                </Card>
                <Card>
                    <CardBody style={{ textAlign: 'center', padding: '1rem' }}>
                        <div style={{ fontSize: '2rem', fontWeight: 700, color: '#854d0e' }}>
                            {stats.consider_count || 0}
                        </div>
                        <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Consider</div>
                    </CardBody>
                </Card>
                <Card>
                    <CardBody style={{ textAlign: 'center', padding: '1rem' }}>
                        <div style={{ fontSize: '2rem', fontWeight: 700, color: '#6b7280' }}>
                            {stats.skip_count || 0}
                        </div>
                        <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Skip</div>
                    </CardBody>
                </Card>
                <Card>
                    <CardBody style={{ textAlign: 'center', padding: '1rem' }}>
                        <div style={{ fontSize: '2rem', fontWeight: 700 }}>
                            {stats.total || 0}
                        </div>
                        <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Total</div>
                    </CardBody>
                </Card>
            </div>

            {/* Filters */}
            <Card style={{ marginBottom: '1.5rem' }}>
                <CardBody>
                    <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                        <div className="form-group" style={{ margin: 0, flex: 1 }}>
                            <label className="form-label" style={{ marginBottom: '0.25rem' }}>Min Score</label>
                            <input
                                type="number"
                                className="form-control"
                                value={filter.min_score}
                                onChange={(e) => setFilter(f => ({ ...f, min_score: parseInt(e.target.value) || 0 }))}
                                min="0"
                                max="100"
                            />
                        </div>
                        <div className="form-group" style={{ margin: 0, flex: 1 }}>
                            <label className="form-label" style={{ marginBottom: '0.25rem' }}>Recommendation</label>
                            <select
                                className="form-select"
                                value={filter.recommendation}
                                onChange={(e) => setFilter(f => ({ ...f, recommendation: e.target.value }))}
                            >
                                <option value="">All</option>
                                <option value="Apply">Apply</option>
                                <option value="Consider">Consider</option>
                                <option value="Skip">Skip</option>
                            </select>
                        </div>
                        <Button
                            variant="secondary"
                            onClick={loadData}
                            style={{ marginTop: '1.25rem' }}
                        >
                            <RefreshIcon /> Refresh
                        </Button>
                    </div>
                </CardBody>
            </Card>

            {/* Results Table */}
            <Card>
                {matches.length > 0 ? (
                    <Table>
                        <TableHead>
                            <TableRow>
                                <TableHeader>Job Title</TableHeader>
                                <TableHeader>Company</TableHeader>
                                <TableHeader>Location</TableHeader>
                                <TableHeader>Score</TableHeader>
                                <TableHeader>Skills</TableHeader>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {matches.map((match) => (
                                <MatchDetails key={match.id} match={match} />
                            ))}
                        </TableBody>
                    </Table>
                ) : (
                    <div className="empty-state">
                        <p>No matches yet. Click "Analyze New Jobs" to start matching.</p>
                    </div>
                )}
            </Card>
        </>
    );
}

export default JobMatching;
