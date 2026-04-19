"""Unit and property-based tests for backend/pathfinder.py.

Validates: Requirements 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 11.3
"""

import math
import sys
import os

# Ensure backend/ is on sys.path so pathfinder can be imported directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import numpy as np
from hypothesis import given, settings, assume
import hypothesis.strategies as st

from coordinate_utils import MapConfig
from pathfinder import astar, traversal_cost


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

STANDARD_CONFIG = MapConfig(
    resolution=0.1,
    width_meters=1.0,
    height_meters=1.0,
    grid_width=10,
    grid_height=10,
    origin_x=0.0,
    origin_y=0.0,
)


def _open_grid(rows: int = 10, cols: int = 10) -> np.ndarray:
    """Return an all-zero (obstacle-free) grid of the given size."""
    return np.zeros((rows, cols), dtype=np.int32)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_finds_path_in_open_grid():
    """10×10 all-zero grid, start (0,0), goal (9,9) → path is not None and non-empty."""
    grid = _open_grid()
    path = astar(grid, STANDARD_CONFIG, (0, 0), (9, 9))
    assert path is not None
    assert len(path) > 0


def test_no_path_when_goal_unreachable():
    """Goal surrounded by obstacle cells (value=100) → astar returns None."""
    grid = _open_grid()
    # Surround cell (5, 5) with obstacles on all 8 neighbours
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = 5 + dx, 5 + dy
            if 0 <= nx < 10 and 0 <= ny < 10:
                grid[ny][nx] = 100
    # Also wall off the entire row/column to ensure no path
    # Surround with a full ring at distance 2
    for i in range(10):
        grid[3][i] = 100  # row 3 — full horizontal wall
    result = astar(grid, STANDARD_CONFIG, (0, 0), (5, 5))
    assert result is None


def test_raises_on_obstacle_start():
    """Start cell value 100 → ValueError is raised."""
    grid = _open_grid()
    grid[0][0] = 100  # start cell is an obstacle
    with pytest.raises(ValueError):
        astar(grid, STANDARD_CONFIG, (0, 0), (9, 9))


def test_raises_on_obstacle_goal():
    """Goal cell value -1 → ValueError is raised."""
    grid = _open_grid()
    grid[9][9] = -1  # goal cell is unknown/obstacle
    with pytest.raises(ValueError):
        astar(grid, STANDARD_CONFIG, (0, 0), (9, 9))


def test_path_avoids_obstacles():
    """Path through grid with obstacles → no step has traversal_cost == inf."""
    grid = _open_grid()
    # Place a vertical wall at column 5, leaving a gap at row 0
    for row in range(1, 10):
        grid[row][5] = 100
    path = astar(grid, STANDARD_CONFIG, (0, 0), (9, 9))
    assert path is not None
    for gx, gy in path:
        assert traversal_cost(int(grid[gy][gx])) != math.inf


def test_path_is_connected():
    """Each consecutive step pair satisfies |dx| <= 1 and |dy| <= 1."""
    grid = _open_grid()
    path = astar(grid, STANDARD_CONFIG, (0, 0), (9, 9))
    assert path is not None
    for i in range(len(path) - 1):
        gx1, gy1 = path[i]
        gx2, gy2 = path[i + 1]
        assert abs(gx2 - gx1) <= 1
        assert abs(gy2 - gy1) <= 1


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

@given(v=st.integers(-1, 255))
def test_traversal_cost_formula(v):
    """Property 6: traversal_cost piecewise formula correctness.

    Validates: Requirements 3.4
    """
    cost = traversal_cost(v)
    if v >= 100 or v == -1:
        assert cost == math.inf
    else:
        # v in [0, 99]
        expected = 1.0 + (v / 100.0) * 5.0
        assert cost == pytest.approx(expected, rel=1e-9)


@given(
    start=st.tuples(st.integers(0, 9), st.integers(0, 9)),
    goal=st.tuples(st.integers(0, 9), st.integers(0, 9)),
)
@settings(max_examples=200)
def test_path_valid_connected_obstacle_free(start, goal):
    """Property 7: A* path is valid, connected, and obstacle-free on a 10×10 zero grid.

    Validates: Requirements 3.7, 3.8, 3.3
    """
    assume(start != goal)

    grid = _open_grid(10, 10)
    path = astar(grid, STANDARD_CONFIG, start, goal)

    # On an all-zero grid a path must always exist between any two distinct cells
    assert path is not None
    assert len(path) >= 2

    # Path starts at start and ends at goal
    assert path[0] == start
    assert path[-1] == goal

    # Each consecutive step is an 8-directional neighbour
    for i in range(len(path) - 1):
        gx1, gy1 = path[i]
        gx2, gy2 = path[i + 1]
        assert abs(gx2 - gx1) <= 1
        assert abs(gy2 - gy1) <= 1

    # No cell in the path has infinite traversal cost
    for gx, gy in path:
        assert traversal_cost(int(grid[gy][gx])) != math.inf
