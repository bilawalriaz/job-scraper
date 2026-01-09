import { Link, NavLink, Outlet } from 'react-router-dom';

function Layout() {
    return (
        <>
            <div className="container">
                <header className="header">
                    <Link to="/" className="logo">
                        <div className="logo-mark">JS</div>
                        <span className="logo-text">Job Scraper</span>
                    </Link>
                    <nav className="nav-links">
                        <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                            Dashboard
                        </NavLink>
                        <NavLink to="/jobs" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                            Jobs
                        </NavLink>
                        <NavLink to="/configs" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                            Searches
                        </NavLink>
                        <NavLink to="/logs" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                            Logs
                        </NavLink>
                    </nav>
                </header>

                <main>
                    <Outlet />
                </main>
            </div>

            <footer>
                Job Scraper &bull; <a href="https://github.com/bilawalriaz/job-scraper" target="_blank" rel="noopener noreferrer">GitHub</a>
            </footer>
        </>
    );
}

export default Layout;
