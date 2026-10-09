"""Write CSV, GeoJSON and media outputs; append to the canonical time series idempotently.

So far the AEV-curve figure (Phase 1) and the reference-validation figure (Phase 1.5)
are implemented; the time-series outputs follow in prompt 08. See docs/architecture.md §3B and §6.
"""

from __future__ import annotations

import textwrap
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from thwake.volume import AEVCurve

# Categorical slots 1–2 of the reference palette (dataviz skill), one per DEM, in the
# order of baseline.aev_dems. Text and reference marks use neutral inks, not series colours.
SERIES_COLOURS = ("#2a78d6", "#eb6834")
INK, INK_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
DEM_SHORT = {"copernicus_glo30": "GLO-30", "srtm": "SRTM"}


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


def _style_axes(ax: Any) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK_MUTED, labelsize=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


# Sensor identity is carried by marker shape (colour is reserved for the DEM).
SENSOR_MARKERS = {"S2": "o", "S1": "^"}
SENSOR_LABELS = {"S2": "Sentinel-2", "S1": "Sentinel-1"}
# Reference-line labels sit on a surface-coloured box so data marks never cut through them.
LABEL_BOX = {"facecolor": SURFACE, "edgecolor": "none", "pad": 1.0, "alpha": 0.85}


def plot_validation_reference(
    series: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    altimetry_rows: Sequence[Mapping[str, Any]],
    targets: Sequence[Any],
    surfaces: Mapping[str, Any],
    dems: Sequence[str],
    settings: Any,
    path: Path,
) -> None:
    """Reference-reservoir validation figure (docs/validation.md).

    Left, top: water area of every usable scene over time (range bars: obscured pixels and
    shoreline pixels). Left, bottom: our level per DEM (colour) and sensor (marker) with the
    published gauge levels (ink diamonds; hollow = low confidence) and each DEM's flat water
    surface, below which no level can be estimated. Right: our level against the published
    level for every matched date, with the 1:1 line.

    Args:
        series: Rows from :func:`thwake.validation.series_rows`.
        rows: Rows from :func:`thwake.validation.comparison_rows` (gauge).
        altimetry_rows: The same for the altimetry series (may be empty).
        targets: Published levels inside the scene window.
        surfaces: :class:`thwake.validation.WaterSurface` per DEM.
        dems: DEM short names, in colour order.
        settings: :class:`thwake.validation.ReferenceSettings`.
        path: PNG to write.
    """
    from datetime import date

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    colours = dict(zip(dems, SERIES_COLOURS, strict=False))
    labels = {d: DEM_SHORT.get(d, d) for d in dems}
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK_MUTED, "text.color": INK})
    fig = plt.figure(figsize=(12, 7.4), dpi=150, facecolor=SURFACE)
    grid = fig.add_gridspec(2, 2, width_ratios=(2.1, 1), hspace=0.32, wspace=0.22)
    ax_area = fig.add_subplot(grid[0, 0])
    ax_level = fig.add_subplot(grid[1, 0], sharex=ax_area)
    ax_cmp = fig.add_subplot(grid[:, 1])
    for ax in (ax_area, ax_level, ax_cmp):
        _style_axes(ax)

    usable = [r for r in series if r["qa_flag"] == "ok"]
    for sensor, marker in SENSOR_MARKERS.items():
        pts = [r for r in usable if r["sensor"] == sensor]
        if not pts:
            continue
        x: Any = [date.fromisoformat(r["date"]) for r in pts]
        best = [float(r["area_km2"]) for r in pts]
        low = [b - float(r["area_km2_low"]) for b, r in zip(best, pts, strict=True)]
        high = [float(r["area_km2_high"]) - b for b, r in zip(best, pts, strict=True)]
        filled = sensor == "S2"
        ax_area.errorbar(
            x,
            best,
            yerr=[low, high],
            fmt=marker,
            markersize=4,
            color=INK if filled else INK_MUTED,
            markerfacecolor=INK if filled else SURFACE,
            ecolor=GRID,
            elinewidth=1,
            label=f"{SENSOR_LABELS[sensor]} ({len(pts)} scenes)",
        )
    for dem in dems:
        s = surfaces[dem]
        if s.level_m is not None:
            ax_area.axhline(s.area_km2, color=colours[dem], linewidth=1, linestyle=(0, (4, 3)))
            ax_area.annotate(
                f"{labels[dem]} flat lake surface ({s.area_km2:.0f} km²)",
                (0.0, s.area_km2),
                xycoords=("axes fraction", "data"),
                xytext=(4, -10),
                textcoords="offset points",
                fontsize=7,
                color=INK_MUTED,
                bbox=LABEL_BOX,
            )
    skipped = len(series) - len(usable)
    ax_area.set_ylabel("Water area (km²)")
    ax_area.set_title(
        f"Water area inside the mask, every usable scene ({skipped} low-coverage scenes left out)",
        loc="left",
        fontsize=9,
        color=INK,
    )
    ax_area.legend(loc="lower left", frameon=False, fontsize=7.5)

    for dem in dems:
        for sensor, marker in SENSOR_MARKERS.items():
            pts = [r for r in usable if r["sensor"] == sensor and r[f"level_status_{dem}"] == "ok"]
            days: Any = [date.fromisoformat(r["date"]) for r in pts]
            ax_level.plot(
                days,
                [float(r[f"level_m_{dem}"]) for r in pts],
                marker,
                markersize=3.5,
                color=colours[dem],
                markerfacecolor=colours[dem] if sensor == "S2" else SURFACE,
                markeredgewidth=0.8,
                alpha=0.85,
            )
        s = surfaces[dem]
        if s.level_m is not None:
            ax_level.axhline(s.level_m, color=colours[dem], linewidth=1, linestyle=(0, (4, 3)))
            ax_level.annotate(
                f"{labels[dem]} lake surface {s.level_m:g} m: no estimate below",
                (0.0, s.level_m),
                xycoords=("axes fraction", "data"),
                xytext=(4, -10),
                textcoords="offset points",
                fontsize=7,
                color=INK_MUTED,
                bbox=LABEL_BOX,
            )
    for t in targets:
        ax_level.plot(
            [t.mid],
            [t.level_m],
            "D",
            markersize=6.5,
            color=INK,
            markerfacecolor=INK if t.headline else SURFACE,
            markeredgecolor=INK,
            markeredgewidth=1.2,
            zorder=5,
        )
    alt = sorted(
        {(r["published_date"], r["published_level_m"]) for r in altimetry_rows}, key=lambda x: x[0]
    )
    if alt:
        alt_days: Any = [date.fromisoformat(d) for d, _ in alt]
        ax_level.plot(
            alt_days,
            [v for _, v in alt],
            color=INK_MUTED,
            linewidth=1,
            marker=".",
            markersize=3,
            zorder=4,
        )
    ax_level.axhline(settings.fsl_m, color=INK_MUTED, linewidth=1, linestyle=(0, (1, 2)))
    ax_level.annotate(
        f"FSL {settings.fsl_m:g} m",
        (0.0, settings.fsl_m),
        xycoords=("axes fraction", "data"),
        xytext=(4, 3),
        textcoords="offset points",
        fontsize=7,
        color=INK_MUTED,
        bbox=LABEL_BOX,
    )
    ax_level.set_ylabel("Water level (m above sea level)")
    ax_level.set_title(
        "Level from area via each DEM curve, KenGen gauge levels"
        + (" and DAHITI altimetry (grey line)" if alt else ""),
        loc="left",
        fontsize=9,
        color=INK,
    )

    lims: list[float] = []
    for r in rows:
        level = _num(r["level_m"])
        if level is None:
            continue
        pub = float(r["published_level_m"])
        lo, hi = _num(r["level_m_low"]), _num(r["level_m_high"])
        solid = r["status"] == "ok" and r["headline"]
        colour = colours[r["dem"]]
        ax_cmp.errorbar(
            [pub],
            [level],
            yerr=[[level - lo if lo is not None else 0], [hi - level if hi is not None else 0]],
            fmt=SENSOR_MARKERS[r["sensor"]],
            markersize=6,
            color=colour,
            markerfacecolor=colour if solid else SURFACE,
            markeredgecolor=colour,
            ecolor=colour,
            elinewidth=1,
            alpha=1 if solid else 0.7,
        )
        lims += [pub, level]
    if lims:
        lo_lim, hi_lim = min(lims) - 1, max(lims) + 1
        ax_cmp.plot([lo_lim, hi_lim], [lo_lim, hi_lim], color=INK_MUTED, linewidth=1)
        ax_cmp.set_xlim(lo_lim, hi_lim)
        ax_cmp.set_ylim(lo_lim, hi_lim)
        ax_cmp.annotate(
            "1:1",
            (hi_lim, hi_lim),
            xytext=(-14, -12),
            textcoords="offset points",
            fontsize=7,
            color=INK_MUTED,
        )
    ax_cmp.set_aspect("equal", adjustable="box")
    ax_cmp.set_xlabel("Published gauge level (m)")
    ax_cmp.set_ylabel("Our level from satellite area (m)")
    ax_cmp.set_title("Matched dates (filled = headline)", loc="left", fontsize=9, color=INK)

    handles = [
        Line2D([], [], color=colours[d], marker="s", linestyle="", markersize=7, label=labels[d])
        for d in dems
    ]
    handles += [
        Line2D(
            [],
            [],
            color=INK_MUTED,
            marker=m,
            linestyle="",
            markersize=6,
            markerfacecolor=INK_MUTED if s == "S2" else SURFACE,
            label=SENSOR_LABELS[s],
        )
        for s, m in SENSOR_MARKERS.items()
    ]
    handles += [
        Line2D([], [], color=INK, marker="D", linestyle="", markersize=6, label="KenGen level"),
        Line2D(
            [],
            [],
            color=INK,
            marker="D",
            linestyle="",
            markersize=6,
            markerfacecolor=SURFACE,
            label="KenGen, low confidence",
        ),
    ]
    if alt:
        label = textwrap.fill(settings.altimetry_label, 30)
        handles.append(Line2D([], [], color=INK_MUTED, marker=".", label=label))
    # Below the panel: the equal-aspect axes leave room there, and no mark is covered.
    ax_cmp.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(-0.02, -0.13),
        ncol=2,
        frameon=False,
        fontsize=7.5,
    )

    fig.suptitle(
        f"Validation on {settings.name}: water level from satellite area vs published gauge levels",
        x=0.01,
        ha="left",
        fontsize=11,
        color=INK,
    )
    fig.text(
        0.01,
        0.01,
        "Area: Sentinel-2 MNDWI and Sentinel-1 VV, Otsu thresholds, inside a GLO-30 mask at "
        f"{settings.mask_level_m:g} m. Both DEMs postdate the dam, so each shows the lake "
        "flat at its acquisition-date level. Gauge levels: KenGen statements "
        "(data/external/reference_reservoirs.csv). "
        + ("Altimetry: DAHITI, DGFI-TUM (Schwatke et al. 2015). " if alt else "")
        + "Indicator of method accuracy, not an official record.",
        fontsize=7,
        color=INK_MUTED,
        wrap=True,
    )
    fig.subplots_adjust(left=0.06, right=0.98, top=0.91, bottom=0.09)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
