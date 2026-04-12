# memory/scheduler.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# Lightweight task scheduler for background vault maintenance.
# Tasks are defined in config/scheduled_tasks.json and run via
# `python main.py --run-scheduled`.
#
# NOT an always-running daemon — designed to be invoked by an OS-level
# scheduler (cron on Linux/Mac, Task Scheduler on Windows).
# ============================================================================

import json
from datetime import datetime, timedelta
from pathlib import Path

CONFIG_FILE = Path('config') / 'scheduled_tasks.json'
STATE_FILE = Path('config') / 'scheduler_state.json'


def get_scheduled_tasks() -> list[dict]:
    """
    Load enabled task definitions from config file.

    Config format: list of dicts with name, description, action,
    interval_hours, enabled fields.

    Returns only enabled tasks.
    """
    if not CONFIG_FILE.exists():
        return []
    try:
        tasks = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return []
    return [t for t in tasks if t.get('enabled', True)]


def _load_state() -> dict:
    """Load scheduler state (last run times)."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict):
    """Save scheduler state to disk."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding='utf-8')


def is_task_due(task: dict) -> bool:
    """
    Check if a task should run based on its interval and last run time.

    Returns True if never run or last run more than interval_hours ago.
    """
    state = _load_state()
    task_state = state.get(task['name'], {})
    last_run = task_state.get('last_run')

    if not last_run:
        return True

    try:
        last_run_dt = datetime.fromisoformat(last_run)
    except (ValueError, TypeError):
        return True

    interval = timedelta(hours=task.get('interval_hours', 24))
    return datetime.now() - last_run_dt >= interval


def mark_task_run(task_name: str):
    """Record that a task was just run."""
    state = _load_state()
    state[task_name] = {'last_run': datetime.now().isoformat()}
    _save_state(state)


def get_due_tasks() -> list[dict]:
    """Get all enabled tasks that are due to run."""
    tasks = get_scheduled_tasks()
    return [t for t in tasks if is_task_due(t)]
