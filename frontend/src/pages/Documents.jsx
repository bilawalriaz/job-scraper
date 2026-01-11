import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getDocuments, downloadDocument, deleteDocument } from '../api/client';
import { Card, CardHeader, CardBody } from '../components/Card';
import { Table, TableHead, TableBody, TableRow, TableHeader, TableCell } from '../components/Table';
import Button from '../components/Button';
import Spinner from '../components/Spinner';
import { DownloadIcon, DeleteIcon, DocumentIcon } from '../components/Icons';

function DocumentTypeBadge({ type }) {
    const isCV = type === 'cv';
    return (
        <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '0.25rem 0.75rem',
            borderRadius: 'var(--radius-full)',
            fontSize: '0.75rem',
            fontWeight: 500,
            background: isCV ? '#dbeafe' : '#f3e8ff',
            color: isCV ? '#1e40af' : '#7c3aed'
        }}>
            {isCV ? 'Tailored CV' : 'Cover Letter'}
        </span>
    );
}

function Documents() {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);

    const loadDocuments = useCallback(async () => {
        try {
            const data = await getDocuments();
            setDocuments(data.documents || []);
        } catch (error) {
            console.error('Failed to load documents:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadDocuments();
    }, [loadDocuments]);

    const handleDownload = (docId) => {
        downloadDocument(docId);
    };

    const handleDelete = async (docId) => {
        if (!window.confirm('Delete this document?')) return;

        try {
            await deleteDocument(docId);
            setDocuments(docs => docs.filter(d => d.id !== docId));
        } catch (error) {
            console.error('Delete failed:', error);
        }
    };

    return (
        <>
            {/* Page Header */}
            <div className="page-header">
                <div>
                    <h1 className="page-title">Generated Documents</h1>
                    <p className="page-subtitle">Tailored CVs and cover letters for your applications</p>
                </div>
            </div>

            <Card>
                {loading ? (
                    <div className="loading-state">
                        <Spinner size={40} />
                    </div>
                ) : documents.length > 0 ? (
                    <Table>
                        <TableHead>
                            <TableRow>
                                <TableHeader>Document</TableHeader>
                                <TableHeader>Job</TableHeader>
                                <TableHeader>Company</TableHeader>
                                <TableHeader>Type</TableHeader>
                                <TableHeader>Created</TableHeader>
                                <TableHeader>Actions</TableHeader>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {documents.map((doc) => (
                                <TableRow key={doc.id}>
                                    <TableCell>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                            <DocumentIcon size={16} />
                                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.875rem' }}>
                                                {doc.filename}
                                            </span>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <Link
                                            to={`/jobs/${doc.job_id}`}
                                            style={{ color: 'var(--primary-color)' }}
                                        >
                                            {doc.title}
                                        </Link>
                                    </TableCell>
                                    <TableCell>{doc.company}</TableCell>
                                    <TableCell>
                                        <DocumentTypeBadge type={doc.doc_type} />
                                    </TableCell>
                                    <TableCell style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                                        {new Date(doc.created_at).toLocaleDateString()}
                                    </TableCell>
                                    <TableCell>
                                        <div className="d-flex gap-2">
                                            <Button
                                                variant="primary"
                                                size="sm"
                                                onClick={() => handleDownload(doc.id)}
                                            >
                                                <DownloadIcon size={14} /> Download
                                            </Button>
                                            <Button
                                                variant="secondary"
                                                size="sm"
                                                style={{ color: '#ef4444' }}
                                                onClick={() => handleDelete(doc.id)}
                                            >
                                                <DeleteIcon size={14} />
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                ) : (
                    <div className="empty-state">
                        <DocumentIcon size={48} />
                        <div style={{ marginTop: '16px' }}>
                            <p style={{ fontSize: '1rem', marginBottom: '8px' }}>No documents generated yet</p>
                            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                                Go to a job detail page to generate tailored CVs and cover letters
                            </p>
                        </div>
                        <Link to="/matching">
                            <Button variant="primary" style={{ marginTop: '16px' }}>
                                View Job Matches
                            </Button>
                        </Link>
                    </div>
                )}
            </Card>
        </>
    );
}

export default Documents;
