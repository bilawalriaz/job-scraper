import { useState, useEffect, useCallback, useRef } from 'react';
import { getCV, uploadCV, deleteCV } from '../api/client';
import { Card, CardHeader, CardBody } from '../components/Card';
import Button from '../components/Button';
import Spinner from '../components/Spinner';
import { UploadIcon, DeleteIcon, CheckIcon } from '../components/Icons';

function CVUploader({ onUpload, uploading }) {
    const fileInputRef = useRef(null);
    const [dragOver, setDragOver] = useState(false);

    const handleDrop = useCallback((e) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file && file.name.toLowerCase().endsWith('.docx')) {
            onUpload(file);
        } else {
            alert('Please upload a .docx file');
        }
    }, [onUpload]);

    const handleFileSelect = (e) => {
        const file = e.target.files[0];
        if (file) {
            onUpload(file);
        }
    };

    return (
        <div
            className={`cv-uploader ${dragOver ? 'drag-over' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
                border: '2px dashed var(--border-color)',
                borderRadius: 'var(--radius-lg)',
                padding: '3rem',
                textAlign: 'center',
                cursor: 'pointer',
                background: dragOver ? 'var(--bg-secondary)' : 'transparent',
                transition: 'all 0.2s'
            }}
        >
            <input
                ref={fileInputRef}
                type="file"
                accept=".docx"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
            />
            {uploading ? (
                <>
                    <Spinner size={40} />
                    <p style={{ marginTop: '1rem', color: 'var(--text-secondary)' }}>
                        Uploading and parsing CV...
                    </p>
                </>
            ) : (
                <>
                    <UploadIcon size={48} />
                    <p style={{ marginTop: '1rem', fontWeight: 600 }}>
                        Drop your CV here or click to upload
                    </p>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                        Only .docx files are supported
                    </p>
                </>
            )}
        </div>
    );
}

function CVSummary({ cv }) {
    const parsed = cv.parsed_data || {};
    const personal = parsed.personal_info || {};
    const skills = parsed.skills || {};
    const experience = parsed.experience || [];

    return (
        <div className="cv-summary">
            {/* Personal Info */}
            {personal.name && (
                <div style={{ marginBottom: '1.5rem' }}>
                    <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>{personal.name}</h3>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                        {[personal.email, personal.phone, personal.location].filter(Boolean).join(' | ')}
                    </div>
                </div>
            )}

            {/* Summary */}
            {parsed.summary && (
                <div style={{ marginBottom: '1.5rem' }}>
                    <h4 style={{ fontSize: '0.875rem', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                        Summary
                    </h4>
                    <p style={{ lineHeight: 1.6 }}>{parsed.summary}</p>
                </div>
            )}

            {/* Skills */}
            {(skills.technical?.length > 0 || skills.certifications?.length > 0) && (
                <div style={{ marginBottom: '1.5rem' }}>
                    <h4 style={{ fontSize: '0.875rem', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                        Skills
                    </h4>
                    {skills.technical?.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.5rem' }}>
                            {skills.technical.map((skill, i) => (
                                <span key={i} className="tag" style={{
                                    background: 'var(--bg-secondary)',
                                    padding: '0.25rem 0.75rem',
                                    borderRadius: 'var(--radius-full)',
                                    fontSize: '0.875rem'
                                }}>
                                    {skill}
                                </span>
                            ))}
                        </div>
                    )}
                    {skills.certifications?.length > 0 && (
                        <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                            <strong>Certifications:</strong> {skills.certifications.join(', ')}
                        </div>
                    )}
                </div>
            )}

            {/* Experience Preview */}
            {experience.length > 0 && (
                <div>
                    <h4 style={{ fontSize: '0.875rem', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                        Experience ({experience.length} roles)
                    </h4>
                    {experience.slice(0, 3).map((exp, i) => (
                        <div key={i} style={{
                            padding: '0.75rem',
                            background: 'var(--bg-secondary)',
                            borderRadius: 'var(--radius-md)',
                            marginBottom: '0.5rem'
                        }}>
                            <div style={{ fontWeight: 600 }}>{exp.title}</div>
                            <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                                {exp.company} {exp.dates && `| ${exp.dates}`}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function CVProfile() {
    const [cv, setCV] = useState(null);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);

    const loadCV = useCallback(async () => {
        try {
            const data = await getCV();
            setCV(data.cv);
        } catch (error) {
            console.error('Failed to load CV:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadCV();
    }, [loadCV]);

    const handleUpload = async (file) => {
        setUploading(true);
        try {
            const result = await uploadCV(file);
            if (result.success) {
                await loadCV();
            }
        } catch (error) {
            console.error('Upload failed:', error);
            alert('Upload failed: ' + error.message);
        } finally {
            setUploading(false);
        }
    };

    const handleDelete = async () => {
        if (!cv || !window.confirm('Delete your CV? This will also remove all match results.')) {
            return;
        }

        try {
            await deleteCV(cv.id);
            setCV(null);
        } catch (error) {
            console.error('Delete failed:', error);
        }
    };

    return (
        <>
            {/* Page Header */}
            <div className="page-header">
                <div>
                    <h1 className="page-title">My CV</h1>
                    <p className="page-subtitle">Upload your CV to enable job matching and tailored applications</p>
                </div>
                {cv && (
                    <Button variant="secondary" onClick={handleDelete} style={{ color: '#ef4444' }}>
                        <DeleteIcon /> Delete CV
                    </Button>
                )}
            </div>

            {loading ? (
                <div className="loading-state">
                    <Spinner size={40} />
                </div>
            ) : cv ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                    {/* CV Info */}
                    <Card>
                        <CardHeader>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <CheckIcon size={20} style={{ color: 'var(--success-color)' }} />
                                <span>CV Uploaded</span>
                            </div>
                        </CardHeader>
                        <CardBody>
                            <div style={{ marginBottom: '1rem' }}>
                                <strong>File:</strong> {cv.filename}
                            </div>
                            <div style={{ marginBottom: '1rem', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                                Uploaded: {new Date(cv.created_at).toLocaleDateString()}
                            </div>
                            <Button variant="primary" onClick={() => document.querySelector('.cv-uploader')?.click()}>
                                Replace CV
                            </Button>
                        </CardBody>
                    </Card>

                    {/* Parsed Summary */}
                    <Card>
                        <CardHeader>Parsed Content</CardHeader>
                        <CardBody>
                            <CVSummary cv={cv} />
                        </CardBody>
                    </Card>
                </div>
            ) : (
                <Card>
                    <CardBody>
                        <CVUploader onUpload={handleUpload} uploading={uploading} />
                    </CardBody>
                </Card>
            )}

            {/* Hidden uploader for replace functionality */}
            {cv && (
                <div style={{ display: 'none' }}>
                    <CVUploader onUpload={handleUpload} uploading={uploading} />
                </div>
            )}
        </>
    );
}

export default CVProfile;
