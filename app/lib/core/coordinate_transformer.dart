import 'dart:math';
import '../models/map_config.dart';

class CoordinateTransformer {
  final MapConfig _cfg;

  const CoordinateTransformer(this._cfg);

  /// Converts a pixel coordinate to world coordinates (meters).
  ///
  /// Applies a Y-axis flip because screen Y increases downward while
  /// world Y (ROS convention) increases upward.
  (double wx, double wy) pixelToWorld(
    double px,
    double py,
    double imageWidthPx,
    double imageHeightPx,
  ) {
    final wx = (px / imageWidthPx) * _cfg.widthMeters + _cfg.originX;
    final wy = (1.0 - py / imageHeightPx) * _cfg.heightMeters + _cfg.originY;
    return (wx, wy);
  }

  /// Converts world coordinates (meters) to grid cell indices.
  (int gx, int gy) worldToGrid(double wx, double wy) {
    final gx = ((wx - _cfg.originX) / _cfg.resolution).floor();
    final gy = ((wy - _cfg.originY) / _cfg.resolution).floor();
    return (gx, gy);
  }

  /// Converts grid cell indices to pixel coordinates.
  ///
  /// Inverse of pixelToWorld, via the world intermediate.
  (double px, double py) gridToPixel(
    int gx,
    int gy,
    double imageWidthPx,
    double imageHeightPx,
  ) {
    final px =
        ((gx * _cfg.resolution) / _cfg.widthMeters) * imageWidthPx;
    final py =
        (1.0 - (gy * _cfg.resolution) / _cfg.heightMeters) * imageHeightPx;
    return (px, py);
  }

  /// Returns the heading in degrees from cell (gx1, gy1) to (gx2, gy2).
  ///
  /// Uses ROS convention: 0° = east, CCW positive.
  double heading(int gx1, int gy1, int gx2, int gy2) {
    return (atan2(
              (gy2 - gy1).toDouble(),
              (gx2 - gx1).toDouble(),
            ) *
            180.0) /
        pi;
  }
}
