import 'map_config.dart';

enum MissionPhase { idle, selectStart, selectGoal, planning, executing, complete }

class Mission {
  final String id;
  final MissionPhase phase;
  final MapConfig? mapConfig;

  const Mission({
    required this.id,
    required this.phase,
    this.mapConfig,
  });

  Mission copyWith({
    String? id,
    MissionPhase? phase,
    MapConfig? mapConfig,
  }) {
    return Mission(
      id: id ?? this.id,
      phase: phase ?? this.phase,
      mapConfig: mapConfig ?? this.mapConfig,
    );
  }
}
