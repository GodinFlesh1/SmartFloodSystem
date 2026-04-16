import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/app_config.dart';
import '../models/station.dart';
import '../models/station_detail.dart';
import '../models/flood_prediction.dart';
import '../models/safe_route.dart';

class ApiService {
  static const String _baseUrl = AppConfig.apiBaseUrl;
  Future<List<Station>> getNearbyStations({
    required double lat,
    required double lon,
    double radiusKm = 5,
  }) async {
    final uri = Uri.parse(
      '$_baseUrl/api/live/stations/nearby?lat=$lat&lon=$lon&radius_km=$radiusKm',
    );

    final response = await http.get(uri).timeout(const Duration(seconds: 15));

    if (response.statusCode != 200) {
      throw Exception('API error ${response.statusCode}: ${response.body}');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;

    if (data['success'] != true) {
      throw Exception(data['error'] ?? 'Unknown API error');
    }

    final stationsJson = data['stations'] as List<dynamic>? ?? [];
    return stationsJson
        .map((s) => Station.fromJson(s as Map<String, dynamic>))
        .toList();
  }

  Future<StationDetail> getStationDetail(String stationId) async {
    final uri = Uri.parse('$_baseUrl/api/ea/stations/$stationId/latest');
    final response = await http.get(uri).timeout(const Duration(seconds: 15));

    if (response.statusCode != 200) {
      throw Exception('API error ${response.statusCode}');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;

    if (data['success'] != true) {
      throw Exception(data['error'] ?? 'Unknown error');
    }

    return StationDetail.fromJson(data);
  }

  Future<FloodPrediction> getAiPrediction({
    required double lat,
    required double lon,
  }) async {
    final uri = Uri.parse(
      '$_baseUrl/api/predict/flood-risk?lat=$lat&lon=$lon',
    );
    final response = await http.get(uri).timeout(const Duration(seconds: 20));

    if (response.statusCode != 200) {
      throw Exception('Prediction API error ${response.statusCode}');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    if (data['success'] != true) {
      throw Exception(data['error'] ?? 'Prediction failed');
    }
    return FloodPrediction.fromJson(data);
  }

  Future<SafeRoute> getSafeRoute({
    required double lat,
    required double lon,
    int radiusM = 5000,
    String profile = 'driving-car',
  }) async {
    final uri = Uri.parse(
      '$_baseUrl/api/safe-route?lat=$lat&lon=$lon&radius_m=$radiusM&profile=$profile',
    );
    final response = await http.get(uri).timeout(const Duration(seconds: 30));

    if (response.statusCode != 200) {
      throw Exception('Safe route API error ${response.statusCode}');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    if (data['success'] != true) {
      throw Exception(data['error'] ?? 'Could not find safe route');
    }
    return SafeRoute.fromJson(data);
  }
}
