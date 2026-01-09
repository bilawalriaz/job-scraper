import { Link } from 'react-router-dom';
import Spinner from './Spinner';

function Button({
    children,
    variant = 'secondary',
    size = 'default',
    loading = false,
    disabled = false,
    to,
    href,
    className = '',
    ...props
}) {
    const classes = `btn btn-${variant} ${size === 'sm' ? 'btn-sm' : ''} ${className}`;

    const content = (
        <>
            {loading && <Spinner />}
            {children}
        </>
    );

    if (to) {
        return (
            <Link to={to} className={classes} {...props}>
                {content}
            </Link>
        );
    }

    if (href) {
        return (
            <a href={href} className={classes} target="_blank" rel="noopener noreferrer" {...props}>
                {content}
            </a>
        );
    }

    return (
        <button className={classes} disabled={disabled || loading} {...props}>
            {content}
        </button>
    );
}

export default Button;
