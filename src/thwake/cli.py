"""Command-line entry point: ``python -m thwake <command>`` or ``thwake <command>``."""

from __future__ import annotations

from datetime import datetime

import click

from thwake import baseline as baseline_steps
from thwake import ee_auth
from thwake import reference as reference_steps
from thwake.config import REPO_ROOT, Config, ConfigError, load_config

# In run order: each step reads the outputs of the ones before it. The composite is last
# because its asset export continues in Earth Engine after the command returns.
BASELINE_STEPS = ["extent", "aev", "landcover", "river", "composite"]


def _run_baseline_step(step: str, cfg: Config) -> str:
    """Run one baseline step and return its terminal report.

    Functions are looked up on the modules at call time (tests replace them).
    """
    b, r, log = baseline_steps, reference_steps, click.echo
    if step == "extent":
        return b.summary(b.build_extent(cfg, log=log))
    if step == "aev":
        return b.aev_summary(b.build_aev(cfg, log=log))
    if step == "landcover":
        return r.landcover_summary(r.build_landcover(cfg, log=log))
    if step == "river":
        return r.river_summary(r.build_river(cfg, log=log))
    return r.composite_summary(r.build_composite(cfg, log=log))


def _not_implemented(name: str) -> None:
    click.echo(f"{name}: not implemented")
    raise SystemExit(1)


@click.group()
@click.version_option(package_name="thwake")
def cli() -> None:
    """Thwake Reservoir Remote Sensing Monitor pipeline."""


@cli.command()
@click.option(
    "--step",
    type=click.Choice(BASELINE_STEPS),
    default=None,
    help="Run one step only (default: all, in order). extent: AOI and max-extent mask "
    "(data/baseline/*.geojson). aev: area–elevation–volume curve (aev_curve_v1.csv). "
    "landcover: land cover in the max extent (landcover_flood_zone.csv). river: historic "
    "river channel (river_channel.geojson). composite: Sentinel-2 'before' composite "
    "(Earth Engine asset + media/before_composite.png).",
)
@click.option(
    "--verify",
    is_flag=True,
    help="Check the frozen files against the freeze manifest; run nothing.",
)
@click.option(
    "--write-manifest",
    is_flag=True,
    help="Freeze: write the SHA-256 manifest of the current baseline files; run nothing.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Run steps (or rewrite the manifest) even though the baseline is frozen. Only to "
    "check reproducibility; changes to a frozen baseline need an ADR and a new version.",
)
def baseline(step: str | None, verify: bool, write_manifest: bool, force: bool) -> None:
    """Build the baseline (Phase 1): extent, AEV curve and pre-filling reference layers."""
    b = baseline_steps
    try:
        cfg = load_config()
        if verify:
            problems = b.verify_manifest(cfg)
            for problem in problems:
                click.echo(f"  {problem}")
            if problems:
                raise click.ClickException("Baseline files differ from the freeze manifest")
            click.echo(f"All {len(b.frozen_files(cfg))} frozen baseline files match.")
            return
        if b.is_frozen(cfg) and not force:
            raise click.ClickException(
                f"The baseline is frozen ({b.manifest_path(cfg).relative_to(REPO_ROOT)}). "
                "Changes need an ADR and a new version (AGENTS.md rule 8). Use --force only "
                "to check reproducibility, then restore the frozen files with git."
            )
        if write_manifest:
            click.echo(f"Freeze manifest -> {b.write_manifest(cfg).relative_to(REPO_ROOT)}")
            return
        ee_auth.initialize(cfg)
        for name in [step] if step else BASELINE_STEPS:
            click.echo(_run_baseline_step(name, cfg))
    except (ConfigError, baseline_steps.BaselineError) as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command()
@click.option(
    "--since",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Process scenes acquired on or after this date (YYYY-MM-DD).",
)
def update(since: datetime | None) -> None:
    """Process new scenes and append them to the time series."""
    _not_implemented("update")


@cli.command()
def media() -> None:
    """Regenerate charts, time-lapse and figures from processed data."""
    _not_implemented("media")


@cli.command()
def qa() -> None:
    """Run sanity checks on the time series and flag suspicious rows."""
    _not_implemented("qa")


def main() -> None:
    """Run the CLI."""
    cli()
