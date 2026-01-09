import { useEffect, useState, useRef } from 'react';
import { Card, CardHeader, CardBody } from './Card';
import { LiveBadge } from './StatusBadge';
import { getConsoleLogs, streamConsoleLogs } from '../api/client';

// Terminal icon
const TerminalIcon = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="4 17 10 11 4 5"></polyline>
        <line x1="12" y1="19" x2="20" y2="19"></line>
    </svg>
);

function Console() {
    const [logs, setLogs] = useState([]);
    const consoleRef = useRef(null);

    useEffect(() => {
        // Load initial logs
        getConsoleLogs()
            .then(data => {
                if (data.length > 0) {
                    setLogs(data);
                }
            })
            .catch(console.error);

        // Start SSE stream
        const cleanup = streamConsoleLogs((log) => {
            setLogs(prev => {
                const newLogs = [...prev, log];
                // Keep only last 100 logs
                if (newLogs.length > 100) {
                    return newLogs.slice(-100);
                }
                return newLogs;
            });
        });

        return cleanup;
    }, []);

    // Auto-scroll to bottom when new logs arrive
    useEffect(() => {
        if (consoleRef.current) {
            consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
        }
    }, [logs]);

    const formatTime = (timestamp) => {
        return new Date(timestamp).toLocaleTimeString();
    };

    return (
        <Card style={{ marginBottom: '32px' }}>
            <CardHeader actions={<LiveBadge />}>
                <TerminalIcon />
                Console Output
            </CardHeader>
            <CardBody noPadding>
                <div className="console" ref={consoleRef}>
                    {logs.length === 0 ? (
                        <div style={{ color: '#6e7681', fontStyle: 'italic' }}>
                            Waiting for scraper output...
                        </div>
                    ) : (
                        logs.map((log, index) => (
                            <div key={index} className="console-entry">
                                <span className="console-time">[{formatTime(log.timestamp)}]</span>
                                <span className={`console-level-${log.level}`}>[{log.level}]</span>
                                <span style={{ color: '#c9d1d9' }}> {log.message}</span>
                            </div>
                        ))
                    )}
                </div>
            </CardBody>
        </Card>
    );
}

export default Console;
