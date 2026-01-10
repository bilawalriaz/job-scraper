"""Background scheduler for autonomous job scraping pipeline."""

import asyncio
import threading
import time
import json
from datetime import datetime
from typing import Dict, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum


class TaskStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskState:
    """Tracks state of a running task."""
    status: TaskStatus = TaskStatus.IDLE
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: int = 0
    total: int = 0
    message: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": self.progress,
            "total": self.total,
            "message": self.message,
            "error": self.error,
        }


@dataclass
class SchedulerConfig:
    """Scheduler configuration."""
    enabled: bool = False
    scrape_interval_minutes: int = 60  # How often to scrape for new jobs
    description_interval_minutes: int = 15  # How often to fetch full descriptions
    llm_interval_minutes: int = 10  # How often to run AI processing
    scrape_enabled: bool = True
    description_enabled: bool = True
    llm_enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'SchedulerConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class JobScheduler:
    """
    Manages autonomous job scraping pipeline.

    Pipeline: Scrape -> Get Descriptions -> AI Process
    Each step runs independently without blocking others.
    """

    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = db_path
        self.config = SchedulerConfig()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Task states (independent tracking for each task type)
        self.task_states: Dict[str, TaskState] = {
            "scrape": TaskState(),
            "descriptions": TaskState(),
            "llm": TaskState(),
        }
        self._state_lock = threading.Lock()

        # Last run times
        self._last_runs: Dict[str, float] = {
            "scrape": 0,
            "descriptions": 0,
            "llm": 0,
        }

        # Task executors (will be set by the app)
        self._executors: Dict[str, Callable] = {}

        # Load config from database
        self._load_config()

    def _load_config(self):
        """Load scheduler config from database."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            # Ensure scheduler_config table exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scheduler_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    config_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

            cursor = conn.execute("SELECT config_json FROM scheduler_config WHERE id = 1")
            row = cursor.fetchone()
            if row:
                self.config = SchedulerConfig.from_dict(json.loads(row['config_json']))
            conn.close()
        except Exception as e:
            print(f"[Scheduler] Error loading config: {e}")

    def save_config(self):
        """Save scheduler config to database."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT OR REPLACE INTO scheduler_config (id, config_json, updated_at)
                VALUES (1, ?, CURRENT_TIMESTAMP)
            """, (json.dumps(self.config.to_dict()),))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[Scheduler] Error saving config: {e}")

    def set_executor(self, task_name: str, executor: Callable):
        """Set the executor function for a task type."""
        self._executors[task_name] = executor

    def get_state(self, task_name: str) -> TaskState:
        """Get current state of a task."""
        with self._state_lock:
            return self.task_states.get(task_name, TaskState())

    def get_all_states(self) -> Dict[str, dict]:
        """Get states of all tasks."""
        with self._state_lock:
            return {name: state.to_dict() for name, state in self.task_states.items()}

    def update_state(self, task_name: str, **kwargs):
        """Update state of a task."""
        with self._state_lock:
            state = self.task_states.get(task_name)
            if state:
                for key, value in kwargs.items():
                    if hasattr(state, key):
                        setattr(state, key, value)

    def _should_run_task(self, task_name: str) -> bool:
        """Check if a task should run based on interval."""
        intervals = {
            "scrape": self.config.scrape_interval_minutes,
            "descriptions": self.config.description_interval_minutes,
            "llm": self.config.llm_interval_minutes,
        }
        enabled = {
            "scrape": self.config.scrape_enabled,
            "descriptions": self.config.description_enabled,
            "llm": self.config.llm_enabled,
        }

        if not enabled.get(task_name, False):
            return False

        # Check if task is already running
        with self._state_lock:
            if self.task_states[task_name].status == TaskStatus.RUNNING:
                return False

        interval_seconds = intervals.get(task_name, 60) * 60
        last_run = self._last_runs.get(task_name, 0)
        return (time.time() - last_run) >= interval_seconds

    def _run_task(self, task_name: str):
        """Run a task in a separate thread."""
        executor = self._executors.get(task_name)
        if not executor:
            print(f"[Scheduler] No executor for task: {task_name}")
            return

        def task_wrapper():
            try:
                self.update_state(
                    task_name,
                    status=TaskStatus.RUNNING,
                    started_at=datetime.utcnow().isoformat(),
                    progress=0,
                    error=None,
                    message=f"Starting {task_name}..."
                )

                # Run the executor
                result = executor(
                    progress_callback=lambda p, t, m: self.update_state(
                        task_name, progress=p, total=t, message=m
                    )
                )

                self.update_state(
                    task_name,
                    status=TaskStatus.COMPLETED,
                    completed_at=datetime.utcnow().isoformat(),
                    message=f"Completed: {result}" if result else "Completed"
                )
                self._last_runs[task_name] = time.time()

            except Exception as e:
                self.update_state(
                    task_name,
                    status=TaskStatus.FAILED,
                    completed_at=datetime.utcnow().isoformat(),
                    error=str(e),
                    message=f"Failed: {e}"
                )
                print(f"[Scheduler] Task {task_name} failed: {e}")

        thread = threading.Thread(target=task_wrapper, daemon=True)
        thread.start()

    def _scheduler_loop(self):
        """Main scheduler loop."""
        print("[Scheduler] Starting scheduler loop...")

        while not self._stop_event.is_set():
            if self.config.enabled:
                # Check each task independently
                for task_name in ["scrape", "descriptions", "llm"]:
                    if self._should_run_task(task_name):
                        print(f"[Scheduler] Starting task: {task_name}")
                        self._run_task(task_name)

            # Sleep for a bit before checking again
            self._stop_event.wait(10)  # Check every 10 seconds

        print("[Scheduler] Scheduler loop stopped")

    def start(self):
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()
        print("[Scheduler] Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        print("[Scheduler] Scheduler stopped")

    def run_task_now(self, task_name: str) -> bool:
        """Manually trigger a task to run now."""
        if task_name not in self.task_states:
            return False

        # Check if already running
        with self._state_lock:
            if self.task_states[task_name].status == TaskStatus.RUNNING:
                return False

        self._run_task(task_name)
        return True

    def is_task_running(self, task_name: str) -> bool:
        """Check if a task is currently running."""
        with self._state_lock:
            state = self.task_states.get(task_name)
            return state and state.status == TaskStatus.RUNNING


# Singleton instance
_scheduler: Optional[JobScheduler] = None


def get_scheduler(db_path: str = "data/jobs.db") -> JobScheduler:
    """Get or create the scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = JobScheduler(db_path)
    return _scheduler
