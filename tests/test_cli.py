import pytest
from click.testing import CliRunner

from thwake import baseline as baseline_steps
from thwake import ee_auth
from thwake import reference as reference_steps
from thwake.cli import cli

COMMANDS = ["baseline", "validate", "update", "media", "qa"]
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


def fake_steps(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace every baseline step with a stub that records its name."""
    calls: list[str] = []
    monkeypatch.setattr(baseline_steps, "is_frozen", lambda cfg: False)
    monkeypatch.setattr(ee_auth, "initialize", lambda cfg: calls.append("init"))
    for module, build, report, name in [
        (baseline_steps, "build_extent", "summary", "extent"),
        (baseline_steps, "build_aev", "aev_summary", "aev"),
        (reference_steps, "build_landcover", "landcover_summary", "landcover"),
        (reference_steps, "build_river", "river_summary", "river"),
        (reference_steps, "build_composite", "composite_summary", "composite"),
    ]:
        monkeypatch.setattr(module, build, lambda cfg, log, n=name: calls.append(n) or n)
        monkeypatch.setattr(module, report, lambda result: f"report of {result}")
    return calls


def test_baseline_without_step_runs_all_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_steps(monkeypatch)
    result = CliRunner().invoke(cli, ["baseline"])
    assert result.exit_code == 0, result.output
    assert calls == ["init", "extent", "aev", "landcover", "river", "composite"]
    for name in ["extent", "aev", "landcover", "river", "composite"]:
        assert f"report of {name}" in result.output


@pytest.mark.parametrize("step", ["landcover", "river", "composite"])
def test_baseline_runs_single_reference_step(monkeypatch: pytest.MonkeyPatch, step: str) -> None:
    calls = fake_steps(monkeypatch)
    result = CliRunner().invoke(cli, ["baseline", "--step", step])
    assert result.exit_code == 0, result.output
    assert calls == ["init", step]


def test_baseline_stops_at_first_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_steps(monkeypatch)

    def fail(cfg, log):
        raise baseline_steps.BaselineError("no Dynamic World scenes")

    monkeypatch.setattr(reference_steps, "build_landcover", fail)
    result = CliRunner().invoke(cli, ["baseline"])
    assert result.exit_code == 1
    assert "no Dynamic World scenes" in result.output
    assert calls == ["init", "extent", "aev"]


def test_baseline_rejects_unknown_step() -> None:
    result = CliRunner().invoke(cli, ["baseline", "--step", "everything"])
    assert result.exit_code == 2


@pytest.fixture(autouse=True)
def unfrozen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the step tests as if the baseline were not frozen (the repository's is)."""
    monkeypatch.setattr(baseline_steps, "is_frozen", lambda cfg: False)


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


def test_frozen_baseline_refuses_to_run(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_steps(monkeypatch)
    monkeypatch.setattr(baseline_steps, "is_frozen", lambda cfg: True)
    for args in (["baseline"], ["baseline", "--write-manifest"]):
        result = CliRunner().invoke(cli, args)
        assert result.exit_code == 1
        assert "frozen" in result.output and "ADR" in result.output
    assert calls == []


def test_frozen_baseline_runs_with_force(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_steps(monkeypatch)
    monkeypatch.setattr(baseline_steps, "is_frozen", lambda cfg: True)
    result = CliRunner().invoke(cli, ["baseline", "--step", "river", "--force"])
    assert result.exit_code == 0, result.output
    assert calls == ["init", "river"]


def test_write_manifest_runs_no_steps(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    calls = fake_steps(monkeypatch)
    from thwake.config import REPO_ROOT

    monkeypatch.setattr(baseline_steps, "write_manifest", lambda cfg: REPO_ROOT / "m.sha256")
    result = CliRunner().invoke(cli, ["baseline", "--write-manifest"])
    assert result.exit_code == 0, result.output
    assert "m.sha256" in result.output and calls == []


@pytest.mark.parametrize("problems, code", [([], 0), (["aoi.geojson: changed"], 1)])
def test_verify(monkeypatch: pytest.MonkeyPatch, problems: list[str], code: int) -> None:
    monkeypatch.setattr(baseline_steps, "verify_manifest", lambda cfg: problems)
    result = CliRunner().invoke(cli, ["baseline", "--verify"])
    assert result.exit_code == code
    assert ("match" in result.output) if code == 0 else ("changed" in result.output)


def fake_validation(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from thwake import validation as validation_steps

    calls: list[str] = []
    monkeypatch.setattr(ee_auth, "initialize", lambda cfg: calls.append("init"))
    monkeypatch.setattr(
        validation_steps, "build_reference", lambda cfg, name, log: calls.append(f"build {name}")
    )
    monkeypatch.setattr(
        validation_steps,
        "compare_reference",
        lambda cfg, name, log: calls.append(f"compare {name}") or "result",
    )
    monkeypatch.setattr(validation_steps, "comparison_summary", lambda result: f"summary {result}")
    return calls


def test_validate_reference_runs_earth_engine_then_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = fake_validation(monkeypatch)
    result = CliRunner().invoke(cli, ["validate", "reference", "--name", "masinga"])
    assert result.exit_code == 0, result.output
    assert calls == ["init", "build masinga", "compare masinga"]
    assert "summary result" in result.output


def test_validate_reference_compare_only_skips_earth_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = fake_validation(monkeypatch)
    result = CliRunner().invoke(
        cli, ["validate", "reference", "--name", "masinga", "--compare-only"]
    )
    assert result.exit_code == 0, result.output
    assert calls == ["compare masinga"]


def test_validate_reference_rejects_unknown_name(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_validation(monkeypatch)
    result = CliRunner().invoke(cli, ["validate", "reference", "--name", "nowhere"])
    assert result.exit_code == 1
    assert "Unknown reference reservoir" in result.output and calls == []
