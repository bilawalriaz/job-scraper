import { useState, useEffect } from 'react';
import { getLogs } from '../api/client';
import { Card, CardBody } from '../components/Card';
import { Table, TableHead, TableBody, TableRow, TableHeader, TableCell } from '../components/Table';
import Spinner from '../components/Spinner';

function Logs() {
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadLogs();
    }, []);

    const loadLogs = async () => {
        try {
            const data = await getLogs();
            setLogs(data.logs || []);
        } catch (error) {
            console.error('Failed to load logs:', error);
        } finally {
            setLoading(false);
        }
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return '';
        return dateStr.substring(0, 19).replace('T', ' ');
    };

    return (
        <>
            {/* Page Header */}
            <div className="page-header">
                <div>
                    <h1 className="page-title">Scraping Logs</h1>
                    <p className="page-subtitle">View the history of scraping runs</p>
                </div>
            </div>

            {/* Logs Table */}
            <Card>
                {loading ? (
                    <div className="loading-state">
                        <Spinner size={40} />
                    </div>
                ) : logs.length > 0 ? (
                    <Table>
                        <TableHead>
                            <TableRow>
                                <TableHeader>Time</TableHeader>
                                <TableHeader>Source</TableHeader>
                                <TableHeader>Config</TableHeader>
                                <TableHeader>Found</TableHeader>
                                <TableHeader>Added</TableHeader>
                                <TableHeader>Status</TableHeader>
                                <TableHeader>Error</TableHeader>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {logs.map((log, index) => (
                                <TableRow key={index}>
                                    <TableCell>{formatDate(log.started_at)}</TableCell>
                                    <TableCell>{log.source}</TableCell>
                                    <TableCell>{log.search_config_id || '-'}</TableCell>
                                    <TableCell>{log.jobs_found}</TableCell>
                                    <TableCell>{log.jobs_added}</TableCell>
                                    <TableCell>
                                        {log.success ? (
                                            <span
                                                className="status-badge"
                                                style={{ background: 'rgba(16, 185, 129, 0.12)', color: '#10b981' }}
                                            >
                                                Success
                                            </span>
                                        ) : (
                                            <span
                                                className="status-badge"
                                                style={{ background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444' }}
                                            >
                                                Failed
                                            </span>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        <span
                                            style={{ maxWidth: '200px', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                            title={log.error_message}
                                        >
                                            {log.error_message || '-'}
                                        </span>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                ) : (
                    <div className="empty-state">
                        <p>No logs yet</p>
                    </div>
                )}
            </Card>
        </>
    );
}

export default Logs;
