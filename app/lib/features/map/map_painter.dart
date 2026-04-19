import 'package:flutter/material.dart';
import '../../core/coordinate_transformer.dart';
import '../../models/path_step.dart';

class MapPainter extends CustomPainter {
  final List<PathStep> pathSteps;
  final int currentStep;
  final Offset? startPixel;
  final Offset? goalPixel;
  final Size imageSize;
  final CoordinateTransformer transformer;

  const MapPainter({
    required this.pathSteps,
    required this.currentStep,
    required this.imageSize,
    required this.transformer,
    this.startPixel,
    this.goalPixel,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (pathSteps.isEmpty) {
      _drawMarkers(canvas);
      return;
    }

    // Convert all path steps to pixel coordinates
    final pixels = pathSteps.map((step) {
      final (px, py) = transformer.gridToPixel(
        step.gx,
        step.gy,
        imageSize.width,
        imageSize.height,
      );
      return Offset(px, py);
    }).toList();

    // Draw traversed segment (index < currentStep) in grey
    if (currentStep > 1) {
      final greyPaint = Paint()
        ..color = Colors.grey
        ..strokeWidth = 1.5
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round;

      final greyPath = Path();
      greyPath.moveTo(pixels[0].dx, pixels[0].dy);
      for (int i = 1; i < currentStep && i < pixels.length; i++) {
        greyPath.lineTo(pixels[i].dx, pixels[i].dy);
      }
      canvas.drawPath(greyPath, greyPaint);
    }

    // Draw upcoming segment (index >= currentStep) in green
    if (currentStep < pixels.length) {
      final greenPaint = Paint()
        ..color = Colors.green
        ..strokeWidth = 2.0
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round;

      final greenPath = Path();
      final startIdx = currentStep > 0 ? currentStep - 1 : 0;
      greenPath.moveTo(pixels[startIdx].dx, pixels[startIdx].dy);
      for (int i = startIdx + 1; i < pixels.length; i++) {
        greenPath.lineTo(pixels[i].dx, pixels[i].dy);
      }
      canvas.drawPath(greenPath, greenPaint);
    }

    _drawMarkers(canvas);
  }

  void _drawMarkers(Canvas canvas) {
    // Draw start marker as blue filled circle
    if (startPixel != null) {
      final bluePaint = Paint()
        ..color = Colors.blue
        ..style = PaintingStyle.fill;
      canvas.drawCircle(startPixel!, 8.0, bluePaint);
    }

    // Draw goal marker as red filled circle
    if (goalPixel != null) {
      final redPaint = Paint()
        ..color = Colors.red
        ..style = PaintingStyle.fill;
      canvas.drawCircle(goalPixel!, 8.0, redPaint);
    }
  }

  @override
  bool shouldRepaint(MapPainter old) {
    return old.currentStep != currentStep || old.pathSteps != pathSteps;
  }
}
