function Card({ children, className = '' }) {
    return (
        <div className={`card ${className}`}>
            {children}
        </div>
    );
}

function CardHeader({ children, className = '', actions }) {
    return (
        <div className={`card-header d-flex justify-between align-center ${className}`}>
            <span className="d-flex align-center gap-2">{children}</span>
            {actions && <div>{actions}</div>}
        </div>
    );
}

function CardBody({ children, className = '', noPadding = false }) {
    return (
        <div className={`card-body ${className}`} style={noPadding ? { padding: 0 } : undefined}>
            {children}
        </div>
    );
}

export { Card, CardHeader, CardBody };
