import 'dart:async';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:firebase_database/firebase_database.dart';
import '../../core/api_client.dart';
import '../../core/coordinate_transformer.dart';
import '../../core/firebase_service.dart';
import '../../models/feedback_state.dart';
import '../../models/map_config.dart';
import '../../models/mission.dart';
import '../../models/path_step.dart';

class MissionState {
  final MapConfig? mapConfig;
  final CoordinateTransformer? transformer;
  final Offset? startPixel;
  final Offset? goalPixel;
  final List<PathStep> pathSteps;
  final FeedbackState? feedback;
  final MissionPhase phase;
  final bool isLoading;
  final String? errorMessage;

  final double? startWx;
  final double? startWy;
  final double? goalWx;
  final double? goalWy;
  final String? missionId;

  const MissionState({
    this.mapConfig,
    this.transformer,
    this.startPixel,
    this.goalPixel,
    this.pathSteps = const [],
    this.feedback,
    this.phase = MissionPhase.idle,
    this.isLoading = false,
    this.errorMessage,
    this.startWx,
    this.startWy,
    this.goalWx,
    this.goalWy,
    this.missionId,
  });

  // Sentinel object used to distinguish "not provided" from explicit null.
  static const _keep = Object();

  MissionState copyWith({
    MapConfig? mapConfig,
    CoordinateTransformer? transformer,
    Object? startPixel = _keep,    // Offset? — clearable
    Object? goalPixel = _keep,     // Offset? — clearable
    List<PathStep>? pathSteps,
    Object? feedback = _keep,      // FeedbackState? — clearable
    MissionPhase? phase,
    bool? isLoading,
    Object? errorMessage = _keep,  // String? — clearable
    Object? startWx = _keep,       // double? — clearable
    Object? startWy = _keep,
    Object? goalWx = _keep,
    Object? goalWy = _keep,
    String? missionId,
  }) {
    return MissionState(
      mapConfig: mapConfig ?? this.mapConfig,
      transformer: transformer ?? this.transformer,
      startPixel: identical(startPixel, _keep)
          ? this.startPixel : startPixel as Offset?,
      goalPixel: identical(goalPixel, _keep)
          ? this.goalPixel : goalPixel as Offset?,
      pathSteps: pathSteps ?? this.pathSteps,
      feedback: identical(feedback, _keep)
          ? this.feedback : feedback as FeedbackState?,
      phase: phase ?? this.phase,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: identical(errorMessage, _keep)
          ? this.errorMessage : errorMessage as String?,
      startWx: identical(startWx, _keep)
          ? this.startWx : startWx as double?,
      startWy: identical(startWy, _keep)
          ? this.startWy : startWy as double?,
      goalWx: identical(goalWx, _keep)
          ? this.goalWx : goalWx as double?,
      goalWy: identical(goalWy, _keep)
          ? this.goalWy : goalWy as double?,
      missionId: missionId ?? this.missionId,
    );
  }
}

class MissionController extends StateNotifier<MissionState> {
  final FirebaseService _firebase;
  final ApiClient _api;

  StreamSubscription<DatabaseEvent>? _pathSub;
  StreamSubscription<DatabaseEvent>? _feedbackSub;

  MissionController({
    required FirebaseService firebase,
    required ApiClient api,
  })  : _firebase = firebase,
        _api = api,
        super(const MissionState());

  /// Initialise: always create a fresh mission ID so we never pick up stale
  /// data from a previous session. Load MapConfig from the API (fast, local
  /// network) and also write it to Firebase so the simulator can read it.
  Future<void> initialize() async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      // Always generate a fresh mission ID on app start so we don't inherit
      // stale path/feedback data from a previous run.
      final missionId =
          'mission_${DateTime.now().millisecondsSinceEpoch}';
      await _firebase.setCurrentMissionId(missionId);

      // Load MapConfig from the FastAPI backend first (most reliable source).
      // Fall back to Firebase if the backend is unreachable.
      MapConfig? mapConfig;
      try {
        mapConfig = await _api.getMapConfig();
      } catch (_) {
        mapConfig = await _firebase.getMapConfig(missionId);
      }

      if (mapConfig == null) {
        throw Exception(
          'Could not load map config. Make sure the backend is running at '
          'http://localhost:8000 and Firebase has map_config data.',
        );
      }

      final transformer = CoordinateTransformer(mapConfig);

