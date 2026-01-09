function StatusBadge({ status, className = '' }) {
    const displayStatus = status || 'new';

    return (
        <span className={`status-badge status-${displayStatus} ${className}`}>
            {displayStatus.charAt(0).toUpperCase() + displayStatus.slice(1)}
        </span>
    );
}

function TypeBadge({ type, className = '' }) {
    if (!type) {
        return <span className="text-muted" style={{ fontSize: '0.875rem' }}>-</span>;
    }

    return (
        <span
            className={`status-badge ${className}`}
            style={{ background: 'rgba(59, 130, 246, 0.12)', color: '#3b82f6' }}
        >
            {type}
        </span>
    );
}

function ActiveBadge({ active }) {
    return (
        <span
            className="status-badge"
            style={active
                ? { background: 'rgba(16, 185, 129, 0.12)', color: '#10b981' }
                : { background: 'rgba(148, 163, 184, 0.12)', color: '#94a3b8' }
            }
        >
            {active ? 'Active' : 'Disabled'}
        </span>
    );
}

function LiveBadge() {
    return (
        <span
            className="status-badge"
            style={{ background: 'rgba(34, 197, 94, 0.12)', color: '#22c55e', fontSize: '0.75rem' }}
        >
            Live
        </span>
    );
}

export { StatusBadge, TypeBadge, ActiveBadge, LiveBadge };
