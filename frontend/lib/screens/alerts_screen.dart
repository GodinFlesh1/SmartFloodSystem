import 'package:flutter/material.dart';
import '../models/station.dart';
import '../widgets/station_card.dart';

class AlertsTab extends StatelessWidget {
  final List<Station> stations;
  final bool loading;

  const AlertsTab({
    super.key,
    required this.stations,
    required this.loading,
  });

  static const _alertLevels = {'SEVERE', 'HIGH', 'ELEVATED'};

  List<Station> get _alertStations =>
      stations.where((s) => _alertLevels.contains(s.riskLevel.toUpperCase())).toList();

  int get _severeCount =>
      stations.where((s) => s.riskLevel.toUpperCase() == 'SEVERE').length;

  int get _highCount =>
      stations.where((s) => s.riskLevel.toUpperCase() == 'HIGH').length;

  int get _elevatedCount =>
      stations.where((s) => s.riskLevel.toUpperCase() == 'ELEVATED').length;

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Checking for alerts…'),
          ],
        ),
      );
    }

    final alerts = _alertStations;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSummaryRow(),
          const SizedBox(height: 20),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Active Alerts',
                style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: Colors.black54),
              ),
              if (alerts.isNotEmpty)
                Text('${alerts.length} station(s)',
                    style: const TextStyle(
                        fontSize: 13, color: Colors.blueGrey)),
            ],
          ),
          const SizedBox(height: 8),
          if (alerts.isEmpty)
            _buildNoAlertsCard()
          else
            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: alerts.length,
              itemBuilder: (_, i) => StationCard(station: alerts[i]),
            ),
        ],
      ),
    );
  }

  Widget _buildSummaryRow() {
    return Row(
      children: [
        _summaryTile('Severe Flood', _severeCount, Colors.red.shade700,
            Icons.warning_rounded),
        const SizedBox(width: 10),
        _summaryTile('Flood Risk', _highCount, Colors.orange.shade700,
            Icons.arrow_upward_rounded),
        const SizedBox(width: 10),
        _summaryTile('Elevated', _elevatedCount, Colors.amber.shade700,
            Icons.trending_up_rounded),
      ],
    );
  }

  Widget _summaryTile(
      String label, int count, Color color, IconData icon) {
    return Expanded(
      child: Container(
        padding:
            const EdgeInsets.symmetric(vertical: 14, horizontal: 10),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.2)),
          boxShadow: [
            BoxShadow(
                color: Colors.black.withOpacity(0.04),
                blurRadius: 6,
                offset: const Offset(0, 2)),
          ],
        ),
        child: Column(
          children: [
            Icon(icon, color: color, size: 22),
            const SizedBox(height: 4),
            Text('$count',
                style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: color)),
            Text(label,
                style: TextStyle(
                    fontSize: 11, color: Colors.grey.shade500)),
          ],
        ),
      ),
    );
  }

  Widget _buildNoAlertsCard() {
    return Card(
      shape:
          RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          children: [
            Icon(Icons.check_circle_outline_rounded,
                size: 52, color: Colors.green.shade400),
            const SizedBox(height: 14),
            const Text(
              'No Active Alerts',
              style: TextStyle(
                  fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 8),
            Text(
              'All nearby stations are within normal water levels.',
              textAlign: TextAlign.center,
              style: TextStyle(
                  color: Colors.grey.shade500,
                  fontSize: 13,
                  height: 1.5),
            ),
          ],
        ),
      ),
    );
  }
}
