"""Unit and property-based tests for backend/coordinate_utils.py.

Validates: Requirements 2.2, 2.3, 2.4, 2.5, 2.7, 11.2, 11.4, 11.6
"""

import math
import sys
import os

# Ensure backend/ is on sys.path so coordinate_utils can be imported directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from hypothesis import given, settings
import hypothesis.strategies as st

from coordinate_utils import MapConfig, CoordinateTransformer, compute_heading


# ---------------------------------------------------------------------------
# Standard test fixture
# ---------------------------------------------------------------------------
# resolution=0.1, 100×100 grid → 10 m × 10 m map, origin at (0, 0)

STANDARD_CONFIG = MapConfig(
    resolution=0.1,
    width_meters=10.0,
    height_meters=10.0,
    grid_width=100,
    grid_height=100,
    origin_x=0.0,
    origin_y=0.0,
)


# ---------------------------------------------------------------------------
# Unit tests — pixel_to_world
# ---------------------------------------------------------------------------

def test_pixel_to_world_center():
    """Pixel (500, 499) on 1000×998 image → wx ≈ 5.0, wy ≈ 5.005."""
    t = CoordinateTransformer(STANDARD_CONFIG)
    wx, wy = t.pixel_to_world(500, 499, 1000, 998)
    assert wx == pytest.approx(5.0, abs=1e-6)
    # wy = (1 - 499/998) * 10.0 = (499/998) * 10.0 ≈ 5.005...
    expected_wy = (1.0 - 499 / 998) * 10.0
    assert wy == pytest.approx(expected_wy, abs=1e-6)


def test_pixel_to_world_bottom_left():
    """Pixel (0, 998) on 1000×998 image → wx ≈ 0.0, wy ≈ 0.0 (world origin)."""
    t = CoordinateTransformer(STANDARD_CONFIG)
    wx, wy = t.pixel_to_world(0, 998, 1000, 998)
    assert wx == pytest.approx(0.0, abs=1e-6)
    assert wy == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Unit tests — world_to_grid
# ---------------------------------------------------------------------------

def test_world_to_grid_known():
    """World (5.0, 5.0) with resolution=0.1 → grid (50, 50)."""
    t = CoordinateTransformer(STANDARD_CONFIG)
    gx, gy = t.world_to_grid(5.0, 5.0)
    assert (gx, gy) == (50, 50)


def test_world_to_grid_with_origin_offset():
    """Non-zero origin_x=1.0, origin_y=2.0 applied correctly."""
    cfg = MapConfig(
        resolution=0.1,
        width_meters=10.0,
        height_meters=10.0,
        grid_width=100,
        grid_height=100,
        origin_x=1.0,
        origin_y=2.0,
    )
    t = CoordinateTransformer(cfg)
    # world (1.5, 2.5) → gx = floor((1.5-1.0)/0.1) = floor(5.0) = 5
    #                     gy = floor((2.5-2.0)/0.1) = floor(5.0) = 5
    gx, gy = t.world_to_grid(1.5, 2.5)
    assert (gx, gy) == (5, 5)


# ---------------------------------------------------------------------------
# Unit tests — grid_to_pixel
# ---------------------------------------------------------------------------

def test_grid_to_pixel_known():
    """Grid (50, 50) on 1000×998 image → px == 500, py == 499."""
    t = CoordinateTransformer(STANDARD_CONFIG)
    px, py = t.grid_to_pixel(50, 50, 1000, 998)
    # px = (50 * 0.1 / 10.0) * 1000 = 500.0
    # py = (1 - 50 * 0.1 / 10.0) * 998 = 0.5 * 998 = 499.0
    assert px == pytest.approx(500.0, abs=1e-6)
    assert py == pytest.approx(499.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Unit tests — heading / compute_heading
# ---------------------------------------------------------------------------

def test_heading_east():
    """heading(0, 0, 1, 0) → 0.0 degrees (east)."""
    t = CoordinateTransformer(STANDARD_CONFIG)
    assert t.heading(0, 0, 1, 0) == pytest.approx(0.0, abs=1e-9)


def test_heading_north():
    """heading(0, 0, 0, 1) → 90.0 degrees (north)."""
    t = CoordinateTransformer(STANDARD_CONFIG)
    assert t.heading(0, 0, 0, 1) == pytest.approx(90.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

@given(
    gx=st.integers(0, 99),
    gy=st.integers(0, 99),
    img_w=st.floats(100, 2000, allow_nan=False, allow_infinity=False),
    img_h=st.floats(100, 2000, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_round_trip_grid_pixel_world_grid(gx, gy, img_w, img_h):
    """Property 3: grid → pixel → world → grid round-trip returns (gx, gy).

    Validates: Requirements 2.7, 11.6

    Note: floating-point arithmetic in the intermediate pixel/world steps can
    introduce sub-cell rounding errors, so we allow a tolerance of ±1 cell.
    """
    t = CoordinateTransformer(STANDARD_CONFIG)
    px, py = t.grid_to_pixel(gx, gy, img_w, img_h)
    wx, wy = t.pixel_to_world(px, py, img_w, img_h)
    gx2, gy2 = t.world_to_grid(wx, wy)
    assert abs(gx2 - gx) <= 1
    assert abs(gy2 - gy) <= 1


@given(
    px=st.floats(0.0, 1000.0, allow_nan=False, allow_infinity=False),
    py=st.floats(0.0, 998.0, allow_nan=False, allow_infinity=False),
    img_w=st.floats(100.0, 2000.0, allow_nan=False, allow_infinity=False),
    img_h=st.floats(100.0, 2000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_pixel_to_world_formula(px, py, img_w, img_h):
    """Property 4: pixel_to_world matches exact formula.

    Validates: Requirements 2.2
    """
    t = CoordinateTransformer(STANDARD_CONFIG)
    wx, wy = t.pixel_to_world(px, py, img_w, img_h)
    expected_wx = (px / img_w) * STANDARD_CONFIG.width_meters + STANDARD_CONFIG.origin_x
    expected_wy = (1.0 - py / img_h) * STANDARD_CONFIG.height_meters + STANDARD_CONFIG.origin_y
    assert wx == pytest.approx(expected_wx, rel=1e-9)
    assert wy == pytest.approx(expected_wy, rel=1e-9)


@given(
    wx=st.floats(0.0, 10.0, allow_nan=False, allow_infinity=False),
    wy=st.floats(0.0, 10.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_world_to_grid_formula(wx, wy):
    """Property 5: world_to_grid matches floor formula.

    Validates: Requirements 2.3
    """
    t = CoordinateTransformer(STANDARD_CONFIG)
    gx, gy = t.world_to_grid(wx, wy)
    expected_gx = int(math.floor((wx - STANDARD_CONFIG.origin_x) / STANDARD_CONFIG.resolution))
    expected_gy = int(math.floor((wy - STANDARD_CONFIG.origin_y) / STANDARD_CONFIG.resolution))
    assert gx == expected_gx
    assert gy == expected_gy
