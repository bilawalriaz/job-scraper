import Button from './Button';
import { ChevronLeftIcon, ChevronRightIcon } from './Icons';

function Pagination({ page, totalPages, onPageChange }) {
    if (totalPages <= 1) return null;

    const getPageNumbers = () => {
        const pages = [];
        for (let i = 1; i <= totalPages; i++) {
            if (
                i === 1 ||
                i === totalPages ||
                (i >= page - 2 && i <= page + 2)
            ) {
                pages.push(i);
            } else if (i === page - 3 || i === page + 3) {
                pages.push('...');
            }
        }
        return pages;
    };

    return (
        <nav className="pagination">
            {page > 1 && (
                <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => onPageChange(page - 1)}
                >
                    <ChevronLeftIcon /> Previous
                </Button>
            )}

            <div className="pagination-numbers">
                {getPageNumbers().map((p, index) => (
                    p === '...' ? (
                        <span key={`ellipsis-${index}`} className="pagination-ellipsis">...</span>
                    ) : (
                        <Button
                            key={p}
                            variant={p === page ? 'primary' : 'secondary'}
                            size="sm"
                            onClick={() => onPageChange(p)}
                            style={{ minWidth: 40, justifyContent: 'center' }}
                        >
                            {p}
                        </Button>
                    )
                ))}
            </div>

            {page < totalPages && (
                <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => onPageChange(page + 1)}
                >
                    Next <ChevronRightIcon />
                </Button>
            )}
        </nav>
    );
}

export default Pagination;
