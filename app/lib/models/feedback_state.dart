enum RobotAction { moving, turning, arrived, obstacleDetected, error }

class FeedbackState {
  final int currentStep;
  final RobotAction action;
  final double heading;
  final int battery;

  const FeedbackState({
    required this.currentStep,
    required this.action,
    required this.heading,
    required this.battery,
  });

  factory FeedbackState.fromJson(Map<String, dynamic> json) => FeedbackState(
        currentStep: json['current_step'] as int,
        action: RobotAction.values.firstWhere(
          (e) => e.name == _toCamel(json['action'] as String),
        ),
        heading: (json['heading'] as num).toDouble(),
        battery: json['battery'] as int,
      );
}

/// Converts snake_case action strings from Firebase (e.g. "obstacle_detected")
/// to camelCase enum names (e.g. "obstacleDetected").
String _toCamel(String snake) {
  final parts = snake.split('_');
  if (parts.length == 1) return snake;
  return parts.first +
      parts
          .skip(1)
          .map((p) => p[0].toUpperCase() + p.substring(1))
          .join();
}
