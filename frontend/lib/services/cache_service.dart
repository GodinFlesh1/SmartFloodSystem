import 'dart:convert';
import 'dart:math' as math;
import 'package:shared_preferences/shared_preferences.dart';

/// Thin wrapper around SharedPreferences for caching API responses with TTL.
class CacheService {
  static const _kPrediction   = 'cache_prediction';
  static const _kPredictionTs = 'cache_prediction_ts';
  static const _kStations     = 'cache_stations';
  static const _kStationsTs   = 'cache_stations_ts';
  static const _kStationsLat  = 'cache_stations_lat';
  static const _kStationsLon  = 'cache_stations_lon';

  static const _predictionTtl = Duration(minutes: 30);
  static const _stationsTtl   = Duration(minutes: 30);

  // ── Prediction ─────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>?> loadPrediction() async {
    final prefs = await SharedPreferences.getInstance();
    final tsRaw = prefs.getString(_kPredictionTs);
    if (tsRaw == null) return null;
    if (DateTime.now().difference(DateTime.parse(tsRaw)) > _predictionTtl) {
      return null;
    }
    final raw = prefs.getString(_kPrediction);
    if (raw == null) return null;
    return jsonDecode(raw) as Map<String, dynamic>;
  }

  Future<void> savePrediction(Map<String, dynamic> data) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kPrediction, jsonEncode(data));
    await prefs.setString(_kPredictionTs, DateTime.now().toIso8601String());
  }

  // ── Stations ───────────────────────────────────────────────────────────────

  /// Returns cached stations if fresh AND within [thresholdM] metres of current position.
  Future<List<Map<String, dynamic>>?> loadStations({
    required double lat,
    required double lon,
    double thresholdM = 500,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final tsRaw = prefs.getString(_kStationsTs);
    if (tsRaw == null) return null;
    if (DateTime.now().difference(DateTime.parse(tsRaw)) > _stationsTtl) {
      return null;
    }
    final cachedLat = prefs.getDouble(_kStationsLat);
    final cachedLon = prefs.getDouble(_kStationsLon);
    if (cachedLat == null || cachedLon == null) return null;
    if (_distanceM(lat, lon, cachedLat, cachedLon) > thresholdM) return null;

    final raw = prefs.getString(_kStations);
    if (raw == null) return null;
    return (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
  }

  Future<void> saveStations(
    List<Map<String, dynamic>> stations,
    double lat,
    double lon,
  ) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kStations, jsonEncode(stations));
    await prefs.setString(_kStationsTs, DateTime.now().toIso8601String());
    await prefs.setDouble(_kStationsLat, lat);
    await prefs.setDouble(_kStationsLon, lon);
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  double _distanceM(double lat1, double lon1, double lat2, double lon2) {
    const r = 6371000.0;
    final dLat = _rad(lat2 - lat1);
    final dLon = _rad(lon2 - lon1);
    final a = math.pow(math.sin(dLat / 2), 2) +
        math.pow(math.sin(dLon / 2), 2) *
            math.cos(_rad(lat1)) *
            math.cos(_rad(lat2));
    return 2 * r * math.asin(math.sqrt(a));
  }

  double _rad(double deg) => deg * math.pi / 180;
}
