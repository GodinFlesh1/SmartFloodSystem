import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/models/station_detail.dart';

Map<String, dynamic> _measureJson({
  String parameter = 'level',
  String qualifier = 'Stage',
  String unit      = 'mAODN',
  double? value    = 1.2,
  String? dateTime = '2024-06-01T12:00:00Z',
}) =>
    {
      'parameter': parameter,
      'qualifier': qualifier,
      'unit':      unit,
      'value':     value,
      'date_time': dateTime,
    };

void main() {
  group('MeasureReading.fromJson', () {
    test('parses all fields', () {
      final m = MeasureReading.fromJson(_measureJson());
      expect(m.parameter, 'level');
      expect(m.qualifier, 'Stage');
      expect(m.unit,      'mAODN');
      expect(m.value,     1.2);
      expect(m.dateTime,  '2024-06-01T12:00:00Z');
    });

    test('value is null when JSON value is null', () {
      final m = MeasureReading.fromJson(_measureJson(value: null));
      expect(m.value, isNull);
    });

    test('uses empty string defaults for missing fields', () {
      final m = MeasureReading.fromJson({});
      expect(m.parameter, '');
      expect(m.qualifier, '');
      expect(m.unit,      '');
    });
  });

  group('MeasureReading.label', () {
    test('includes qualifier when present', () {
      final m = MeasureReading.fromJson(_measureJson(parameter: 'level', qualifier: 'Stage'));
      expect(m.label, 'Water Level (Stage)');
    });

    test('omits qualifier when empty', () {
      final m = MeasureReading.fromJson(_measureJson(parameter: 'flow', qualifier: ''));
      expect(m.label, 'Flow Rate');
    });

    test('maps all known parameters', () {
      final cases = {
        'level':       'Water Level',
        'flow':        'Flow Rate',
        'groundwater': 'Groundwater',
        'rainfall':    'Rainfall',
        'tidal':       'Tidal Level',
        'wind':        'Wind Speed',
        'temperature': 'Temperature',
        'ph':          'pH',
      };
      cases.forEach((param, expected) {
        final m = MeasureReading.fromJson(_measureJson(parameter: param, qualifier: ''));
        expect(m.label, expected, reason: 'param: $param');
      });
    });

    test('capitalizes unknown parameter', () {
      final m = MeasureReading.fromJson(_measureJson(parameter: 'salinity', qualifier: ''));
      expect(m.label, 'Salinity');
    });
  });

  group('MeasureReading.displayUnit', () {
    test('maps known units', () {
      expect(MeasureReading.fromJson(_measureJson(unit: 'mAODN')).displayUnit,  'm');
      expect(MeasureReading.fromJson(_measureJson(unit: 'mASD')).displayUnit,   'm');
      expect(MeasureReading.fromJson(_measureJson(unit: 'm')).displayUnit,      'm');
      expect(MeasureReading.fromJson(_measureJson(unit: 'm3_s')).displayUnit,   'm³/s');
      expect(MeasureReading.fromJson(_measureJson(unit: 'mm')).displayUnit,     'mm');
      expect(MeasureReading.fromJson(_measureJson(unit: 'deg_C')).displayUnit,  '°C');
      expect(MeasureReading.fromJson(_measureJson(unit: 'knots')).displayUnit,  'knots');
    });

    test('returns raw unit for unknown', () {
      expect(MeasureReading.fromJson(_measureJson(unit: 'ppm')).displayUnit, 'ppm');
    });
  });

  group('StationDetail.fromJson', () {
    test('parses full response', () {
      final json = {
        'station_id':          'ABC123',
        'station_name':        'Thames at London',
        'river_name':          'Thames',
        'town':                'London',
        'typical_range_low':   0.5,
        'typical_range_high':  2.0,
        'status':              'NORMAL',
        'measures': [_measureJson(), _measureJson(parameter: 'flow')],
      };
      final detail = StationDetail.fromJson(json);

      expect(detail.stationId,       'ABC123');
      expect(detail.stationName,     'Thames at London');
      expect(detail.riverName,       'Thames');
      expect(detail.town,            'London');
      expect(detail.typicalRangeLow, 0.5);
      expect(detail.typicalRangeHigh,2.0);
      expect(detail.status,          'NORMAL');
      expect(detail.measures,        hasLength(2));
    });

    test('uses defaults for missing fields', () {
      final detail = StationDetail.fromJson({});
      expect(detail.stationId,   '');
      expect(detail.status,      'NO_SENSOR');
      expect(detail.measures,    isEmpty);
      expect(detail.riverName,   isNull);
    });
  });
}
