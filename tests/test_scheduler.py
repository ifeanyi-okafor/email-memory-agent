# tests/test_scheduler.py
"""Tests for the background task scheduler (memory/scheduler.py)."""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.scheduler import get_scheduled_tasks, is_task_due, mark_task_run, get_due_tasks


def _setup_scheduler(tmp_path, monkeypatch):
    config_dir = tmp_path / 'config'
    config_dir.mkdir()
    monkeypatch.setattr('memory.scheduler.CONFIG_FILE', config_dir / 'scheduled_tasks.json')
    monkeypatch.setattr('memory.scheduler.STATE_FILE', config_dir / 'scheduler_state.json')
    return config_dir


class TestGetScheduledTasks:
    def test_returns_empty_when_no_config(self, tmp_path, monkeypatch):
        _setup_scheduler(tmp_path, monkeypatch)
        assert get_scheduled_tasks() == []

    def test_loads_tasks_from_config(self, tmp_path, monkeypatch):
        config_dir = _setup_scheduler(tmp_path, monkeypatch)
        config = [
            {"name": "daily_lint", "description": "Run vault health check",
             "action": "lint", "interval_hours": 24, "enabled": True},
            {"name": "weekly_reconcile", "description": "Reconcile action items",
             "action": "reconcile", "interval_hours": 168, "enabled": True},
        ]
        (config_dir / 'scheduled_tasks.json').write_text(json.dumps(config))
        tasks = get_scheduled_tasks()
        assert len(tasks) == 2
        assert tasks[0]['name'] == 'daily_lint'

    def test_skips_disabled_tasks(self, tmp_path, monkeypatch):
        config_dir = _setup_scheduler(tmp_path, monkeypatch)
        config = [
            {"name": "active", "action": "lint", "interval_hours": 24, "enabled": True},
            {"name": "inactive", "action": "lint", "interval_hours": 24, "enabled": False},
        ]
        (config_dir / 'scheduled_tasks.json').write_text(json.dumps(config))
        tasks = get_scheduled_tasks()
        assert len(tasks) == 1
        assert tasks[0]['name'] == 'active'


class TestIsTaskDue:
    def test_never_run_is_due(self, tmp_path, monkeypatch):
        _setup_scheduler(tmp_path, monkeypatch)
        assert is_task_due({"name": "test", "interval_hours": 24}) is True

    def test_recently_run_not_due(self, tmp_path, monkeypatch):
        config_dir = _setup_scheduler(tmp_path, monkeypatch)
        state = {"test": {"last_run": datetime.now().isoformat()}}
        (config_dir / 'scheduler_state.json').write_text(json.dumps(state))
        assert is_task_due({"name": "test", "interval_hours": 24}) is False

    def test_old_run_is_due(self, tmp_path, monkeypatch):
        config_dir = _setup_scheduler(tmp_path, monkeypatch)
        old = (datetime.now() - timedelta(hours=2)).isoformat()
        state = {"test": {"last_run": old}}
        (config_dir / 'scheduler_state.json').write_text(json.dumps(state))
        assert is_task_due({"name": "test", "interval_hours": 1}) is True


class TestMarkTaskRun:
    def test_records_run_time(self, tmp_path, monkeypatch):
        config_dir = _setup_scheduler(tmp_path, monkeypatch)
        mark_task_run("daily_lint")
        state = json.loads((config_dir / 'scheduler_state.json').read_text())
        assert "daily_lint" in state
        assert "last_run" in state["daily_lint"]

    def test_preserves_other_tasks(self, tmp_path, monkeypatch):
        config_dir = _setup_scheduler(tmp_path, monkeypatch)
        old_time = datetime.now().isoformat()
        state = {"other_task": {"last_run": old_time}}
        (config_dir / 'scheduler_state.json').write_text(json.dumps(state))
        mark_task_run("new_task")
        loaded = json.loads((config_dir / 'scheduler_state.json').read_text())
        assert "other_task" in loaded
        assert "new_task" in loaded
        assert loaded["other_task"]["last_run"] == old_time


class TestGetDueTasks:
    def test_returns_only_due_tasks(self, tmp_path, monkeypatch):
        config_dir = _setup_scheduler(tmp_path, monkeypatch)
        config = [
            {"name": "due_task", "action": "lint", "interval_hours": 1, "enabled": True},
            {"name": "not_due", "action": "reconcile", "interval_hours": 24, "enabled": True},
        ]
        (config_dir / 'scheduled_tasks.json').write_text(json.dumps(config))
        state = {"not_due": {"last_run": datetime.now().isoformat()}}
        (config_dir / 'scheduler_state.json').write_text(json.dumps(state))
        due = get_due_tasks()
        assert len(due) == 1
        assert due[0]['name'] == 'due_task'
