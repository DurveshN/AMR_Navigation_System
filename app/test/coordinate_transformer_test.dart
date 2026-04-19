import 'dart:math';
import 'package:flutter_test/flutter_test.dart';
import 'package:amr_navigation/core/coordinate_transformer.dart';
import 'package:amr_navigation/models/map_config.dart';

/// Fixture: resolution=0.1, 10×10 m map, 100×100 grid, origin at (0,0)
const _cfg = MapConfig(
  resolution: 0.1,
  widthMeters: 10.0,
  heightMeters: 10.0,
  gridWidth: 100,
  gridHeight: 100,
  originX: 0.0,
  originY: 0.0,
);

const _transformer = CoordinateTransformer(_cfg);

void main() {
  // ── pixel_to_world ──────────────────────────────────────────────────────────

  test('pixel_to_world center pixel', () {
    // Pixel (500, 499) on a 1000×998 image should map to world ≈ (5.0, 5.005)
    final (wx, wy) = _transformer.pixelToWorld(500, 499, 1000, 998);
    expect(wx, closeTo(5.0, 0.001));
    expect(wy, closeTo(5.005, 0.01));
  });

  test('pixel_to_world bottom-left', () {
    // Pixel (0, 998) is the bottom-left corner → world origin (0, 0)
    final (wx, wy) = _transformer.pixelToWorld(0, 998, 1000, 998);
    expect(wx, closeTo(0.0, 1e-9));
    expect(wy, closeTo(0.0, 1e-9));
  });

  // ── world_to_grid ───────────────────────────────────────────────────────────

  test('world_to_grid known coordinate', () {
    // World (5.0, 5.0) with resolution 0.1 → grid cell (50, 50)
    final (gx, gy) = _transformer.worldToGrid(5.0, 5.0);
    expect(gx, equals(50));
    expect(gy, equals(50));
  });

  // ── grid_to_pixel ───────────────────────────────────────────────────────────

  test('grid_to_pixel known cell', () {
    // Grid (50, 50) on 1000×998 image → pixel (500.0, 499.0)
    final (px, py) = _transformer.gridToPixel(50, 50, 1000, 998);
    expect(px, closeTo(500.0, 1e-9));
    expect(py, closeTo(499.0, 1e-9));
  });

  // ── heading ─────────────────────────────────────────────────────────────────

  test('heading east', () {
    // Moving from (0,0) to (1,0) → 0° (east)
    expect(_transformer.heading(0, 0, 1, 0), closeTo(0.0, 1e-9));
  });

  test('heading north', () {
    // Moving from (0,0) to (0,1) → 90° (north / CCW positive)
    expect(_transformer.heading(0, 0, 0, 1), closeTo(90.0, 1e-9));
  });

  test('heading northwest', () {
    // Moving from (1,0) to (0,1) → 135°
    expect(_transformer.heading(1, 0, 0, 1), closeTo(135.0, 1e-9));
  });

  // ── Property 3: round-trip grid → pixel → world → grid ─────────────────────
  //
  // Validates: Requirements 2.7, 11.1, 11.6

  test('round-trip grid→pixel→world→grid (Property 3)', () {
    final rng = Random(42);
    const imageW = 1000.0;
    const imageH = 998.0;

    for (var i = 0; i < 200; i++) {
      final gxIn = rng.nextInt(100); // 0..99
      final gyIn = rng.nextInt(100);

      final (px, py) = _transformer.gridToPixel(gxIn, gyIn, imageW, imageH);
      final (wx, wy) = _transformer.pixelToWorld(px, py, imageW, imageH);
      final (gxOut, gyOut) = _transformer.worldToGrid(wx, wy);

      expect(
        (gxOut - gxIn).abs(),
        lessThanOrEqualTo(1),
        reason: 'gx round-trip failed for input ($gxIn, $gyIn): got $gxOut',
      );
      expect(
        (gyOut - gyIn).abs(),
        lessThanOrEqualTo(1),
        reason: 'gy round-trip failed for input ($gxIn, $gyIn): got $gyOut',
      );
    }
  });

  // ── Property 4: pixel_to_world formula correctness ──────────────────────────
  //
  // Validates: Requirements 2.7, 11.1, 11.6

  test('pixel_to_world formula (Property 4)', () {
    final rng = Random(42);

    for (var i = 0; i < 100; i++) {
      final px = rng.nextDouble() * 1000.0;
      final py = rng.nextDouble() * 998.0;
      const imageW = 1000.0;
      const imageH = 998.0;

      final (wx, wy) = _transformer.pixelToWorld(px, py, imageW, imageH);

      // Expected values from the formula directly
      final expectedWx = (px / imageW) * _cfg.widthMeters + _cfg.originX;
      final expectedWy =
          (1.0 - py / imageH) * _cfg.heightMeters + _cfg.originY;

      expect(wx, closeTo(expectedWx, 1e-9));
      expect(wy, closeTo(expectedWy, 1e-9));
    }
  });
}
