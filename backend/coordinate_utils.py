"""Coordinate utilities — stateless coordinate math for the AMR Navigation System.

Provides:
  - MapConfig dataclass: all spatial parameters derived from map JSON metadata.
  - build_map_config(): factory that derives MapConfig from a numpy grid and raw metadata.
  - CoordinateTransformer: converts between pixel, world, and grid coordinate spaces.
  - compute_heading(): module-level heading computation function.

Coordinate spaces:
  Pixel  — origin top-left, Y increases downward (screen convention).
  World  — origin bottom-left, Y increases upward (ROS convention).
  Grid   — origin bottom-left, Y increases upward, units are cell indices.

All formulas include the origin offset so the system works with any ROS map
that has a non-zero origin.
"""

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class MapConfig:
    """Spatial configuration derived from map JSON metadata.

    No hardcoded dimensions — all values are computed from the grid array shape
    and the raw metadata dictionary returned by costmap_loader.load_map().
    """

    resolution: float       # meters per grid cell (e.g. 0.1)
    width_meters: float     # total map width in meters (grid_width * resolution)
    height_meters: float    # total map height in meters (grid_height * resolution)
    grid_width: int         # number of grid columns
    grid_height: int        # number of grid rows
    origin_x: float         # world X of grid cell (0,0) in meters
    origin_y: float         # world Y of grid cell (0,0) in meters


def build_map_config(grid: np.ndarray, raw_meta: dict) -> MapConfig:
    """Derive a MapConfig from the grid array shape and raw metadata dict.

    Parameters
    ----------
    grid : np.ndarray
        The 2D occupancy grid with shape (height, width).
    raw_meta : dict
        Raw metadata dict as returned by costmap_loader.load_map(), containing
        at minimum 'resolution', 'origin_x', 'origin_y', 'width', 'height'.

    Returns
    -------
    MapConfig
        Fully populated configuration with no hardcoded dimensions.
    """
    # Derive grid dimensions from the actual numpy array shape (rows=height, cols=width)
    grid_height, grid_width = grid.shape

    resolution = float(raw_meta["resolution"])
    origin_x = float(raw_meta["origin_x"])
    origin_y = float(raw_meta["origin_y"])

    # Compute world-space extents: total meters = number of cells * meters per cell
    width_meters = grid_width * resolution
    height_meters = grid_height * resolution

    return MapConfig(
        resolution=resolution,
        width_meters=width_meters,
        height_meters=height_meters,
        grid_width=grid_width,
        grid_height=grid_height,
        origin_x=origin_x,
        origin_y=origin_y,
    )


class CoordinateTransformer:
    """Converts between pixel, world, and grid coordinate spaces.

    All conversions use the MapConfig passed at construction time.
    No hardcoded spatial dimensions are stored or used.
    """

    def __init__(self, config: MapConfig):
        self._cfg = config

    def pixel_to_world(
        self, px: float, py: float, image_width_px: float, image_height_px: float
    ) -> tuple[float, float]:
        """Convert pixel coordinates to world coordinates.

        Parameters
        ----------
        px, py : float
            Pixel position (origin top-left, Y down).
        image_width_px, image_height_px : float
            Rendered image dimensions in pixels.

        Returns
        -------
        tuple[float, float]
            World coordinates (wx, wy) in meters.
        """
        # X: scale pixel fraction to world width, then shift by origin offset.
        # px/image_width_px gives the normalised horizontal position [0,1],
        # multiplied by width_meters gives world distance, plus origin_x shifts the frame.
        wx = (px / image_width_px) * self._cfg.width_meters + self._cfg.origin_x

        # Y: apply Y-axis flip (screen Y-down → ROS Y-up), scale to world height,
        # then shift by origin offset.
        # (1 - py/image_height_px) flips the vertical axis so that py=0 maps to
        # the top of the world and py=image_height maps to origin_y.
        wy = (1.0 - py / image_height_px) * self._cfg.height_meters + self._cfg.origin_y

        return wx, wy

    def world_to_grid(self, wx: float, wy: float) -> tuple[int, int]:
        """Convert world coordinates to grid cell indices.

        Parameters
        ----------
        wx, wy : float
            World position in meters (ROS convention, origin bottom-left).

        Returns
        -------
        tuple[int, int]
            Grid indices (gx, gy) where gx is the column and gy is the row.
        """
        # Subtract origin offset to get distance from grid origin, then divide by
        # resolution to convert meters to cell indices. Floor ensures we land in
        # the correct cell (cells span [i*res, (i+1)*res)).
        gx = int(math.floor((wx - self._cfg.origin_x) / self._cfg.resolution))

        # Same logic for Y axis — origin_y shifts the world frame relative to grid.
        gy = int(math.floor((wy - self._cfg.origin_y) / self._cfg.resolution))

        return gx, gy

    def grid_to_pixel(
        self, gx: int, gy: int, image_width_px: float, image_height_px: float
    ) -> tuple[float, float]:
        """Convert grid cell indices to pixel coordinates.

        This is the inverse of pixel_to_world composed with world_to_grid.

        Parameters
        ----------
        gx, gy : int
            Grid cell indices (column, row).
        image_width_px, image_height_px : float
            Rendered image dimensions in pixels.

        Returns
        -------
        tuple[float, float]
            Pixel coordinates (px, py) with origin top-left.
        """
        # X: convert grid index to a fraction of the total grid width, then scale
        # to image pixels. (gx * resolution) gives world distance from origin,
        # dividing by width_meters normalises to [0,1], multiplying by image_width_px
        # gives the pixel position. Origin offset cancels in the round-trip because
        # pixel space is relative to the image, not the world frame.
        px = ((gx * self._cfg.resolution) / self._cfg.width_meters) * image_width_px

        # Y: same normalisation but with Y-axis flip to convert from ROS Y-up to
        # screen Y-down. (1 - fraction) inverts the vertical axis.
        py = (1.0 - (gy * self._cfg.resolution) / self._cfg.height_meters) * image_height_px

        return px, py

    def heading(self, gx1: int, gy1: int, gx2: int, gy2: int) -> float:
        """Compute heading between two grid positions in degrees.

        Uses ROS convention: 0° = east, 90° = north, counter-clockwise positive.

        Parameters
        ----------
        gx1, gy1 : int
            Source grid cell.
        gx2, gy2 : int
            Destination grid cell.

        Returns
        -------
        float
            Heading in degrees.
        """
        # atan2(dy, dx) gives the angle from the positive X-axis (east) in radians.
        # dy = gy2 - gy1 is the grid row difference (Y component in ROS frame).
        # dx = gx2 - gx1 is the grid column difference (X component).
        # Convert radians to degrees for the ROS heading convention.
        return math.degrees(math.atan2(gy2 - gy1, gx2 - gx1))


def compute_heading(gx1: int, gy1: int, gx2: int, gy2: int) -> float:
    """Module-level heading computation between two grid positions.

    Uses ROS convention: 0° = east, 90° = north, counter-clockwise positive.
    Equivalent to degrees(atan2(gy2 - gy1, gx2 - gx1)).

    Parameters
    ----------
    gx1, gy1 : int
        Source grid cell.
    gx2, gy2 : int
        Destination grid cell.

    Returns
    -------
    float
        Heading in degrees.
    """
    # atan2(dy, dx) gives the angle from east (positive X-axis).
    # dy = gy2 - gy1 is the vertical component, dx = gx2 - gx1 is horizontal.
    return math.degrees(math.atan2(gy2 - gy1, gx2 - gx1))
