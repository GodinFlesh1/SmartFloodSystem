import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import '../models/station.dart';
import '../models/station_detail.dart';
import '../services/api_service.dart';
import '../utils/risk_style.dart';

class MapTab extends StatefulWidget {
  final Position? position;
  final List<Station> stations;
  final bool loading;

  const MapTab({
    super.key,
    required this.position,
    required this.stations,
    required this.loading,
  });

  @override
  State<MapTab> createState() => _MapTabState();
}

class _MapTabState extends State<MapTab> {
  final _apiService = ApiService();

  Station? _selectedStation;
  StationDetail? _detail;
  bool _loadingDetail = false;
  String? _detailError;

  Color _markerColor(String risk) => RiskStyle.of(risk).color;

  Future<void> _onStationTap(Station station) async {
    setState(() {
      _selectedStation = station;
      _detail = null;
      _detailError = null;
      _loadingDetail = true;
    });

    try {
      final detail = await _apiService.getStationDetail(station.eaStationId);
      setState(() => _detail = detail);
    } catch (e) {
      setState(() => _detailError = e.toString());
    } finally {
      setState(() => _loadingDetail = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.loading) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Loading map data…'),
          ],
        ),
      );
    }

    if (widget.position == null) {
      return const Center(child: Text('Location not available.'));
    }

    final userLatLng =
        LatLng(widget.position!.latitude, widget.position!.longitude);
    final validStations = widget.stations
        .where((s) => s.latitude != 0 && s.longitude != 0)
        .toList();

    return Column(
      children: [
        Expanded(
          child: FlutterMap(
            options: MapOptions(
              initialCenter: userLatLng,
              initialZoom: 11,
              onTap: (_, __) =>
                  setState(() => _selectedStation = null),
            ),
            children: [
              TileLayer(
                urlTemplate:
                    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.example.frontend',
              ),
              MarkerLayer(
                markers: [
                  // User location
                  Marker(
                    point: userLatLng,
                    width: 44,
                    height: 44,
                    child: Container(
                      decoration: BoxDecoration(
                        color: const Color(0xFF1565C0),
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 2.5),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(0.25),
                            blurRadius: 6,
                          ),
                        ],
                      ),
                      child: const Icon(Icons.person_pin,
                          color: Colors.white, size: 22),
                    ),
                  ),
                  // Station markers
                  ...validStations.map((s) {
                    final color = _markerColor(s.riskLevel);
                    final isSelected = _selectedStation?.eaStationId == s.eaStationId;
                    return Marker(
                      point: LatLng(s.latitude, s.longitude),
                      width: isSelected ? 48 : 36,
                      height: isSelected ? 48 : 36,
                      child: GestureDetector(
                        onTap: () => _onStationTap(s),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          decoration: BoxDecoration(
                            color: color,
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: isSelected ? Colors.white : Colors.white70,
                              width: isSelected ? 3 : 2,
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: color.withOpacity(0.5),
                                blurRadius: isSelected ? 10 : 4,
                                spreadRadius: isSelected ? 2 : 0,
                              ),
                            ],
                          ),
                          child: const Icon(Icons.water_drop,
                              color: Colors.white, size: 16),
                        ),
                      ),
                    );
                  }),
                ],
              ),
            ],
          ),
        ),
        // Bottom panel
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 200),
          child: _selectedStation != null
              ? _buildDetailPanel()
              : _buildLegend(),
        ),
      ],
    );
  }

  // ── DETAIL PANEL ──────────────────────────────────────────────────────────

  Widget _buildDetailPanel() {
    final s = _selectedStation!;
    // Use detail status if loaded, otherwise fall back to map marker status
    final statusKey = _detail?.status ?? s.riskLevel;
    final risk = RiskStyle.of(statusKey);

    return Container(
      key: ValueKey(s.eaStationId),
      width: double.infinity,
      constraints: const BoxConstraints(maxHeight: 340),
      decoration: const BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(color: Colors.black12, blurRadius: 8, offset: Offset(0, -2)),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(s.stationName,
                          style: const TextStyle(
                              fontWeight: FontWeight.bold, fontSize: 15)),
                      if (s.riverName != null)
                        Text(s.riverName!,
                            style: TextStyle(
                                color: Colors.grey.shade600, fontSize: 12)),
                      if (s.town != null)
                        Text(s.town!,
                            style: TextStyle(
                                color: Colors.grey.shade500, fontSize: 12)),
                    ],
                  ),
                ),
                // Status badge
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: risk.color.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(risk.icon, size: 13, color: risk.color),
                      const SizedBox(width: 4),
                      Text(risk.label,
                          style: TextStyle(
                              color: risk.color,
                              fontWeight: FontWeight.bold,
                              fontSize: 12)),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                GestureDetector(
                  onTap: () => setState(() => _selectedStation = null),
                  child: const Icon(Icons.close, size: 20, color: Colors.grey),
                ),
              ],
            ),
          ),
          // Plain-English status description
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Text(risk.description,
                style: TextStyle(fontSize: 12, color: Colors.grey.shade500)),
          ),
          const Divider(height: 1),
          // Readings body
          if (_loadingDetail)
            const Padding(
              padding: EdgeInsets.all(20),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(strokeWidth: 2),
                  SizedBox(width: 12),
                  Text('Fetching readings…'),
                ],
              ),
            )
          else if (_detailError != null)
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text(_detailError!,
                  style: const TextStyle(color: Colors.red)),
            )
          else if (_detail == null || _detail!.measures.isEmpty)
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text('No readings available for this station.',
                  style: TextStyle(color: Colors.grey.shade500)),
            )
          else
            Flexible(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(16, 10, 16, 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Water level gauge bar if we have level + typical range
                    if (_detail!.typicalRangeHigh != null)
                      _buildLevelBar(_detail!),
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: _detail!.measures
                          .map((m) => _measureChip(m))
                          .toList(),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  /// Visual bar showing where the current level sits vs the typical range.
  Widget _buildLevelBar(StationDetail detail) {
    final level = detail.measures
        .where((m) => m.parameter == 'level')
        .map((m) => m.value)
        .firstWhere((v) => v != null, orElse: () => null);

    if (level == null) return const SizedBox.shrink();

    final low = detail.typicalRangeLow ?? 0.0;
    final high = detail.typicalRangeHigh!;
    // Show bar from 0 up to 130% of high
    final barMax = high * 1.3;
    final fraction = (level / barMax).clamp(0.0, 1.0);
    final risk = RiskStyle.of(detail.status);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('Water Level',
                style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: Colors.grey.shade700)),
            Text('${level.toStringAsFixed(3)} m',
                style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.bold,
                    color: risk.color)),
          ],
        ),
        const SizedBox(height: 6),
        Stack(
          children: [
            // Background track
            Container(
              height: 10,
              decoration: BoxDecoration(
                color: Colors.grey.shade200,
                borderRadius: BorderRadius.circular(5),
              ),
            ),
            // Typical range highlight
            FractionallySizedBox(
              widthFactor: (high / barMax).clamp(0.0, 1.0),
              child: Container(
                height: 10,
                decoration: BoxDecoration(
                  color: Colors.green.shade100,
                  borderRadius: BorderRadius.circular(5),
                ),
              ),
            ),
            // Current level fill
            FractionallySizedBox(
              widthFactor: fraction,
              child: Container(
                height: 10,
                decoration: BoxDecoration(
                  color: risk.color,
                  borderRadius: BorderRadius.circular(5),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('Normal up to ${high.toStringAsFixed(2)} m',
                style: TextStyle(fontSize: 10, color: Colors.grey.shade500)),
            Text(risk.label,
                style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    color: risk.color)),
          ],
        ),
        const SizedBox(height: 4),
      ],
    );
  }

  Widget _measureChip(MeasureReading m) {
    final hasValue = m.value != null;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFF0F4F8),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.blueGrey.shade100),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            m.label,
            style: TextStyle(
                fontSize: 11,
                color: Colors.grey.shade600,
                fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 2),
          Text(
            hasValue
                ? '${m.value!.toStringAsFixed(3)} ${m.displayUnit}'
                : 'No reading',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.bold,
              color: hasValue
                  ? const Color(0xFF1565C0)
                  : Colors.grey.shade400,
            ),
          ),
        ],
      ),
    );
  }

  // ── LEGEND ────────────────────────────────────────────────────────────────

  Widget _buildLegend() {
    return Container(
      key: const ValueKey('legend'),
      color: Colors.white,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _legendDot(RiskStyle.of('NORMAL').color, 'Normal'),
          _legendDot(RiskStyle.of('ELEVATED').color, 'Elevated'),
          _legendDot(RiskStyle.of('HIGH').color, 'Flood Risk'),
          _legendDot(RiskStyle.of('SEVERE').color, 'Severe'),
          _legendDot(RiskStyle.of('NO_SENSOR').color, 'No Sensor'),
          _legendDot(const Color(0xFF1565C0), 'You'),
        ],
      ),
    );
  }

  Widget _legendDot(Color color, String label) {
    return Row(
      children: [
        Container(
          width: 11,
          height: 11,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 11)),
      ],
    );
  }
}
