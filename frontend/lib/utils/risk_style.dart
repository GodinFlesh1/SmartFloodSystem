import 'package:flutter/material.dart';

/// Centralised risk label / colour / description used across the whole app.
class RiskStyle {
  final String label;       // e.g. "Minimal Risk"
  final String description; // e.g. "Water levels are within the normal range"
  final Color color;
  final IconData icon;

  const RiskStyle._({
    required this.label,
    required this.description,
    required this.color,
    required this.icon,
  });

  static RiskStyle of(String riskLevel) {
    switch (riskLevel.toUpperCase()) {
      case 'SEVERE':
        return RiskStyle._(
          label: 'Severe Flood Risk',
          description: 'Critical water levels — immediate flood danger',
          color: Colors.red.shade700,
          icon: Icons.warning_rounded,
        );
      case 'HIGH':
        return RiskStyle._(
          label: 'High Flood Risk',
          description: 'Water has exceeded typical levels — flooding likely',
          color: Colors.orange.shade700,
          icon: Icons.arrow_upward_rounded,
        );
      case 'ELEVATED':
      case 'MODERATE':
        return RiskStyle._(
          label: 'Moderate Risk',
          description: 'Water levels are rising — monitor conditions closely',
          color: Colors.amber.shade700,
          icon: Icons.trending_up_rounded,
        );
      case 'NORMAL':
      case 'MINIMAL':
        return RiskStyle._(
          label: 'Minimal Risk',
          description: 'Water levels are within the normal range',
          color: Colors.green.shade600,
          icon: Icons.check_circle_outline_rounded,
        );
      case 'NO_SENSOR':
      default:
        return RiskStyle._(
          label: 'Minimal Risk',
          description: 'No active reading — conditions appear calm',
          color: Colors.green.shade500,
          icon: Icons.water_outlined,
        );
    }
  }
}
