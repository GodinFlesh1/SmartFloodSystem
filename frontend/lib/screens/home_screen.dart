import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import '../models/station.dart';
import '../models/flood_prediction.dart';
import '../services/geocoding_service.dart';
import '../utils/risk_style.dart';
import '../widgets/station_card.dart';
import '../widgets/ai_prediction_card.dart';

class DashboardTab extends StatelessWidget {
  final Position? position;
  final CountryResult? country;
  final List<Station> stations;
  final bool loadingLocation;
  final bool loadingCountry;
  final bool loadingStations;
  final String? locationError;
  final String? stationsError;
  final FloodPrediction? prediction;
  final bool loadingPrediction;
  final String? predictionError;

  const DashboardTab({
    super.key,
    required this.position,
    required this.country,
    required this.stations,
    required this.loadingLocation,
    required this.loadingCountry,
    required this.loadingStations,
    required this.locationError,
    required this.stationsError,
    this.prediction,
    this.loadingPrediction = false,
    this.predictionError,
  });

  // Overall area risk = worst level among all stations
  String get _areaRisk {
    if (stations.isEmpty) return 'MINIMAL';
    const order = ['SEVERE', 'HIGH', 'ELEVATED', 'MODERATE', 'NORMAL', 'MINIMAL', 'NO_SENSOR'];
    for (final level in order) {
      if (stations.any((s) => s.riskLevel.toUpperCase() == level)) return level;
    }
    return 'MINIMAL';
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildLocationCard(),
          const SizedBox(height: 12),
          AiPredictionCard(
            prediction: prediction,
            loading: loadingPrediction,
            error: predictionError,
          ),
          const SizedBox(height: 12),
          _buildAreaRiskCard(),
          const SizedBox(height: 20),
          _buildStationsSection(),
        ],
      ),
    );
  }

  // ── LOCATION CARD ─────────────────────────────────────────────────────────

  Widget _buildLocationCard() {
    if (loadingLocation) {
      return _infoCard(
        child: const Row(children: [
          CircularProgressIndicator(strokeWidth: 2),
          SizedBox(width: 16),
          Text('Detecting your location…'),
        ]),
      );
    }
    if (locationError != null) {
      return _infoCard(
        child: Row(children: [
          const Icon(Icons.error_outline, color: Colors.red),
          const SizedBox(width: 12),
          Expanded(
              child: Text(locationError!,
                  style: const TextStyle(color: Colors.red))),
        ]),
      );
    }
    if (position == null) return const SizedBox.shrink();

    return _infoCard(
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: const Color(0xFF1565C0).withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.my_location,
                color: Color(0xFF1565C0), size: 22),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  const Text('Your Location',
                      style: TextStyle(
                          fontWeight: FontWeight.bold, fontSize: 14)),
                  const Spacer(),
                  if (loadingCountry)
                    const SizedBox(
                      width: 12,
                      height: 12,
                      child:
                          CircularProgressIndicator(strokeWidth: 1.5),
                    )
                  else if (country != null)
                    _pill(country!.countryName,
                        country!.isUK ? Colors.green : Colors.orange),
                ]),
                const SizedBox(height: 4),
                Text(
                  '${position!.latitude.toStringAsFixed(5)}, '
                  '${position!.longitude.toStringAsFixed(5)}',
                  style: TextStyle(
                      fontSize: 12, color: Colors.grey.shade600),
                ),
                Text(
                  'Accuracy ±${position!.accuracy.toStringAsFixed(0)} m',
                  style: TextStyle(
                      fontSize: 11, color: Colors.grey.shade400),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── AREA RISK CARD ────────────────────────────────────────────────────────

  Widget _buildAreaRiskCard() {
    if (loadingStations) {
      return _infoCard(
        child: const Row(children: [
          CircularProgressIndicator(strokeWidth: 2),
          SizedBox(width: 16),
          Text('Checking flood risk in your area…'),
        ]),
      );
    }

    if (country != null && !country!.isUK) {
      return _buildNotInUKCard();
    }

    if (stationsError != null) {
      return _infoCard(
        color: Colors.red.shade50,
        child: Row(children: [
          const Icon(Icons.error_outline, color: Colors.red),
          const SizedBox(width: 12),
          Expanded(
              child: Text(stationsError!,
                  style: const TextStyle(color: Colors.red))),
        ]),
      );
    }

    if (stations.isEmpty && !loadingStations && position != null) {
      return _infoCard(
        child: const Row(children: [
          Icon(Icons.search_off_rounded, color: Colors.blueGrey),
          SizedBox(width: 12),
          Text('No monitoring stations found within 10 km.'),
        ]),
      );
    }

    final risk = RiskStyle.of(_areaRisk);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: risk.color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: risk.color.withOpacity(0.3), width: 1.5),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: risk.color.withOpacity(0.15),
              shape: BoxShape.circle,
            ),
            child: Icon(risk.icon, color: risk.color, size: 28),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Area Flood Risk',
                    style: TextStyle(
                        fontSize: 12, color: Colors.grey.shade600)),
                Text(risk.label,
                    style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: risk.color)),
                Text(risk.description,
                    style: TextStyle(
                        fontSize: 12, color: Colors.grey.shade600)),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('${stations.length}',
                  style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: risk.color)),
              Text('station${stations.length == 1 ? '' : 's'}',
                  style: TextStyle(
                      fontSize: 11, color: Colors.grey.shade500)),
              Text('nearby',
                  style: TextStyle(
                      fontSize: 11, color: Colors.grey.shade500)),
            ],
          ),
        ],
      ),
    );
  }

  // ── NOT IN UK ─────────────────────────────────────────────────────────────

  Widget _buildNotInUKCard() {
    return _infoCard(
      color: Colors.orange.shade50,
      child: Column(
        children: [
          Row(children: [
            Icon(Icons.public_off_rounded,
                color: Colors.orange.shade600, size: 28),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Outside the UK',
                      style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 15,
                          color: Colors.orange.shade800)),
                  Text(
                      'You\'re in ${country!.countryName}. '
                      'EcoFlood only works within the United Kingdom.',
                      style: TextStyle(
                          fontSize: 13,
                          color: Colors.orange.shade700,
                          height: 1.4)),
                ],
              ),
            ),
          ]),
        ],
      ),
    );
  }

  // ── STATIONS SECTION ──────────────────────────────────────────────────────

  Widget _buildStationsSection() {
    if (loadingStations || stations.isEmpty) return const SizedBox.shrink();
    if (country != null && !country!.isUK) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('Monitoring Stations Nearby',
                style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: Colors.black54)),
            Text('${stations.length} found',
                style: const TextStyle(
                    fontSize: 12, color: Colors.blueGrey)),
          ],
        ),
        const SizedBox(height: 8),
        ListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: stations.length,
          itemBuilder: (_, i) => StationCard(station: stations[i]),
        ),
      ],
    );
  }

  // ── HELPERS ───────────────────────────────────────────────────────────────

  Widget _infoCard({required Widget child, Color? color}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color ?? Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withOpacity(0.04),
              blurRadius: 8,
              offset: const Offset(0, 2)),
        ],
      ),
      child: child,
    );
  }

  Widget _pill(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(label,
          style: TextStyle(
              fontSize: 11,
              color: color,
              fontWeight: FontWeight.w600)),
    );
  }
}
