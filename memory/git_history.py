# memory/git_history.py
#
# ============================================================================
# WHAT THIS FILE DOES:
# Manages a git repository inside the vault folder, enabling a full
# version history of every vault mutation. Uses subprocess calls to
# git (no GitPython dependency).
#
# The vault is its own standalone git repo — separate from the project
# git repo. This means every pipeline run can auto-commit the vault
# state without touching the project's main repo.
#
# Inspired by Rowboat's version_history.ts — commits after every batch
# so the user has a full timeline of vault evolution.
# ============================================================================

import subprocess
from pathlib import Path

VAULT_ROOT = Path('vault')

# Files that should NEVER be committed — internal tracking and state
_GITIGNORE_ENTRIES = [
    "_processed_emails.json",
    "_file_state.json",
    "scheduler_state.json",
    ".DS_Store",
    "Thumbs.db",
]


def _run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command inside the vault directory."""
    return subprocess.run(
        ['git', '-C', str(VAULT_ROOT)] + args,
        capture_output=True,
        text=True,
        check=check,
    )


def is_vault_repo() -> bool:
    """Check whether the vault has been initialized as a git repo."""
    return (VAULT_ROOT / '.git').is_dir()


def init_vault_repo():
    """
    Initialize the vault as a git repository if not already.

    Creates `.git/` and a `.gitignore` excluding internal tracking files.
    Idempotent — safe to call on an already-initialized vault.
    """
    if not VAULT_ROOT.exists():
        VAULT_ROOT.mkdir(parents=True)

    if not is_vault_repo():
        _run_git(['init', '-b', 'main'])

        # Configure a local user for commits (required by git)
        _run_git(['config', 'user.email', 'vault@email-memory-agent.local'])
        _run_git(['config', 'user.name', 'Vault Auto-Commit'])

    # Always (re)write .gitignore to keep excluded files up to date
    gitignore_content = '\n'.join(_GITIGNORE_ENTRIES) + '\n'
    gitignore_path = VAULT_ROOT / '.gitignore'
    gitignore_path.write_text(gitignore_content, encoding='utf-8')

    # Also mirror the ignore rules (plus `.gitignore` itself) into
    # `.git/info/exclude`. This keeps `.gitignore` out of `git status`
    # so a freshly-initialized vault reports "no changes" until the
    # user actually writes memory files. The `.gitignore` file is kept
    # in the working tree for visibility / external tooling.
    exclude_path = VAULT_ROOT / '.git' / 'info' / 'exclude'
    if exclude_path.parent.exists():
        exclude_path.write_text(gitignore_content + '.gitignore\n', encoding='utf-8')


def _has_changes() -> bool:
    """Check whether there are any uncommitted changes in the vault."""
    result = _run_git(['status', '--porcelain'])
    return bool(result.stdout.strip())


def commit_vault_changes(message: str) -> bool:
    """
    Stage all vault changes and create a commit.

    Args:
        message: Commit message.

    Returns:
        True if a commit was created, False if there were no changes.
    """
    if not is_vault_repo():
        init_vault_repo()

    # Stage all changes (respects .gitignore)
    _run_git(['add', '-A'])

    if not _has_changes():
        return False

    _run_git(['commit', '-m', message])
    return True


def get_vault_log(limit: int = 50) -> list[dict]:
    """
    Get recent vault commits in reverse chronological order.

    Returns:
        List of dicts with sha, message, timestamp (ISO format).
    """
    if not is_vault_repo():
        return []

    # Use a format string that's easy to parse: sha<TAB>timestamp<TAB>message
    result = _run_git(
        ['log', f'-n{limit}', '--format=%H%x09%aI%x09%s'],
        check=False,
    )

    if result.returncode != 0 or not result.stdout.strip():
        return []

    entries = []
    for line in result.stdout.strip().split('\n'):
        parts = line.split('\t', 2)
        if len(parts) == 3:
            entries.append({
                'sha': parts[0],
                'timestamp': parts[1],
                'message': parts[2],
            })

    return entries
