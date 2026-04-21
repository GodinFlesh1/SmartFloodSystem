import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/models/flood_prediction.dart';

void main() {
  group('FloodPrediction.fromJson', () {
    test('parses complete JSON', () {
      final prediction = FloodPrediction.fromJson({
        'risk_level':  'HIGH',
        'probability': 0.72,
        'confidence':  'high',
        'reason':      'Heavy rain near Station X.',
        'top_station': 'Station X',
      });

      expect(prediction.riskLevel,   'HIGH');
      expect(prediction.probability, 0.72);
      expect(prediction.confidence,  'high');
      expect(prediction.reason,      'Heavy rain near Station X.');
      expect(prediction.topStation,  'Station X');
    });

    test('uses defaults for missing fields', () {
      final prediction = FloodPrediction.fromJson({});

      expect(prediction.riskLevel,   'UNKNOWN');
      expect(prediction.probability, 0.0);
      expect(prediction.confidence,  'low');
      expect(prediction.reason,      '');
      expect(prediction.topStation,  '');
    });

    test('handles integer probability (num cast)', () {
      final prediction = FloodPrediction.fromJson({
        'risk_level': 'NORMAL',
        'probability': 0,
        'confidence': 'high',
        'reason': '',
        'top_station': '',
      });
      expect(prediction.probability, 0.0);
    });
  });
}
