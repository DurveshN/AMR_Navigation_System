"""A* path planner for the AMR Navigation System.

Provides:
  - AStarNode: dataclass used as heap entries for the priority queue.
  - traversal_cost(): maps cell values to movement costs.
  - octile(): admissible heuristic for 8-directional grids.
  - astar(): core A* search returning a list of (gx, gy) grid cells.
  - _reconstruct(): traces the came_from dict back to the start.
  - plan_path(): full pipeline — world coords → grid → A* → world coords + headings.

Grid indexing convention: grid[gy][gx]  (row = gy, col = gx).
Coordinate convention: ROS — origin bottom-left, Y increases upward.
"""

import heapq
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from coordinate_utils import MapConfig, CoordinateTransformer, compute_heading

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SQRT2 = math.sqrt(2)

DIRECTIONS: list[tuple[int, int]] = [
    (1, 0), (-1, 0), (0, 1), (0, -1),   # cardinal
    (1, 1), (1, -1), (-1, 1), (-1, -1), # diagonal
]


# ---------------------------------------------------------------------------
# AStarNode
# ---------------------------------------------------------------------------

@dataclass(order=True)
class AStarNode:
    """Heap entry for the A* open set.

    Only ``f`` participates in ordering so that ``heapq`` pops the node with
    the lowest estimated total cost first.  All other fields are excluded from
    comparison via ``field(compare=False)``.
    """

    f: float                        # priority = g + h  (ordering key)
    g: float = field(compare=False) # cost accumulated from start
    gx: int  = field(compare=False) # grid column index
    gy: int  = field(compare=False) # grid row index


# ---------------------------------------------------------------------------
# Cost functions
# ---------------------------------------------------------------------------

def traversal_cost(cell_value: int) -> float:
    """Return the traversal cost multiplier for a grid cell value.

    Parameters
    ----------
    cell_value : int
        Raw occupancy value from the inflated costmap.

    Returns
    -------
    float
        ``math.inf`` for obstacle (>= 100) or unknown (-1) cells;
        ``1.0 + (cell_value / 100.0) * 5.0`` for free/inflated cells [0, 99].
    """
    if cell_value >= 100 or cell_value == -1:
        return math.inf
    return 1.0 + (cell_value / 100.0) * 5.0


def octile(dx: int, dy: int) -> float:
    """Octile distance heuristic for 8-directional movement.

    Admissible for weighted grids where the minimum traversal cost is 1.0,
    because the cheapest cardinal step costs ``resolution * 1.0`` and the
    cheapest diagonal step costs ``resolution * sqrt(2) * 1.0``.

    Parameters
    ----------
    dx, dy : int
        Difference in grid column and row indices (sign does not matter).

    Returns
    -------
    float
        ``max(|dx|, |dy|) + (sqrt(2) - 1) * min(|dx|, |dy|)``
    """
    adx, ady = abs(dx), abs(dy)
    return max(adx, ady) + (SQRT2 - 1) * min(adx, ady)


# ---------------------------------------------------------------------------
# Path reconstruction
# ---------------------------------------------------------------------------

def _reconstruct(
    came_from: dict[tuple[int, int], tuple[int, int]],
    goal: tuple[int, int],
) -> list[tuple[int, int]]:
    """Trace the came_from dict from goal back to start and return the path.

    Parameters
    ----------
    came_from : dict
        Maps each visited cell to the cell it was reached from.
    goal : tuple[int, int]
        The goal cell ``(gx, gy)``.

    Returns
    -------
    list[tuple[int, int]]
        Ordered path from start to goal (inclusive).
    """
    path: list[tuple[int, int]] = []
    node = goal
    while node in came_from:
        path.append(node)
        node = came_from[node]
    path.append(node)  # append start (not in came_from)
    path.reverse()
    return path


# ---------------------------------------------------------------------------
# A* search
# ---------------------------------------------------------------------------

