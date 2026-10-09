import pytest

from thwake.area import area_range

KM2 = 1e6


def test_clear_scene_range_is_edge_only() -> None:
    r = area_range(40 * KM2, 100 * KM2, 100 * KM2, 2 * KM2, 0.5)
    assert r.best_km2 == pytest.approx(40)
    assert (r.low_km2, r.high_km2) == pytest.approx((39, 41))
    assert r.valid_fraction == 1


def test_obscured_pixels_widen_the_range() -> None:
    # 20 km² of the 100 km² mask hidden; water is 50% of the clear part.
    r = area_range(40 * KM2, 80 * KM2, 100 * KM2, 0, 0.5)
    assert r.best_km2 == pytest.approx(50)
    assert (r.low_km2, r.high_km2) == pytest.approx((40, 60))
    assert r.valid_fraction == pytest.approx(0.8)


def test_range_is_clamped_to_mask() -> None:
    r = area_range(99 * KM2, 99.5 * KM2, 100 * KM2, 10 * KM2, 0.5)
    assert r.high_km2 == pytest.approx(100)
    r = area_range(1 * KM2, 100 * KM2, 100 * KM2, 1 * KM2, 2.0)
    assert r.low_km2 == 0


def test_nothing_valid_gives_zero_best_and_full_range() -> None:
    r = area_range(0, 0, 100 * KM2, 0, 0.5)
    assert (r.best_km2, r.low_km2, r.high_km2, r.valid_fraction) == (0, 0, 100, 0)


@pytest.mark.parametrize(
    "sums",
    [(-1, 1, 1, 0), (2, 1, 3, 0), (1, 4, 3, 0), (1, 2, 3, 2)],
)
def test_rejects_inconsistent_sums(sums: tuple[float, float, float, float]) -> None:
    with pytest.raises(ValueError):
        area_range(*sums, 0.5)
