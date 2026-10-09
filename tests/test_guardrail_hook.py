"""Tests for the agent guardrail hook (.claude/hooks/block-repo-writes.sh).

The hook must let agents read git/GitHub repositories but block every write.
See AGENTS.md rule 10 and docs/human-steps.md (H3).
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "block-repo-writes.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="hook needs bash and jq",
)


def run_hook(command: str) -> str:
    """Return the hook's stdout for a Bash tool call with this command ('' = allowed)."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = subprocess.run(
        ["bash", str(HOOK)], input=payload, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


ALLOWED = [
    "git status",
    "git diff --stat",
    "git log --oneline -5",
    "git -C /tmp log",
    "git show HEAD",
    "git branch",
    "git remote -v",
    "git config --get user.name",
    "gh auth status",
    "gh repo view",
    "gh pr list",
    "ls -la",
    "uv run pytest",
    "ruff check .",
    "echo 'not git at all'",
]

BLOCKED = [
    "git commit -m x",
    "git add .",
    "git push origin main",
    "git -C ../other push",
    "git tag v1",
    "cd x && git commit -am y",
    "ls | git commit -m z",
    "FOO=1 git push",
    "git branch -D main",
    "git remote add origin https://example.com/x.git",
    "git config user.name x",
    "git stash",
    "git init",
    "git reset --hard HEAD~1",
    "git checkout -- README.md",
    "gh repo delete foo --yes",
    "gh api -X DELETE repos/a/b",
    "gh pr create",
    "gh secret set X",
    "rm -rf .git",
    "echo x > .git/HEAD",
]


@pytest.mark.parametrize("command", ALLOWED)
def test_read_only_commands_are_allowed(command: str) -> None:
    assert run_hook(command) == ""


@pytest.mark.parametrize("command", BLOCKED)
def test_write_commands_are_denied(command: str) -> None:
    out = run_hook(command)
    assert out, f"expected a deny decision for: {command}"
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert decision["permissionDecisionReason"]


def test_empty_input_is_allowed() -> None:
    result = subprocess.run(
        ["bash", str(HOOK)], input="{}", capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == ""
