"""Unit and property-based tests for backend/costmap_loader.py.

Validates: Requirements 1.2, 1.3, 1.4, 1.5, 11.5
"""

import json
import sys
import os

# Ensure backend/ is on sys.path so costmap_loader can be imported directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import numpy as np
from hypothesis import given, settings
import hypothesis.strategies as st

import costmap_loader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(tmp_path, data: dict) -> str:
    """Write a dict as JSON to a temp file and return the path string."""
    p = tmp_path / "map.json"
    p.write_text(json.dumps(data))
    return str(p)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_load_nested_2d_shape(tmp_path):
    """Shape A: 3×4 nested 2D JSON → array shape (3, 4)."""
    payload = {"data": [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11]]}
    path = _write_json(tmp_path, payload)
    grid, _ = costmap_loader.load_map(path)
    assert grid.shape == (3, 4)


def test_load_flat_array_shape(tmp_path):
    """Shape B: flat array of length 12 with width=4, height=3 → shape (3, 4)."""
    payload = {"data": list(range(12)), "width": 4, "height": 3}
    path = _write_json(tmp_path, payload)
    grid, _ = costmap_loader.load_map(path)
    assert grid.shape == (3, 4)


def test_load_extracts_resolution(tmp_path):
    """JSON with resolution=0.05 → raw_meta["resolution"] == 0.05."""
    payload = {
        "data": [[0, 1], [2, 3]],
        "resolution": 0.05,
    }
    path = _write_json(tmp_path, payload)
    _, raw_meta = costmap_loader.load_map(path)
    assert raw_meta["resolution"] == pytest.approx(0.05)


def test_load_defaults_origin_when_absent(tmp_path):
    """JSON without 'origin' key → origin_x == 0.0 and origin_y == 0.0."""
    payload = {"data": [[0, 1], [2, 3]]}
    path = _write_json(tmp_path, payload)
    _, raw_meta = costmap_loader.load_map(path)
    assert raw_meta["origin_x"] == 0.0
    assert raw_meta["origin_y"] == 0.0


def test_load_raises_on_unknown_shape(tmp_path):
    """JSON with 'data' as a scalar → ValueError with file path in message."""
    import re
    payload = {"data": 42}
    path = _write_json(tmp_path, payload)
    with pytest.raises(ValueError, match=re.escape(path)):
        costmap_loader.load_map(path)


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

@given(h=st.integers(1, 200), w=st.integers(1, 200))
@settings(max_examples=100)
def test_nested_2d_shape_property(h, w):
    """Property 1: Nested-2D JSON normalisation preserves shape.

    Validates: Requirements 1.2
    """
    import tempfile
    data = [[0] * w for _ in range(h)]
    payload = {"data": data}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        path = f.name
    try:
        grid, _ = costmap_loader.load_map(path)
        assert grid.shape == (h, w)
    finally:
        os.unlink(path)


@given(h=st.integers(1, 200), w=st.integers(1, 200))
@settings(max_examples=100)
def test_flat_array_shape_property(h, w):
    """Property 2: Flat-array JSON normalisation preserves shape.

    Validates: Requirements 1.3
    """
    import tempfile
    payload = {"data": [0] * (h * w), "width": w, "height": h}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        path = f.name
    try:
        grid, _ = costmap_loader.load_map(path)
        assert grid.shape == (h, w)
    finally:
        os.unlink(path)
