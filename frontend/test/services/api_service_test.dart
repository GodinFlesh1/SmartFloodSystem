import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_service.dart';

// ── Helpers ───────────────────────────────────────────────────────────────────

ApiService _serviceWith(MockClient client) => ApiService(client: client);

MockClient _mockJson(int status, Map<String, dynamic> body) =>
    MockClient((_) async => http.Response(jsonEncode(body), status));

final _stationJson = {
  'ea_station_id': 'ABC123',
  'station_name':  'Test Station',
  'latitude':      51.5,
  'longitude':     -0.1,
  'risk_level':    'NORMAL',
};

// ── getNearbyStations ─────────────────────────────────────────────────────────

void main() {
  group('ApiService.getNearbyStations', () {
    test('returns list of stations on success', () async {
      final client = _mockJson(200, {
        'success':  true,
        'stations': [_stationJson],
      });
      final api      = _serviceWith(client);
      final stations = await api.getNearbyStations(lat: 51.5, lon: -0.1);

      expect(stations, hasLength(1));
      expect(stations[0].eaStationId,  'ABC123');
      expect(stations[0].stationName,  'Test Station');
    });

    test('returns empty list when stations array is empty', () async {
      final client   = _mockJson(200, {'success': true, 'stations': []});
      final stations = await _serviceWith(client).getNearbyStations(lat: 51.5, lon: -0.1);
      expect(stations, isEmpty);
    });

    test('throws on non-200 status', () async {
      final client = _mockJson(503, {});
      expect(
        () => _serviceWith(client).getNearbyStations(lat: 51.5, lon: -0.1),
        throwsException,
      );
    });

    test('throws when success is false', () async {
      final client = _mockJson(200, {'success': false, 'error': 'API down'});
      expect(
        () => _serviceWith(client).getNearbyStations(lat: 51.5, lon: -0.1),
        throwsException,
      );
    });
  });

  // ── getStationDetail ────────────────────────────────────────────────────────

  group('ApiService.getStationDetail', () {
    test('returns StationDetail on success', () async {
      final client = _mockJson(200, {
        'success':      true,
        'station_id':   'ABC123',
        'station_name': 'Test',
        'status':       'NORMAL',
        'measures':     [],
      });
      final detail = await _serviceWith(client).getStationDetail('ABC123');
      expect(detail.stationId,   'ABC123');
      expect(detail.stationName, 'Test');
    });

    test('throws on API error status', () async {
      final client = _mockJson(404, {});
      expect(
        () => _serviceWith(client).getStationDetail('UNKNOWN'),
        throwsException,
      );
    });

    test('throws when success is false', () async {
      final client = _mockJson(200, {'success': false, 'error': 'not found'});
      expect(
        () => _serviceWith(client).getStationDetail('X'),
        throwsException,
      );
    });
  });

  // ── getAiPrediction ─────────────────────────────────────────────────────────

  group('ApiService.getAiPrediction', () {
    test('returns FloodPrediction on success', () async {
      final client = _mockJson(200, {
        'success':     true,
        'risk_level':  'MODERATE',
        'probability': 0.45,
        'confidence':  'medium',
        'reason':      'Rain expected.',
        'top_station': 'Station A',
      });
      final pred = await _serviceWith(client).getAiPrediction(lat: 51.5, lon: -0.1);
      expect(pred.riskLevel,   'MODERATE');
      expect(pred.probability, 0.45);
    });

    test('throws on non-200 status', () async {
      final client = _mockJson(500, {});
      expect(
        () => _serviceWith(client).getAiPrediction(lat: 51.5, lon: -0.1),
        throwsException,
      );
    });
  });

  // ── getSafeRoute ────────────────────────────────────────────────────────────

  group('ApiService.getSafeRoute', () {
    test('returns SafeRoute on success', () async {
      final client = _mockJson(200, {
        'success': true,
        'shelter': {
          'name': 'Hall', 'type': 'community_centre',
          'latitude': 51.51, 'longitude': -0.09,
          'distance_m': 800, 'distance_km': 0.8, 'address': '',
        },
        'all_shelters': [],
        'route': {
          'success': true,
          'distance_m': 800, 'distance_km': 0.8,
          'duration_s': 120, 'duration_min': 2,
          'coordinates': [[51.5, -0.1], [51.51, -0.09]],
          'steps': [], 'profile': 'driving-car',
        },
      });
      final route = await _serviceWith(client).getSafeRoute(lat: 51.5, lon: -0.1);
      expect(route.shelter.name, 'Hall');
      expect(route.distanceM,    800);
    });

    test('throws when success is false', () async {
      final client = _mockJson(200, {
        'success': false,
        'error':   'No shelters found',
      });
      expect(
        () => _serviceWith(client).getSafeRoute(lat: 51.5, lon: -0.1),
        throwsException,
      );
    });
  });
}
