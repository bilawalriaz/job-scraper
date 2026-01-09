function Spinner({ size = 20, className = '' }) {
    return (
        <div
            className={`spinner ${className}`}
            style={{ width: size, height: size }}
        />
    );
}

export default Spinner;
