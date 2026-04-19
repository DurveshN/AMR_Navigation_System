import 'package:dio/dio.dart';
import '../models/map_config.dart';

/// Thrown when the backend returns HTTP 400 or 422.
class PlanPathException implements Exception {
  final int statusCode;
  final String detail;

  const PlanPathException({required this.statusCode, required this.detail});

  @override
  String toString() => 'PlanPathException($statusCode): $detail';
}

/// The FastAPI backend URL.
///
/// - Physical Android device: use your PC's LAN IP (same WiFi network).
/// - Android emulator: use 10.0.2.2 (maps to host machine).
/// - Desktop/web: use localhost.
const String kBackendBaseUrl = 'http://192.168.1.7:8000';

class ApiClient {
  final Dio _dio;

  ApiClient({String baseUrl = kBackendBaseUrl})
      : _dio = Dio(BaseOptions(
          baseUrl: baseUrl,
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 30),
        ));

  /// POSTs to `/plan-path` and returns the raw response map.
  ///
  /// Throws [PlanPathException] on HTTP 400 or 422.
  Future<Map<String, dynamic>> planPath({
    required String missionId,
    required double startWx,
    required double startWy,
    required double goalWx,
    required double goalWy,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/plan-path',
        data: {
          'mission_id': missionId,
          'start': [startWx, startWy],
          'goal': [goalWx, goalWy],
        },
      );
      return response.data ?? {};
    } on DioException catch (e) {
      final statusCode = e.response?.statusCode;
      if (statusCode == 400 || statusCode == 422) {
        final detail = _extractDetail(e.response?.data);
        throw PlanPathException(statusCode: statusCode!, detail: detail);
      }
      rethrow;
    }
  }

  /// GETs `/map-config` and returns a [MapConfig].
  Future<MapConfig> getMapConfig() async {
    final response =
        await _dio.get<Map<String, dynamic>>('/map-config');
    return MapConfig.fromJson(response.data!);
  }

  String _extractDetail(dynamic data) {
    if (data is Map && data.containsKey('detail')) {
      return data['detail'].toString();
    }
    return data?.toString() ?? 'Unknown error';
  }
}
