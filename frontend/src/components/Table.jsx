function Table({ children, className = '' }) {
    return (
        <div style={{ overflowX: 'auto' }}>
            <table className={`table ${className}`}>
                {children}
            </table>
        </div>
    );
}

function TableHead({ children }) {
    return <thead>{children}</thead>;
}

function TableBody({ children }) {
    return <tbody>{children}</tbody>;
}

function TableRow({ children, onClick }) {
    return (
        <tr onClick={onClick} style={onClick ? { cursor: 'pointer' } : undefined}>
            {children}
        </tr>
    );
}

function TableHeader({ children, width }) {
    return <th style={width ? { width } : undefined}>{children}</th>;
}

function TableCell({ children, className = '' }) {
    return <td className={className}>{children}</td>;
}

export { Table, TableHead, TableBody, TableRow, TableHeader, TableCell };