      state = state.copyWith(
        missionId: missionId,
        mapConfig: mapConfig,
        transformer: transformer,
        phase: MissionPhase.selectStart,
        isLoading: false,
        errorMessage: null,
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        phase: MissionPhase.idle,
        errorMessage: e.toString(),
      );
    }
  }

  void onMapTap(Offset pixelPos, Size imageSize) {
    final transformer = state.transformer;
    final missionId = state.missionId;
    if (transformer == null || missionId == null) return;

    final (wx, wy) = transformer.pixelToWorld(
      pixelPos.dx,
      pixelPos.dy,
      imageSize.width,
      imageSize.height,
    );

    if (state.phase == MissionPhase.selectStart) {
      _firebase.writeWaypoint(missionId, 'start', wx, wy);
      state = MissionState(
        mapConfig: state.mapConfig,
        transformer: state.transformer,
        missionId: state.missionId,
        startPixel: pixelPos,
        startWx: wx,
        startWy: wy,
        phase: MissionPhase.selectGoal,
      );
    } else if (state.phase == MissionPhase.selectGoal) {
      _firebase.writeWaypoint(missionId, 'goal', wx, wy);
      state = state.copyWith(
        goalPixel: pixelPos,
        goalWx: wx,
        goalWy: wy,
        phase: MissionPhase.planning,
      );
      submitMission();
    }
  }

  Future<void> submitMission() async {
    final missionId = state.missionId;
    if (missionId == null) return;

    state = state.copyWith(isLoading: true, errorMessage: null);

    try {
      await _firebase.setStatus(missionId, 'planning');

      await _api.planPath(
        missionId: missionId,
        startWx: state.startWx!,
        startWy: state.startWy!,
        goalWx: state.goalWx!,
        goalWy: state.goalWy!,
      );

      state = state.copyWith(
        phase: MissionPhase.executing,
        isLoading: false,
      );

      // Subscribe to path updates from Firebase
      _pathSub?.cancel();
      _pathSub = _firebase.watchPath(missionId).listen((event) {
        if (event.snapshot.exists && event.snapshot.value != null) {
          try {
            final raw =
                Map<String, dynamic>.from(event.snapshot.value as Map);
            final stepsRaw = raw['steps'];
            if (stepsRaw != null) {
              final stepsMap =
                  Map<String, dynamic>.from(stepsRaw as Map);
              final entries = stepsMap.entries.toList()
                ..sort((a, b) =>
                    int.parse(a.key).compareTo(int.parse(b.key)));
              final steps = entries
                  .map((e) => PathStep.fromJson(
                      Map<String, dynamic>.from(e.value as Map)))
                  .toList();
              state = state.copyWith(pathSteps: steps);
            }
          } catch (_) {
            // Ignore malformed path data
          }
        }
      });

      // Subscribe to feedback updates from Firebase
      _feedbackSub?.cancel();
      _feedbackSub =
          _firebase.watchFeedback(missionId).listen((event) {
        if (event.snapshot.exists && event.snapshot.value != null) {
          try {
            final data =
                Map<String, dynamic>.from(event.snapshot.value as Map);
            final feedback = FeedbackState.fromJson(data);
            onFeedbackUpdate(feedback);
          } catch (_) {
            // Ignore malformed feedback
          }
        }
      });
    } on PlanPathException catch (e) {
      state = state.copyWith(
        isLoading: false,
        phase: MissionPhase.selectStart,
        errorMessage: 'PlanPathException:${e.statusCode}:${e.detail}',
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        phase: MissionPhase.selectStart,
        errorMessage: e.toString(),
      );
    }
  }

  void onFeedbackUpdate(FeedbackState feedback) {
    MissionPhase phase = state.phase;
    if (feedback.action == RobotAction.arrived) {
      phase = MissionPhase.complete;
    }
    state = state.copyWith(feedback: feedback, phase: phase);
  }

  void resetMission() {
    _pathSub?.cancel();
    _feedbackSub?.cancel();
    final missionId =
        'mission_${DateTime.now().millisecondsSinceEpoch}';
    _firebase.setCurrentMissionId(missionId);
    state = MissionState(
      mapConfig: state.mapConfig,
      transformer: state.transformer,
      missionId: missionId,
      phase: MissionPhase.selectStart,
    );
  }

  @override
  void dispose() {
    _pathSub?.cancel();
    _feedbackSub?.cancel();
    super.dispose();
  }
}

final missionControllerProvider =
    StateNotifierProvider<MissionController, MissionState>((ref) {
  return MissionController(
    firebase: FirebaseService(),
    api: ApiClient(),
  );
});
