import pytest
from click.testing import CliRunner

from thwake import baseline as baseline_steps
from thwake import ee_auth
from thwake.cli import cli

COMMANDS = ["baseline", "update", "media", "qa"]
NOT_IMPLEMENTED = ["update", "media", "qa"]


def test_help_lists_all_commands() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    for command in COMMANDS:
        assert command in result.output


@pytest.mark.parametrize("command", NOT_IMPLEMENTED)
def test_commands_report_not_implemented(command: str) -> None:
    result = CliRunner().invoke(cli, [command])
    assert result.exit_code == 1
    assert "not implemented" in result.output


def test_update_rejects_bad_since_date() -> None:
    result = CliRunner().invoke(cli, ["update", "--since", "09/10/2026"])
    assert result.exit_code == 2


def test_baseline_requires_step() -> None:
    result = CliRunner().invoke(cli, ["baseline"])
    assert result.exit_code == 2
    assert "--step" in result.output


def test_baseline_rejects_unknown_step() -> None:
    result = CliRunner().invoke(cli, ["baseline", "--step", "everything"])
    assert result.exit_code == 2


def test_baseline_extent_runs_step(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(ee_auth, "initialize", lambda cfg: calls.append("init"))
    monkeypatch.setattr(
        baseline_steps, "build_extent", lambda cfg, log: calls.append("build") or "result"
    )
    monkeypatch.setattr(baseline_steps, "summary", lambda result: f"summary of {result}")
    result = CliRunner().invoke(cli, ["baseline", "--step", "extent"])
    assert result.exit_code == 0, result.output
    assert calls == ["init", "build"]
    assert "summary of result" in result.output


def test_baseline_extent_reports_sanity_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(cfg, log):
        raise baseline_steps.BaselineError("leaks past the dam wall")

    monkeypatch.setattr(ee_auth, "initialize", lambda cfg: None)
    monkeypatch.setattr(baseline_steps, "build_extent", fail)
    result = CliRunner().invoke(cli, ["baseline", "--step", "extent"])
    assert result.exit_code == 1
    assert "leaks past the dam wall" in result.output


def test_baseline_aev_runs_step(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(ee_auth, "initialize", lambda cfg: calls.append("init"))
    monkeypatch.setattr(
        baseline_steps, "build_aev", lambda cfg, log: calls.append("aev") or "curve"
    )
    monkeypatch.setattr(baseline_steps, "aev_summary", lambda result: f"aev summary of {result}")
    result = CliRunner().invoke(cli, ["baseline", "--step", "aev"])
    assert result.exit_code == 0, result.output
    assert calls == ["init", "aev"]
    assert "aev summary of curve" in result.output
