import { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getJobs } from '../api/client';
import { Card, CardBody } from '../components/Card';
import { Table, TableHead, TableBody, TableRow, TableHeader, TableCell } from '../components/Table';
import { StatusBadge, TypeBadge } from '../components/StatusBadge';
import Spinner from '../components/Spinner';
import Pagination from '../components/Pagination';
import { EditIcon, BriefcaseIcon } from '../components/Icons';

function Jobs() {
    const [searchParams, setSearchParams] = useSearchParams();
    const [jobs, setJobs] = useState([]);
    const [total, setTotal] = useState(0);
    const [totalPages, setTotalPages] = useState(1);
    const [loading, setLoading] = useState(true);

    // Get filter values from URL
    const page = parseInt(searchParams.get('page') || '1');
    const status = searchParams.get('status') || '';
    const employmentType = searchParams.get('employment_type') || '';
    const source = searchParams.get('source') || '';
    const search = searchParams.get('search') || '';

    const loadJobs = useCallback(async () => {
        setLoading(true);
        try {
            const data = await getJobs({
                page,
                per_page: 20,
                status,
                employment_type: employmentType,
                source,
                search
            });
            setJobs(data.jobs || []);
            setTotal(data.total || 0);
            setTotalPages(data.total_pages || 1);
        } catch (error) {
            console.error('Failed to load jobs:', error);
        } finally {
            setLoading(false);
        }
    }, [page, status, employmentType, source, search]);

    useEffect(() => {
        loadJobs();
    }, [loadJobs]);

    const updateFilter = (key, value) => {
        const newParams = new URLSearchParams(searchParams);
        if (value) {
            newParams.set(key, value);
        } else {
            newParams.delete(key);
        }
        // Reset to page 1 when filters change
        if (key !== 'page') {
            newParams.set('page', '1');
        }
        setSearchParams(newParams);
    };

    const handlePageChange = (newPage) => {
        updateFilter('page', newPage.toString());
    };

    return (
        <>
            {/* Page Header */}
            <div className="page-header">
                <div>
                    <h1 className="page-title">Jobs</h1>
                    <p className="page-subtitle">Browse and manage your job listings</p>
                </div>
            </div>

            {/* Filters */}
            <Card>
                <CardBody>
                    <div className="filters-grid">
                        <div>
                            <label className="form-label">Search</label>
                            <input
                                type="text"
                                className="form-control"
                                placeholder="Search jobs..."
                                value={search}
                                onChange={(e) => updateFilter('search', e.target.value)}
                            />
                        </div>
                        <div>
                            <label className="form-label">Status</label>
                            <select
                                className="form-select"
                                value={status}
                                onChange={(e) => updateFilter('status', e.target.value)}
                            >
                                <option value="">All Status</option>
                                <option value="new">New</option>
                                <option value="interested">Interested</option>
                                <option value="applied">Applied</option>
                                <option value="interviewing">Interviewing</option>
                                <option value="offer">Offer</option>
                                <option value="rejected">Rejected</option>
                                <option value="archived">Archived</option>
                            </select>
                        </div>
                        <div>
                            <label className="form-label">Employment Type</label>
                            <select
                                className="form-select"
                                value={employmentType}
                                onChange={(e) => updateFilter('employment_type', e.target.value)}
                            >
                                <option value="">All Types</option>
                                <option value="contract">Contract</option>
                                <option value="permanent">Permanent</option>
                                <option value="WHF">Work From Home</option>
                            </select>
                        </div>
                        <div>
                            <label className="form-label">Source</label>
                            <select
                                className="form-select"
                                value={source}
                                onChange={(e) => updateFilter('source', e.target.value)}
                            >
                                <option value="">All Sources</option>
                                <option value="totaljobs">TotalJobs</option>
                            </select>
                        </div>
                        <div>
                            <div className="text-muted small" style={{ paddingBottom: '2px' }}>
                                Showing {jobs.length} of {total} jobs
                            </div>
                        </div>
                    </div>
                </CardBody>
            </Card>

            {/* Jobs Table */}
            <Card>
                {loading ? (
                    <div className="loading-state">
                        <Spinner size={40} />
                    </div>
                ) : jobs.length > 0 ? (
                    <Table>
                        <TableHead>
                            <TableRow>
                                <TableHeader width="30%">Title</TableHeader>
                                <TableHeader width="20%">Company</TableHeader>
                                <TableHeader width="15%">Location</TableHeader>
                                <TableHeader width="15%">Salary</TableHeader>
                                <TableHeader width="10%">Type</TableHeader>
                                <TableHeader width="10%">Status</TableHeader>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {jobs.map(job => (
                                <TableRow key={job.id}>
                                    <TableCell>
                                        <Link to={`/jobs/${job.id}`} style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                                            {job.title}
                                        </Link>
                                        {job.is_edited && (
                                            <span style={{ marginLeft: '4px', color: 'var(--text-muted)', verticalAlign: 'middle' }}>
                                                <EditIcon size={12} />
                                            </span>
                                        )}
                                    </TableCell>
                                    <TableCell>{job.company}</TableCell>
                                    <TableCell>{job.location}</TableCell>
                                    <TableCell>{job.salary || '-'}</TableCell>
                                    <TableCell>
                                        <TypeBadge type={job.employment_type} />
                                    </TableCell>
                                    <TableCell>
                                        <StatusBadge status={job.status} />
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                ) : (
                    <div className="empty-state">
                        <BriefcaseIcon size={48} />
                        <p>No jobs found matching your filters</p>
                    </div>
                )}
            </Card>

            {/* Pagination */}
            <Pagination
                page={page}
                totalPages={totalPages}
                onPageChange={handlePageChange}
            />
        </>
    );
}

export default Jobs;
