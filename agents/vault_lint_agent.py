# agents/vault_lint_agent.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# This is the Vault Lint Agent — it runs the programmatic lint checks
# from memory/vault_lint.py and produces a human-readable report.
#
# Unlike other agents, this one doesn't need LLM calls for the checks
# themselves (they're pure functions). It formats the results into a
# clear, actionable report.
# ============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.vault_lint import run_lint_checks
from memory.vault import get_vault_stats


def run_vault_lint() -> str:
    """
    Run all vault lint checks and return a formatted report.

    Returns:
        str: Human-readable report of vault health issues.
    """
    issues = run_lint_checks()
    stats = get_vault_stats()

    if not issues:
        return (
            f"Vault Health Check: ALL CLEAR\n\n"
            f"Scanned {stats['total']} memories across {len(stats) - 1} categories.\n"
            f"No issues found — vault is clean!"
        )

    errors = [i for i in issues if i['severity'] == 'error']
    warnings = [i for i in issues if i['severity'] == 'warning']
    infos = [i for i in issues if i['severity'] == 'info']

    report = f"Vault Health Check: {len(issues)} issue(s) found\n\n"
    report += f"Scanned {stats['total']} memories.\n\n"

    if errors:
        report += f"ERRORS ({len(errors)}):\n"
        for issue in errors:
            report += f"  - [{issue['check']}] {issue['description']}\n"
            report += f"    File: {issue['filepath']}\n"
        report += "\n"

    if warnings:
        report += f"WARNINGS ({len(warnings)}):\n"
        for issue in warnings:
            report += f"  - [{issue['check']}] {issue['description']}\n"
            report += f"    File: {issue['filepath']}\n"
        report += "\n"

    if infos:
        report += f"INFO ({len(infos)}):\n"
        for issue in infos:
            report += f"  - [{issue['check']}] {issue['description']}\n"
            report += f"    File: {issue['filepath']}\n"

    return report
