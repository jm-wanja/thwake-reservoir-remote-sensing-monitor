"""Write CSV, GeoJSON and media outputs; append to the canonical time series idempotently.

So far only the AEV-curve figure (Phase 1) is implemented; the time-series outputs follow
in prompt 08. See docs/architecture.md §3B and §6.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from thwake.volume import AEVCurve

# Categorical slots 1–2 of the reference palette (dataviz skill), one per DEM, in the
# order of baseline.aev_dems. Text and reference marks use neutral inks, not series colours.
SERIES_COLOURS = ("#2a78d6", "#eb6834")
INK, INK_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def plot_aev_curve(curves: Mapping[str, AEVCurve], metadata: Mapping[str, Any], path: Path) -> None:
    """Plot area and volume against water level for each DEM (two panels, shared level axis).

    Reference marks: the FSL, the official area at FSL, the current design capacity and the
    design-history range of capacities at the same FSL.

    Args:
        curves: Curves by DEM short name (plotted in this order).
        metadata: The AEV metadata (``aev_curve_v1.json``) for labels and reference values.
        path: PNG to write (parent directories are created).
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dems = metadata["dems"]
    fsl = metadata["full_supply_level_m_asl"]
    first = dems[next(iter(curves))]["capacity_check"]
    design, (hist_low, hist_high) = first["design_capacity_mcm"], first["design_history_mcm"]

    plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK_MUTED, "text.color": INK})
    fig, (ax_area, ax_vol) = plt.subplots(
        1, 2, figsize=(10, 4.8), sharey=True, dpi=150, facecolor=SURFACE
    )
    for ax in (ax_area, ax_vol):
        ax.set_facecolor(SURFACE)
        ax.grid(color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(colors=INK_MUTED)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.axhline(fsl, color=INK_MUTED, linewidth=1, linestyle=(0, (4, 3)))

    for colour, (name, c) in zip(SERIES_COLOURS, curves.items(), strict=False):
        label = f"{dems[name]['label']} (acquired {dems[name]['acquired'].replace('/', '–')})"
        ax_area.plot(c.areas_km2, c.levels_m, color=colour, linewidth=2, label=label)
        ax_vol.plot(c.volumes_mcm, c.levels_m, color=colour, linewidth=2, label=label)
        ax_vol.plot(
            c.top_volume_mcm,
            fsl,
            "o",
            color=colour,
            markersize=7,
            markeredgecolor=SURFACE,
            markeredgewidth=2,
        )

    # Reference marks sit just above the FSL line, clear of the curves: the current design
    # capacity (diamond), the range across design stages (bracket), the official area.
    ref_y = fsl + 3
    ax_vol.plot([hist_low, hist_high], [ref_y] * 2, color=INK_MUTED, linewidth=1.5)
    for x in (hist_low, hist_high):
        ax_vol.plot([x, x], [ref_y - 0.8, ref_y + 0.8], color=INK_MUTED, linewidth=1.5)
    ax_vol.plot(design, ref_y, "D", color=INK, markersize=6)
    ax_vol.annotate(
        "design",
        (design, ref_y),
        xytext=(-8, 0),
        textcoords="offset points",
        ha="right",
        va="center",
        color=INK_MUTED,
        fontsize=8,
    )
    official_area = metadata["max_extent"].get("official_area_km2")
    if official_area is not None:
        ax_area.plot(official_area, ref_y, "D", color=INK, markersize=6)
        ax_area.annotate(
            f"official ~{official_area:g} km²",
            (official_area, ref_y),
            xytext=(-8, 0),
            textcoords="offset points",
            ha="right",
            va="center",
            color=INK_MUTED,
            fontsize=8,
        )
    ax_area.annotate(
        f"FSL {fsl:g} m",
        (0, fsl),
        xytext=(4, -10),
        textcoords="offset points",
        color=INK_MUTED,
        fontsize=8,
    )
    readout = [f"At FSL {fsl:g} m a.s.l.:"]
    for name, c in curves.items():
        check = dems[name]["capacity_check"]
        readout.append(
            f"{dems[name]['label']}: {c.top_volume_mcm:.0f} MCM ({check['vs_design_pct']:+.0f}%)"
        )
    readout += [
        f"Design capacity: {design:g} MCM (diamond)",
        f"Earlier designs: {hist_low:g}–{hist_high:g} MCM (bracket)",
    ]
    ax_vol.text(
        0.98,
        0.04,
        "\n".join(readout),
        transform=ax_vol.transAxes,
        ha="right",
        va="bottom",
        color=INK,
        fontsize=8,
        linespacing=1.5,
    )
    ax_area.set_ylim(top=fsl + 6)

    ax_area.set_xlabel("Water area (km²)")
    ax_vol.set_xlabel("Stored volume (million m³)")
    ax_area.set_ylabel("Water level (m above sea level)")
    ax_area.set_xlim(left=0)
    ax_vol.set_xlim(left=0)
    ax_area.legend(loc="lower right", frameon=False, fontsize=8)
    fig.suptitle(
        "Thwake reservoir: area and volume by water level from two pre-dam elevation "
        f"models (curve {metadata['method_version']}, baseline v1)",
        x=0.01,
        ha="left",
        fontsize=11,
        color=INK,
    )
    fig.text(
        0.01,
        0.01,
        "Inside the same max-extent mask (pre-dam Copernicus GLO-30 ≤ FSL, upstream of the "
        "wall). The spread between DEMs is part of the volume uncertainty. "
        "Sources: Copernicus DEM GLO-30 (ESA), SRTM (NASA/USGS); design figures from "
        "data/external/official_figures.csv.",
        fontsize=7,
        color=INK_MUTED,
        wrap=True,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
