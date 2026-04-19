import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../../core/coordinate_transformer.dart';
import '../../models/feedback_state.dart';
import '../../models/path_step.dart';

class RobotAnimator extends StatefulWidget {
  final int currentStep;
  final List<PathStep> pathSteps;
  final Size imageSize;
  final FeedbackState? feedback;
  final CoordinateTransformer? transformer;

  const RobotAnimator({
    super.key,
    required this.currentStep,
    required this.pathSteps,
    required this.imageSize,
    this.feedback,
    this.transformer,
  });

  @override
  State<RobotAnimator> createState() => _RobotAnimatorState();
}

class _RobotAnimatorState extends State<RobotAnimator> {
  double _left = 0.0;
  double _top = 0.0;
  double _turns = 0.0; // AnimatedRotation uses full turns (1.0 = 360°)
  bool _visible = false;
  bool _missionComplete = false;

  static const double _iconSize = 32.0;

  @override
  void didUpdateWidget(RobotAnimator old) {
    super.didUpdateWidget(old);

    final feedback = widget.feedback;
    final transformer = widget.transformer;

    if (feedback == null || transformer == null) return;

    if (feedback.action == RobotAction.arrived && !_missionComplete) {
      setState(() {
        _missionComplete = true;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Mission complete')),
          );
        }
      });
      return;
    }

    if (feedback.action == RobotAction.moving) {
      final stepIndex = feedback.currentStep;
      if (stepIndex >= 0 && stepIndex < widget.pathSteps.length) {
        final step = widget.pathSteps[stepIndex];
        final (px, py) = transformer.gridToPixel(
          step.gx,
          step.gy,
          widget.imageSize.width,
          widget.imageSize.height,
        );
        setState(() {
          _left = px - _iconSize / 2;
          _top = py - _iconSize / 2;
          _visible = true;
        });
      }
    } else if (feedback.action == RobotAction.turning) {
      // Animate rotation only; do not change position
      setState(() {
        // Convert degrees to turns (AnimatedRotation uses turns where 1.0 = 360°)
        _turns = feedback.heading / 360.0;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_visible) return const SizedBox.shrink();

    return AnimatedPositioned(
      duration: const Duration(milliseconds: 280),
      left: _left,
      top: _top,
      child: AnimatedRotation(
        duration: const Duration(milliseconds: 700),
        turns: _turns,
        child: SizedBox(
          width: _iconSize,
          height: _iconSize,
          child: SvgPicture.asset(
            'assets/robot_icon.svg',
            width: _iconSize,
            height: _iconSize,
          ),
        ),
      ),
    );
  }
}