def astar(
    grid: np.ndarray,
    config: MapConfig,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> Optional[list[tuple[int, int]]]:
    """Find the minimum-cost path from start to goal using A*.

    Uses 8-directional movement.  Cardinal step cost is
    ``config.resolution * traversal_cost(cell_value)``; diagonal step cost is
    ``config.resolution * sqrt(2) * traversal_cost(cell_value)``.

    Parameters
    ----------
    grid : np.ndarray
        2D occupancy grid with shape ``(height, width)``.  Indexed as
        ``grid[gy][gx]``.
    config : MapConfig
        Spatial configuration (resolution used for step costs).
    start : tuple[int, int]
        Start cell ``(gx, gy)``.
    goal : tuple[int, int]
        Goal cell ``(gx, gy)``.

    Returns
    -------
    list[tuple[int, int]] or None
        Ordered list of ``(gx, gy)`` cells from start to goal (inclusive), or
        ``None`` if no path exists between reachable cells.

    Raises
    ------
    ValueError
        If the start or goal cell has infinite traversal cost (i.e. is an
        obstacle or unknown cell).
    """
    height, width = grid.shape
    sx, sy = start
    gx_goal, gy_goal = goal

    # Validate start and goal are not obstacles
    start_cost = traversal_cost(int(grid[sy][sx]))
    if start_cost == math.inf:
        raise ValueError(
            f"Start cell ({sx}, {sy}) has value {grid[sy][sx]} which is an "
            f"obstacle or unknown cell (traversal cost = inf). "
            f"Please choose a free cell."
        )

    goal_cost = traversal_cost(int(grid[gy_goal][gx_goal]))
    if goal_cost == math.inf:
        raise ValueError(
            f"Goal cell ({gx_goal}, {gy_goal}) has value {grid[gy_goal][gx_goal]} "
            f"which is an obstacle or unknown cell (traversal cost = inf). "
            f"Please choose a free cell."
        )

    # Trivial case: start == goal
    if start == goal:
        return [start]

    # g_score[cell] = best known cost from start to cell
    g_score: dict[tuple[int, int], float] = {start: 0.0}
    came_from: dict[tuple[int, int], tuple[int, int]] = {}

    # Seed the open heap with the start node
    h0 = octile(gx_goal - sx, gy_goal - sy) * config.resolution
    open_heap: list[tuple[float, float, int, int]] = [(h0, 0.0, sx, sy)]

    while open_heap:
        f, g, cx, cy = heapq.heappop(open_heap)

        # Goal reached
        if (cx, cy) == goal:
            return _reconstruct(came_from, goal)

        # Skip stale entries (a better path to this cell was already found)
        if g > g_score.get((cx, cy), math.inf):
            continue

        for dx, dy in DIRECTIONS:
            nx, ny = cx + dx, cy + dy

            # Bounds check
            if not (0 <= nx < width and 0 <= ny < height):
                continue

            tc = traversal_cost(int(grid[ny][nx]))
            if tc == math.inf:
                continue  # skip obstacles

            diagonal = dx != 0 and dy != 0
            move_cost = config.resolution * (SQRT2 if diagonal else 1.0) * tc
            ng = g + move_cost

            if ng < g_score.get((nx, ny), math.inf):
                g_score[(nx, ny)] = ng
                came_from[(nx, ny)] = (cx, cy)
                h = octile(gx_goal - nx, gy_goal - ny) * config.resolution
                heapq.heappush(open_heap, (ng + h, ng, nx, ny))

    return None  # no path found


# ---------------------------------------------------------------------------
# World-level planning pipeline
# ---------------------------------------------------------------------------

def plan_path(
    grid: np.ndarray,
    config: MapConfig,
    start_world: tuple[float, float],
    goal_world: tuple[float, float],
) -> list[dict]:
    """Full planning pipeline: world coordinates → grid → A* → PathStep dicts.

    Converts world coordinates to grid cells, runs A*, then converts each
    grid cell back to world coordinates and computes the heading for each step.

    Heading convention (ROS): 0° = east, 90° = north, counter-clockwise positive.
    For the first step the heading is computed from step[0] → step[1].
    For the last step the heading is reused from the previous step.
    For a single-cell path (start == goal) the heading defaults to 0.0°.

    Parameters
    ----------
    grid : np.ndarray
        2D occupancy grid with shape ``(height, width)``.
    config : MapConfig
        Spatial configuration derived from map JSON metadata.
    start_world : tuple[float, float]
        Start position in world coordinates ``(wx, wy)`` in meters.
    goal_world : tuple[float, float]
        Goal position in world coordinates ``(wx, wy)`` in meters.

    Returns
    -------
    list[dict]
        Ordered list of PathStep dicts, each containing:
        ``{gx, gy, wx, wy, heading}``.

    Raises
    ------
    ValueError
        If the start or goal cell is an obstacle (→ HTTP 400).
    RuntimeError
        If no path exists between the start and goal cells (→ HTTP 422).
    """
    transformer = CoordinateTransformer(config)

    # Convert world coordinates to grid indices
    start_gx, start_gy = transformer.world_to_grid(*start_world)
    goal_gx, goal_gy = transformer.world_to_grid(*goal_world)

    # Run A* — raises ValueError if start/goal is an obstacle
    path = astar(grid, config, (start_gx, start_gy), (goal_gx, goal_gy))

    if path is None:
        raise RuntimeError(
            f"No path found from world ({start_world[0]:.3f}, {start_world[1]:.3f}) "
            f"[grid ({start_gx}, {start_gy})] to world "
            f"({goal_world[0]:.3f}, {goal_world[1]:.3f}) "
            f"[grid ({goal_gx}, {goal_gy})]. "
            f"The two cells may be in disconnected regions of the map."
        )

    # Build PathStep dicts
    steps: list[dict] = []
    n = len(path)

    for i, (gx, gy) in enumerate(path):
        # World coordinates: use cell centre (add 0.5 * resolution)
        wx = config.origin_x + (gx + 0.5) * config.resolution
        wy = config.origin_y + (gy + 0.5) * config.resolution

        # Heading computation
        if n == 1:
            # Single-cell path — no direction of travel
            heading = 0.0
        elif i < n - 1:
            # All steps except the last: heading toward the next step
            next_gx, next_gy = path[i + 1]
            heading = compute_heading(gx, gy, next_gx, next_gy)
        else:
            # Last step: reuse the heading from the previous step
            prev_gx, prev_gy = path[i - 1]
            heading = compute_heading(prev_gx, prev_gy, gx, gy)

        steps.append({
            "gx": gx,
            "gy": gy,
            "wx": wx,
            "wy": wy,
            "heading": heading,
        })

    return steps
