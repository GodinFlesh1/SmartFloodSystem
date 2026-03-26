import 'dart:convert';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;
import '../models/station.dart';
import '../models/station_detail.dart';

class ApiService {
  // On web: backend runs on localhost.
  // On Android emulator: 10.0.2.2 is the alias for the host machine's localhost.
  static String get _baseUrl =>
      kIsWeb ? 'http://localhost:8000' : 'http://10.0.2.2:8000';

  Future<List<Station>> getNearbyStations({
    required double lat,
    required double lon,
    double radiusKm = 10,
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
}
