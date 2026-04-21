import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/utils/risk_style.dart';

void main() {
  group('RiskStyle.of', () {
    test('SEVERE returns red color and warning icon', () {
      final style = RiskStyle.of('SEVERE');
      expect(style.label, 'Severe Flood');
      expect(style.color, Colors.red.shade700);
      expect(style.icon,  Icons.warning_rounded);
    });

    test('HIGH returns orange color', () {
      final style = RiskStyle.of('HIGH');
      expect(style.label, 'Flood Risk');
      expect(style.color, Colors.orange.shade700);
    });

    test('ELEVATED returns amber color', () {
      final style = RiskStyle.of('ELEVATED');
      expect(style.label, 'Elevated');
      expect(style.color, Colors.amber.shade700);
      expect(style.icon,  Icons.trending_up_rounded);
    });

    test('NORMAL returns green color', () {
      final style = RiskStyle.of('NORMAL');
      expect(style.label, 'Normal');
      expect(style.color, Colors.green.shade600);
      expect(style.icon,  Icons.check_circle_outline_rounded);
    });

    test('NO_SENSOR returns grey color', () {
      final style = RiskStyle.of('NO_SENSOR');
      expect(style.label, 'No Sensor');
      expect(style.color, Colors.grey.shade400);
      expect(style.icon,  Icons.sensors_off_rounded);
    });

    test('unknown level falls back to NO_SENSOR style', () {
      final style = RiskStyle.of('TOTALLY_MADE_UP');
      expect(style.label, 'No Sensor');
    });

    test('is case-insensitive', () {
      expect(RiskStyle.of('severe').label, RiskStyle.of('SEVERE').label);
      expect(RiskStyle.of('high').label,   RiskStyle.of('HIGH').label);
      expect(RiskStyle.of('normal').label, RiskStyle.of('NORMAL').label);
    });

    test('description is non-empty for all known levels', () {
      for (final level in ['SEVERE', 'HIGH', 'ELEVATED', 'NORMAL', 'NO_SENSOR']) {
        expect(RiskStyle.of(level).description, isNotEmpty, reason: level);
      }
    });
  });
}
