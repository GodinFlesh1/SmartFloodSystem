import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/models/station.dart';

void main() {
  group('Station.fromJson', () {
    test('parses complete JSON correctly', () {
      final json = {
        'ea_station_id': 'ABC123',
        'station_name':  'Test Station',
        'latitude':      51.5,
        'longitude':     -0.1,
        'town':          'London',
        'river_name':    'Thames',
        'water_level':   1.2,
        'flow':          3.5,
        'rainfall':      0.0,
        'groundwater':   null,
        'tidal':         null,
        'risk_level':    'ELEVATED',
        'distance_km':   2.3,
      };
      final station = Station.fromJson(json);

      expect(station.eaStationId, 'ABC123');
      expect(station.stationName, 'Test Station');
      expect(station.latitude,    51.5);
      expect(station.longitude,   -0.1);
      expect(station.town,        'London');
      expect(station.riverName,   'Thames');
      expect(station.waterLevel,  1.2);
      expect(station.flow,        3.5);
      expect(station.rainfall,    0.0);
      expect(station.groundwater, isNull);
      expect(station.tidal,       isNull);
      expect(station.riskLevel,   'ELEVATED');
      expect(station.distanceKm,  2.3);
    });

    test('uses defaults when fields are missing', () {
      final station = Station.fromJson({
        'latitude':  51.5,
        'longitude': -0.1,
      });
      expect(station.eaStationId,  '');
      expect(station.stationName,  'Unknown Station');
      expect(station.riskLevel,    'UNKNOWN');
      expect(station.waterLevel,   isNull);
    });

    test('handles integer lat/lon (num cast)', () {
      final station = Station.fromJson({
        'ea_station_id': 'X',
        'station_name':  'X',
        'latitude':  51,
        'longitude': 0,
        'risk_level': 'NORMAL',
      });
      expect(station.latitude, 51.0);
      expect(station.longitude, 0.0);
    });
  });

  group('Station.hasAnyReading', () {
    test('returns true when waterLevel is set', () {
      final s = Station.fromJson({
        'ea_station_id': 'X', 'station_name': 'X',
        'latitude': 0, 'longitude': 0, 'risk_level': 'NORMAL',
        'water_level': 1.2,
      });
      expect(s.hasAnyReading, isTrue);
    });

    test('returns true when only flow is set', () {
      final s = Station.fromJson({
        'ea_station_id': 'X', 'station_name': 'X',
        'latitude': 0, 'longitude': 0, 'risk_level': 'NORMAL',
        'flow': 5.0,
      });
      expect(s.hasAnyReading, isTrue);
    });

    test('returns false when all readings are null', () {
      final s = Station.fromJson({
        'ea_station_id': 'X', 'station_name': 'X',
        'latitude': 0, 'longitude': 0, 'risk_level': 'NO_SENSOR',
      });
      expect(s.hasAnyReading, isFalse);
    });
  });
}
