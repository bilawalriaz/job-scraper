import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getJob, updateJob, deleteJob } from '../api/client';
import { Card, CardHeader, CardBody } from '../components/Card';
import Button from '../components/Button';
import Spinner from '../components/Spinner';
import { StatusBadge } from '../components/StatusBadge';
import { ExternalLinkIcon, EditIcon, DeleteIcon, CheckIcon, BriefcaseIcon, LocationIcon } from '../components/Icons';

function JobDetail() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [job, setJob] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [descriptionExpanded, setDescriptionExpanded] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [editForm, setEditForm] = useState({});

    useEffect(() => {
        loadJob();
    }, [id]);

    const loadJob = async () => {
        try {
            const data = await getJob(id);
            setJob(data);
            setEditForm({
                title: data.title,
                company: data.company,
                location: data.location,
                salary: data.salary || '',
                notes: data.notes || '',
                status: data.status || 'new'
            });
        } catch (error) {
            console.error('Failed to load job:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleStatusChange = async (newStatus) => {
        setSaving(true);
        try {
            await updateJob(id, { status: newStatus });
            setJob(prev => ({ ...prev, status: newStatus }));
        } catch (error) {
            console.error('Failed to update status:', error);
        } finally {
            setSaving(false);
        }
    };

    const handleToggleApplied = async () => {
        setSaving(true);
        try {
            const newApplied = !job.is_applied;
            await updateJob(id, { is_applied: newApplied });
            setJob(prev => ({ ...prev, is_applied: newApplied }));
        } catch (error) {
            console.error('Failed to toggle applied:', error);
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!window.confirm('Are you sure you want to delete this job?')) return;

        try {
            await deleteJob(id);
            navigate('/jobs');
        } catch (error) {
            console.error('Failed to delete job:', error);
        }
    };

    const handleSaveEdit = async () => {
        setSaving(true);
        try {
            await updateJob(id, editForm);
            setJob(prev => ({ ...prev, ...editForm }));
            setIsEditing(false);
        } catch (error) {
            console.error('Failed to update job:', error);
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="loading-state">
                <Spinner size={40} />
            </div>
        );
    }

    if (!job) {
        return (
            <div className="empty-state">
                <p>Job not found</p>
                <Button to="/jobs" variant="secondary">Back to Jobs</Button>
            </div>
        );
    }

    return (
        <>
            {/* Breadcrumb */}
            <div className="breadcrumb">
                <Link to="/">Dashboard</Link>
                <span className="breadcrumb-separator">/</span>
                <Link to="/jobs">Jobs</Link>
                <span className="breadcrumb-separator">/</span>
                <span className="breadcrumb-current">
                    {job.title.length > 50 ? `${job.title.substring(0, 50)}...` : job.title}
                </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
                {/* Main Content */}
                <div>
                    <Card>
                        <div style={{ padding: '32px' }}>
                            {isEditing ? (
                                // Edit Form
                                <>
                                    <div className="form-group">
                                        <label className="form-label">Title</label>
                                        <input
                                            type="text"
                                            className="form-control"
                                            value={editForm.title}
                                            onChange={(e) => setEditForm(prev => ({ ...prev, title: e.target.value }))}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label className="form-label">Company</label>
                                        <input
                                            type="text"
                                            className="form-control"
                                            value={editForm.company}
                                            onChange={(e) => setEditForm(prev => ({ ...prev, company: e.target.value }))}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label className="form-label">Location</label>
                                        <input
                                            type="text"
                                            className="form-control"
                                            value={editForm.location}
                                            onChange={(e) => setEditForm(prev => ({ ...prev, location: e.target.value }))}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label className="form-label">Salary</label>
                                        <input
                                            type="text"
                                            className="form-control"
                                            value={editForm.salary}
                                            onChange={(e) => setEditForm(prev => ({ ...prev, salary: e.target.value }))}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label className="form-label">Notes</label>
                                        <textarea
                                            className="form-control"
                                            rows={4}
                                            value={editForm.notes}
                                            onChange={(e) => setEditForm(prev => ({ ...prev, notes: e.target.value }))}
                                        />
                                    </div>
                                    <div className="d-flex gap-3">
                                        <Button variant="primary" onClick={handleSaveEdit} loading={saving}>
                                            Save Changes
                                        </Button>
                                        <Button variant="secondary" onClick={() => setIsEditing(false)}>
                                            Cancel
                                        </Button>
                                    </div>
                                </>
                            ) : (
                                // View Mode
                                <>
                                    {/* Header */}
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
                                        <div style={{ flex: 1 }}>
                                            <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: '8px', letterSpacing: '-0.02em' }}>
                                                {job.title}
                                            </h1>
                                            <div className="d-flex align-center gap-4 text-secondary" style={{ fontSize: '0.9375rem' }}>
                                                <BriefcaseIcon size={16} />
                                                <span>{job.company}</span>
                                                <LocationIcon size={16} />
                                                <span>{job.location}</span>
                                            </div>
                                        </div>
                                        <StatusBadge status={job.status} style={{ fontSize: '0.875rem' }} />
                                    </div>

                                    {/* Details Grid */}
                                    <div className="detail-grid">
                                        <div className="detail-item">
                                            <small>Salary</small>
                                            <p>{job.salary || <span className="text-muted">Not specified</span>}</p>
                                        </div>
                                        <div className="detail-item">
                                            <small>Posted</small>
                                            <p>{job.posted_date || 'Unknown'}</p>
                                        </div>
                                        <div className="detail-item">
                                            <small>Employment Type</small>
                                            <p>{job.employment_type ? job.employment_type.charAt(0).toUpperCase() + job.employment_type.slice(1) : 'Not specified'}</p>
                                        </div>
                                        <div className="detail-item">
                                            <small>Source</small>
                                            <p>{job.source ? job.source.charAt(0).toUpperCase() + job.source.slice(1) : 'Unknown'}</p>
                                        </div>
                                    </div>

                                    {/* Description */}
                                    <div style={{ marginBottom: '32px' }}>
                                        <h3 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '16px' }}>Description</h3>
                                        <div
                                            className={`job-description ${descriptionExpanded ? 'expanded' : ''}`}
                                            dangerouslySetInnerHTML={{ __html: job.description?.replace(/\n/g, '<br>') || 'No description available' }}
                                        />
                                        <button
                                            className="show-more-btn"
                                            onClick={() => setDescriptionExpanded(!descriptionExpanded)}
                                        >
                                            {descriptionExpanded ? 'Show Less' : 'Show More'}
                                        </button>
                                    </div>

                                    {/* Actions */}
                                    <div className="d-flex gap-3">
                                        {job.url && (
                                            <Button variant="primary" href={job.url}>
                                                <ExternalLinkIcon /> View Original
                                            </Button>
                                        )}
                                        <Button variant="secondary" onClick={() => setIsEditing(true)}>
                                            <EditIcon /> Edit
                                        </Button>
                                    </div>
                                </>
                            )}
                        </div>
                    </Card>
                </div>

                {/* Sidebar */}
                <div>
                    {/* Status Card */}
                    <Card>
                        <CardHeader>Status & Actions</CardHeader>
                        <div style={{ padding: '20px' }}>
                            <div style={{ marginBottom: '20px' }}>
                                <label className="form-label">Status</label>
                                <select
                                    className="form-select"
                                    value={job.status || 'new'}
                                    onChange={(e) => handleStatusChange(e.target.value)}
                                    disabled={saving}
                                >
                                    <option value="new">New</option>
                                    <option value="interested">Interested</option>
                                    <option value="applied">Applied</option>
                                    <option value="interviewing">Interviewing</option>
                                    <option value="offer">Offer</option>
                                    <option value="rejected">Rejected</option>
                                    <option value="archived">Archived</option>
                                </select>
                            </div>

                            <Button
                                variant={job.is_applied ? 'secondary' : 'success'}
                                style={{ width: '100%', marginBottom: '12px' }}
                                onClick={handleToggleApplied}
                                loading={saving}
                            >
                                <CheckIcon /> {job.is_applied ? 'Applied' : 'Mark Applied'}
                            </Button>

                            <Button
                                variant="danger"
                                style={{ width: '100%' }}
                                onClick={handleDelete}
                            >
                                <DeleteIcon /> Delete
                            </Button>
                        </div>
                    </Card>

                    {/* Notes Card */}
                    <Card>
                        <CardHeader>Notes</CardHeader>
                        <div style={{ padding: '20px' }}>
                            <p style={{ fontSize: '0.9375rem', color: 'var(--text-secondary)', marginBottom: '12px', minHeight: '60px' }}>
                                {job.notes || 'No notes'}
                            </p>
                            <Button variant="secondary" size="sm" onClick={() => setIsEditing(true)}>
                                Add/Edit Notes
                            </Button>
                        </div>
                    </Card>
                </div>
            </div>
        </>
    );
}

export default JobDetail;
