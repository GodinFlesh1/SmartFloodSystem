import 'package:flutter/material.dart';
import '../models/station.dart';
import '../utils/risk_style.dart';

class StationCard extends StatelessWidget {
  final Station station;

  const StationCard({super.key, required this.station});

  @override
  Widget build(BuildContext context) {
    final risk = RiskStyle.of(station.riskLevel);

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: risk.color.withOpacity(0.3), width: 1.2),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(station.stationName,
                          style: const TextStyle(
                              fontWeight: FontWeight.bold, fontSize: 14)),
                      if (station.riverName != null)
                        Text(station.riverName!,
                            style: TextStyle(
                                color: Colors.grey.shade600, fontSize: 13)),
                      if (station.town != null)
                        Text(station.town!,
                            style: TextStyle(
                                color: Colors.grey.shade500, fontSize: 12)),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    // Status badge
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: risk.color.withOpacity(0.12),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(risk.icon, size: 12, color: risk.color),
                          const SizedBox(width: 4),
                          Text(risk.label,
                              style: TextStyle(
                                  color: risk.color,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 12)),
                        ],
                      ),
                    ),
                    if (station.distanceKm != null) ...[
                      const SizedBox(height: 4),
                      Text('${station.distanceKm!.toStringAsFixed(1)} km',
                          style: TextStyle(
                              fontSize: 11, color: Colors.grey.shade500)),
                    ],
                  ],
                ),
              ],
            ),
            // Plain-English description
            const SizedBox(height: 6),
            Text(risk.description,
                style:
                    TextStyle(fontSize: 12, color: Colors.grey.shade500)),
            // Readings
            if (station.hasAnyReading) ...[
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  if (station.waterLevel != null)
                    _chip(Icons.water, 'Water Level',
                        '${station.waterLevel!.toStringAsFixed(2)} m',
                        Colors.blue.shade700),
                  if (station.flow != null)
                    _chip(Icons.waves, 'Flow Rate',
                        '${station.flow!.toStringAsFixed(2)} m³/s',
                        Colors.cyan.shade700),
                  if (station.rainfall != null)
                    _chip(Icons.grain, 'Rainfall',
                        '${station.rainfall!.toStringAsFixed(1)} mm',
                        Colors.indigo.shade400),
                  if (station.groundwater != null)
                    _chip(Icons.landslide_outlined, 'Groundwater',
                        '${station.groundwater!.toStringAsFixed(2)} m',
                        Colors.brown.shade400),
                  if (station.tidal != null)
                    _chip(Icons.tsunami, 'Tidal Level',
                        '${station.tidal!.toStringAsFixed(2)} m',
                        Colors.teal.shade600),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _chip(IconData icon, String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: color),
          const SizedBox(width: 4),
          Text(label,
              style: TextStyle(
                  fontSize: 10,
                  color: color,
                  fontWeight: FontWeight.w500)),
          const SizedBox(width: 4),
          Text(value,
              style: TextStyle(
                  fontSize: 11,
                  color: color,
                  fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }
}
