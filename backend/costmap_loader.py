"""Costmap loader — loads JSON map files and normalises them into numpy arrays.

Supports two JSON shapes:
  Shape A: nested 2D array under "data" key
  Shape B: flat 1D array under "data" key with separate "width" and "height" keys

Returns the numpy grid and a raw metadata dict for downstream use by
coordinate_utils.build_map_config.
"""

import json
from typing import Any

import numpy as np


def load_map(path: str) -> tuple[np.ndarray, dict]:
    """Load a JSON map file and return (grid_array, raw_metadata).

    Auto-detects Shape A (nested 2D array with "data" key where data[0] is a list)
    or Shape B (flat 1D array with "data" key plus "width" and "height" keys).
    Raises ValueError for unrecognised shapes.
    """
    with open(path, "r") as f:
        raw: dict[str, Any] = json.load(f)

    if "data" not in raw:
        raise ValueError(
            f"Unrecognised map shape in {path}: missing 'data' key"
        )

    data = raw["data"]

    # --- Shape detection ---
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
        # Shape A: nested 2D array — each element of data is a row (list of ints)
        # height = number of rows, width = length of first row
        grid = np.array(data, dtype=np.int32)
        height, width = grid.shape  # derive from actual array, not JSON keys
    elif isinstance(data, list) and len(data) > 0 and not isinstance(data[0], list):
        # Candidate for Shape B: flat 1D array — needs "width" and "height" keys
        if "width" in raw and "height" in raw:
            # Shape B: reshape flat array to (height, width) using numpy
            height = int(raw["height"])
            width = int(raw["width"])
            grid = np.array(data, dtype=np.int32).reshape((height, width))
        else:
            raise ValueError(
                f"Unrecognised map shape in {path}: flat 'data' array "
                f"without 'width' and 'height' keys"
            )
    else:
        raise ValueError(
            f"Unrecognised map shape in {path}: 'data' is not a non-empty list"
        )

    # --- Metadata extraction ---
    # Resolution: json["resolution"] > json["cell_size_px"] / 100.0 > 0.05 default
    if "resolution" in raw:
        resolution = float(raw["resolution"])
    elif "cell_size_px" in raw:
        # cell_size_px represents pixels per cell; dividing by 100 gives meters/cell
        resolution = float(raw["cell_size_px"]) / 100.0
    else:
        resolution = 0.05

    # Origin: json["origin"][0], json["origin"][1] if present, else 0.0
    if "origin" in raw and isinstance(raw["origin"], list) and len(raw["origin"]) >= 2:
        origin_x = float(raw["origin"][0])
        origin_y = float(raw["origin"][1])
    else:
        origin_x = 0.0
        origin_y = 0.0

    # Derive width/height from the numpy array shape (not from JSON keys)
    # to avoid mismatch between declared and actual dimensions
    actual_height, actual_width = grid.shape

    # Build raw metadata dict for downstream use by coordinate_utils.build_map_config
    raw_meta: dict[str, Any] = {
        "resolution": resolution,
        "origin_x": origin_x,
        "origin_y": origin_y,
        "width": actual_width,   # grid columns, derived from array shape
        "height": actual_height,  # grid rows, derived from array shape
    }

    return grid, raw_meta
