import 'package:flutter/material.dart';

/// Centralised risk label / colour / description used across the whole app.
class RiskStyle {
  final String label;       // e.g. "Normal"
  final String description; // e.g. "Water is within the typical range"
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
          label: 'Severe Flood',
          description: 'Water is critically high — serious flood danger',
          color: Colors.red.shade700,
          icon: Icons.warning_rounded,
        );
      case 'HIGH':
        return RiskStyle._(
          label: 'Flood Risk',
          description: 'Water has exceeded the typical high level',
          color: Colors.orange.shade700,
          icon: Icons.arrow_upward_rounded,
        );
      case 'ELEVATED':
        return RiskStyle._(
          label: 'Elevated',
          description: 'Water is above normal but not yet dangerous',
          color: Colors.amber.shade700,
          icon: Icons.trending_up_rounded,
        );
      case 'NORMAL':
        return RiskStyle._(
          label: 'Normal',
          description: 'Water is within the typical range',
          color: Colors.green.shade600,
          icon: Icons.check_circle_outline_rounded,
        );
      case 'NO_SENSOR':
      default:
        return RiskStyle._(
          label: 'No Sensor',
          description: 'No recent reading from this station',
          color: Colors.grey.shade400,
          icon: Icons.sensors_off_rounded,
        );
    }
  }
}
