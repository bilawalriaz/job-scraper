import { useEffect, useCallback } from 'react';

function Modal({ isOpen, onClose, title, children, footer }) {
    const handleEscape = useCallback((e) => {
        if (e.key === 'Escape') {
            onClose();
        }
    }, [onClose]);

    const handleOverlayClick = (e) => {
        if (e.target === e.currentTarget) {
            onClose();
        }
    };

    useEffect(() => {
        if (isOpen) {
            document.addEventListener('keydown', handleEscape);
            document.body.style.overflow = 'hidden';
        }
        return () => {
            document.removeEventListener('keydown', handleEscape);
            document.body.style.overflow = '';
        };
    }, [isOpen, handleEscape]);

    return (
        <div
            className={`modal-overlay ${isOpen ? 'show' : ''}`}
            onClick={handleOverlayClick}
        >
            <div className="modal-content">
                <div className="modal-header">
                    <span className="modal-title">{title}</span>
                    <button className="btn-close" onClick={onClose}>
                        ×
                    </button>
                </div>
                <div className="modal-body">
                    {children}
                </div>
                {footer && (
                    <div className="modal-footer">
                        {footer}
                    </div>
                )}
            </div>
        </div>
    );
}

export default Modal;
