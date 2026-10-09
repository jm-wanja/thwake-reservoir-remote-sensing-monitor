"""Command-line entry point: ``python -m thwake <command>`` or ``thwake <command>``."""

from __future__ import annotations

from datetime import datetime

import click

from thwake import baseline as baseline_steps
from thwake import ee_auth
from thwake.config import ConfigError, load_config

BASELINE_STEPS = ["extent", "aev"]


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
    required=True,
    help="Baseline step to run. extent: AOI and max-extent mask (data/baseline/*.geojson). "
    "aev: area–elevation–volume curve for GLO-30 and SRTM (data/baseline/aev_curve_v1.csv).",
)
def baseline(step: str) -> None:
    """Build the frozen baseline: AOI, max-extent mask, AEV curve (Phase 1)."""
    try:
        cfg = load_config()
        ee_auth.initialize(cfg)
        if step == "extent":
            report = baseline_steps.summary(baseline_steps.build_extent(cfg, log=click.echo))
        else:
            report = baseline_steps.aev_summary(baseline_steps.build_aev(cfg, log=click.echo))
    except (ConfigError, baseline_steps.BaselineError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(report)


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
