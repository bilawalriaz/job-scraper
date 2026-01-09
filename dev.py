#!/usr/bin/env python3
"""Development server that runs both Flask backend and React frontend."""

import subprocess
import sys
import os
import signal
import time
from pathlib import Path

# Get project root directory
PROJECT_ROOT = Path(__file__).parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []
    
    # Check Flask
    try:
        import flask
    except ImportError:
        missing.append("flask")
    
    if missing:
        print("❌ Missing Python dependencies:", ", ".join(missing))
        print("\n   Install with: pip install -r requirements.txt")
        print("   Or activate your virtual environment first.\n")
        sys.exit(1)
    
    # Check npm
    try:
        subprocess.run(["npm", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ npm not found. Please install Node.js first.")
        sys.exit(1)


def run_dev():
    """Run both backend and frontend for development."""
    processes = []

    def cleanup(signum=None, frame=None):
        """Clean up child processes on exit."""
        print("\n🛑 Shutting down...")
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Check if frontend dependencies are installed
    if not (FRONTEND_DIR / "node_modules").exists():
        print("📦 Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=FRONTEND_DIR, check=True)

    # Check if frontend is built (for production mode)
    frontend_built = (FRONTEND_DIR / "dist").exists()

    print("=" * 60)
    print("🚀 JOB SCRAPER - Development Server")
    print("=" * 60)

    # Start Flask backend
    print("\n🐍 Starting Flask backend on http://localhost:8000")
    flask_env = os.environ.copy()
    flask_env["FLASK_ENV"] = "development"
    flask_proc = subprocess.Popen(
        [sys.executable, "api/app.py"],
        cwd=PROJECT_ROOT,
        env=flask_env
    )
    processes.append(flask_proc)

    # Give Flask a moment to start
    time.sleep(1)

    # Start Vite dev server (proxies to Flask)
    print("⚛️  Starting React dev server on http://localhost:5173")
    print("\n" + "=" * 60)
    print("📌 Open http://localhost:5173 in your browser")
    print("   (API requests are proxied to Flask on port 8000)")
    print("=" * 60 + "\n")

    vite_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=FRONTEND_DIR
    )
    processes.append(vite_proc)

    # Wait for processes
    try:
        while True:
            # Check if any process has died
            for proc in processes:
                if proc.poll() is not None:
                    print(f"⚠️  Process exited with code {proc.returncode}")
                    cleanup()
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


def run_prod():
    """Run in production mode (Flask serves built React app)."""
    # Build frontend if needed
    if not (FRONTEND_DIR / "dist").exists():
        print("📦 Building frontend for production...")
        subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=True)

    print("=" * 60)
    print("🚀 JOB SCRAPER - Production Server")
    print("=" * 60)
    print("\n📌 Open http://localhost:8000 in your browser\n")

    # Run Flask (serves React build)
    os.execv(sys.executable, [sys.executable, "api/app.py"])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Job Scraper Development Server")
    parser.add_argument("--prod", action="store_true", help="Run in production mode")
    args = parser.parse_args()

    # Check dependencies first
    check_dependencies()

    if args.prod:
        run_prod()
    else:
        run_dev()
