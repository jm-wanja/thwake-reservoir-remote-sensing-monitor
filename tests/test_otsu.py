import math
import random

import pytest

from thwake.otsu import FALLBACK, OTSU, choose_threshold, histogram_bins, otsu_threshold


def bimodal(
    edges: list[float], modes: tuple[float, float], weights: tuple[float, float]
) -> list[float]:
    width = edges[1] - edges[0]
    counts = []
    for e in edges:
        x = e + width / 2
        counts.append(
            sum(
                w * math.exp(-((x - m) ** 2) / (2 * 0.05**2))
                for m, w in zip(modes, weights, strict=True)
            )
        )
    return counts


def test_threshold_lies_between_two_modes() -> None:
    edges = histogram_bins(-1, 1, 0.01)
    t = otsu_threshold(bimodal(edges, (-0.4, 0.3), (1, 1)), edges)
    assert t is not None and -0.15 < t < 0.05


def test_unbalanced_classes_still_split_between_modes() -> None:
    edges = histogram_bins(-1, 1, 0.01)
    t = otsu_threshold(bimodal(edges, (-0.4, 0.3), (9, 1)), edges)
    assert t is not None and -0.4 < t < 0.3


def test_threshold_separates_samples_like_brute_force() -> None:
    rng = random.Random(1)
    values = [rng.gauss(-20, 1.5) for _ in range(500)] + [rng.gauss(-8, 2) for _ in range(1500)]
    edges = histogram_bins(-35, 5, 0.5)
    counts = [0.0] * len(edges)
    for v in values:
        counts[min(int((v + 35) / 0.5), len(edges) - 1)] += 1
    t = otsu_threshold(counts, edges)
    assert t is not None
    low = [v for v in values if v <= t]
    assert 450 <= len(low) <= 550


def test_single_occupied_bin_has_no_threshold() -> None:
    assert otsu_threshold([0, 5, 0, 0], [0, 1, 2, 3]) is None


def test_two_occupied_bins_split_between_them() -> None:
    assert otsu_threshold([3, 0, 0, 7], [0, 1, 2, 3]) == pytest.approx(1.0)


@pytest.mark.parametrize(("counts", "edges"), [([1], [0]), ([1, 2], [0]), ([1, -1], [0, 1])])
def test_rejects_bad_histograms(counts: list[float], edges: list[float]) -> None:
    with pytest.raises(ValueError):
        otsu_threshold(counts, edges)


def test_choose_threshold_uses_otsu_inside_range() -> None:
    edges = histogram_bins(-1, 1, 0.01)
    t = choose_threshold(bimodal(edges, (-0.4, 0.3), (1, 1)), edges, 0.0, (-0.5, 0.5))
    assert t.method == OTSU


def test_choose_threshold_falls_back_outside_range_or_when_empty() -> None:
    edges = histogram_bins(-1, 1, 0.01)
    far = choose_threshold(bimodal(edges, (0.6, 0.9), (1, 1)), edges, 0.0, (-0.5, 0.5))
    assert (far.value, far.method) == (0.0, FALLBACK)
    empty = choose_threshold([0.0] * len(edges), edges, -18.0, (-25, -12))
    assert (empty.value, empty.method) == (-18.0, FALLBACK)


def test_histogram_bins() -> None:
    edges = histogram_bins(-35, 5, 0.1)
    assert len(edges) == 400
    assert edges[0] == -35 and edges[-1] == pytest.approx(4.9)
    with pytest.raises(ValueError):
        histogram_bins(1, 0, 0.1)
