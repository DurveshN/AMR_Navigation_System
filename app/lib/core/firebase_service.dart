import 'package:firebase_database/firebase_database.dart';
import '../models/map_config.dart';
import '../models/path_step.dart';

class FirebaseService {
  final DatabaseReference _db;

  FirebaseService() : _db = FirebaseDatabase.instance.ref();

  /// Reads the current mission ID from `/missions/current_mission_id`.
  Future<String?> getCurrentMissionId() async {
    final snapshot = await _db.child('missions/current_mission_id').get();
    if (!snapshot.exists) return null;
    return snapshot.value as String?;
  }

  /// Reads the map config for [missionId] and returns a [MapConfig].
  Future<MapConfig?> getMapConfig(String missionId) async {
    final snapshot =
        await _db.child('missions/$missionId/map_config').get();
    if (!snapshot.exists || snapshot.value == null) return null;
    final data = Map<String, dynamic>.from(snapshot.value as Map);
    return MapConfig.fromJson(data);
  }

  /// Writes [missionId] to `/missions/current_mission_id`.
  Future<void> setCurrentMissionId(String missionId) async {
    await _db.child('missions/current_mission_id').set(missionId);
  }

  /// Writes a waypoint `{wx, wy}` to `/missions/{missionId}/waypoints/{key}`.
  Future<void> writeWaypoint(
    String missionId,
    String key,
    double wx,
    double wy,
  ) async {
    await _db
        .child('missions/$missionId/waypoints/$key')
        .set({'wx': wx, 'wy': wy});
  }

  /// Writes [status] to `/missions/{missionId}/meta/status`.
  Future<void> setStatus(String missionId, String status) async {
    await _db.child('missions/$missionId/meta/status').set(status);
  }

  /// Returns a stream of [DatabaseEvent] for `/missions/{missionId}/path`.
  Stream<DatabaseEvent> watchPath(String missionId) {
    return _db.child('missions/$missionId/path').onValue;
  }

  /// Returns a stream of [DatabaseEvent] for `/missions/{missionId}/feedback`.
  Stream<DatabaseEvent> watchFeedback(String missionId) {
    return _db.child('missions/$missionId/feedback').onValue;
  }

  /// Reads all path steps for [missionId] and returns them sorted by index.
  Future<List<PathStep>> getPathSteps(String missionId) async {
    final snapshot =
        await _db.child('missions/$missionId/path/steps').get();
    if (!snapshot.exists || snapshot.value == null) return [];

    final rawMap = Map<String, dynamic>.from(snapshot.value as Map);
    final entries = rawMap.entries.toList()
      ..sort((a, b) => int.parse(a.key).compareTo(int.parse(b.key)));

    return entries
        .map((e) => PathStep.fromJson(Map<String, dynamic>.from(e.value as Map)))
        .toList();
  }
}
