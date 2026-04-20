import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../models/mission.dart';
import 'map_painter.dart';
import 'mission_controller.dart';
import 'robot_animator.dart';

class MapScreen extends ConsumerStatefulWidget {
  const MapScreen({super.key});

  @override
  ConsumerState<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends ConsumerState<MapScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(missionControllerProvider.notifier).initialize();
    });
  }

  void _handleTap(TapDownDetails details, Size imageSize) {
    debugPrint('[MapScreen] _handleTap at ${details.localPosition}, '
        'imageSize=$imageSize');
    ref
        .read(missionControllerProvider.notifier)
        .onMapTap(details.localPosition, imageSize);
  }

  String _phaseLabel(MissionPhase phase) {
    switch (phase) {
      case MissionPhase.selectStart:
        return 'TAP TO SET START';
      case MissionPhase.selectGoal:
        return 'TAP TO SET GOAL';
      case MissionPhase.planning:
        return 'PLANNING PATH…';
      case MissionPhase.executing:
        return 'ROBOT MOVING';
      case MissionPhase.complete:
        return 'MISSION COMPLETE';
      default:
        return 'INITIALISING…';
    }
  }

  Color _phaseColor(MissionPhase phase) {
    switch (phase) {
      case MissionPhase.selectStart:
        return Colors.blue.shade100;
      case MissionPhase.selectGoal:
        return Colors.orange.shade100;
      case MissionPhase.planning:
        return Colors.purple.shade100;
      case MissionPhase.executing:
        return Colors.green.shade100;
      case MissionPhase.complete:
        return Colors.teal.shade100;
      default:
        return Colors.grey.shade200;
    }
  }

  @override
  Widget build(BuildContext context) {
    final missionState = ref.watch(missionControllerProvider);
    debugPrint('[MapScreen] build: phase=${missionState.phase}, '
        'isLoading=${missionState.isLoading}, '
        'transformer=${missionState.transformer != null}, '
        'error=${missionState.errorMessage}');

    ref.listen<MissionState>(missionControllerProvider, (prev, next) {
      if (next.errorMessage != null &&
          next.errorMessage != prev?.errorMessage) {
        final msg = next.errorMessage!;
        String snackText;
        if (msg.contains('PlanPathException:400')) {
          snackText =
              'Selected position is inside an obstacle. Please tap a clear area.';
        } else if (msg.contains('PlanPathException:422')) {
          snackText = 'No path found between selected points.';
        } else {
          snackText = 'Error: $msg';
        }
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(snackText),
            duration: const Duration(seconds: 5),
            action: SnackBarAction(
              label: 'DISMISS',
              onPressed: () =>
                  ScaffoldMessenger.of(context).hideCurrentSnackBar(),
            ),
          ),
        );
      }
    });

    final currentStep = missionState.feedback?.currentStep ?? 0;
    final bool isTappable = missionState.phase == MissionPhase.selectStart ||
        missionState.phase == MissionPhase.selectGoal;

    return Scaffold(
      appBar: AppBar(
        title: const Text('AMR Navigation'),
        actions: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 8.0),
            child: Chip(
              label: Text(
                _phaseLabel(missionState.phase),
                style: const TextStyle(fontSize: 12),
              ),
              backgroundColor: _phaseColor(missionState.phase),
            ),
          ),
          if (missionState.phase == MissionPhase.complete ||
              (missionState.errorMessage != null &&
                  missionState.phase == MissionPhase.idle))
            IconButton(
              icon: const Icon(Icons.refresh),
              tooltip: 'New Mission',
              onPressed: () =>
                  ref.read(missionControllerProvider.notifier).resetMission(),
            ),
        ],
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          debugPrint('[MapScreen] constraints: '
              '${constraints.maxWidth}x${constraints.maxHeight}');
          final imageSize = Size(constraints.maxWidth, constraints.maxHeight);

          return GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTapDown: (details) {
              debugPrint(
                  '[MapScreen] TAP DETECTED at ${details.localPosition}');
              _handleTap(details, imageSize);
            },
            child: Container(
              color: Colors.lightGreen,
              child: Stack(
                children: [
                  // ── Layer 1: Map image ─────────────────────────────
                  Positioned.fill(
                    child: Image.asset(
                      'assets/map_fallback.png',
                      fit: BoxFit.contain,
                    ),
                  ),

                  // ── Layer 2: Path + markers ────────────────────────
                  // (temporarily disabled to isolate rendering issue)

                  // ── Layer 3: Robot icon ────────────────────────────
                  // (temporarily disabled to isolate rendering issue)

                  // ── Layer 4: Tap hint ──────────────────────────────
                  if (isTappable)
                    Positioned(
                      bottom: 16,
                      left: 0,
                      right: 0,
                      child: Center(
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 16, vertical: 8),
                          decoration: BoxDecoration(
                            color: Colors.black54,
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            missionState.phase == MissionPhase.selectStart
                                ? 'Tap the map to set the START position'
                                : 'Tap the map to set the GOAL position',
                            style: const TextStyle(
                                color: Colors.white, fontSize: 13),
                          ),
                        ),
                      ),
                    ),

                  // ── Layer 5: Loading overlay ───────────────────────
                  if (missionState.isLoading)
                    const Positioned.fill(
                      child: ColoredBox(
                        color: Color(0x55000000),
                        child: Center(
                          child: CircularProgressIndicator(
                              color: Colors.white),
                        ),
                      ),
                    ),

                  // ── Error banner ───────────────────────────────────
                  if (missionState.errorMessage != null &&
                      missionState.phase == MissionPhase.idle)
                    Positioned(
                      top: 0,
                      left: 0,
                      right: 0,
                      child: MaterialBanner(
                        content: Text(
                          'Init failed: ${missionState.errorMessage}',
                          style: const TextStyle(fontSize: 13),
                        ),
                        backgroundColor: Colors.red.shade100,
                        actions: [
                          TextButton(
                            onPressed: () => ref
                                .read(missionControllerProvider.notifier)
                                .initialize(),
                            child: const Text('RETRY'),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
