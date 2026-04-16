import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import '../models/safe_route.dart';
import '../services/api_service.dart';

class SafeRouteScreen extends StatefulWidget {
  final Position position;

  const SafeRouteScreen({super.key, required this.position});

  @override
  State<SafeRouteScreen> createState() => _SafeRouteScreenState();
}

class _SafeRouteScreenState extends State<SafeRouteScreen> {
  final _api = ApiService();

  SafeRoute? _route;
  bool _loading = true;
  String? _error;
  String _profile = 'driving-car';
  bool _showSteps = false;

  @override
  void initState() {
    super.initState();
    _fetchRoute();
  }

  Future<void> _fetchRoute() async {
    setState(() {
      _loading = true;
      _error   = null;
    });
    try {
      final route = await _api.getSafeRoute(
        lat:      widget.position.latitude,
        lon:      widget.position.longitude,
        profile:  _profile,
      );
      setState(() => _route = route);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4F8),
      appBar: AppBar(
        backgroundColor: const Color(0xFFB71C1C),
        title: const Row(
          children: [
            Icon(Icons.emergency, color: Colors.white, size: 20),
            SizedBox(width: 8),
            Text('Safe Route',
                style: TextStyle(
                    color: Colors.white, fontWeight: FontWeight.bold)),
          ],
        ),
        actions: [
          // Toggle walking/driving
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: SegmentedButton<String>(
              style: SegmentedButton.styleFrom(
                backgroundColor: Colors.red.shade800,
                selectedBackgroundColor: Colors.white,
                selectedForegroundColor: Colors.red.shade900,
                foregroundColor: Colors.white,
                textStyle: const TextStyle(fontSize: 11),
              ),
              segments: const [
                ButtonSegment(
                    value: 'driving-car',
                    icon: Icon(Icons.directions_car, size: 14)),
                ButtonSegment(
                    value: 'foot-walking',
                    icon: Icon(Icons.directions_walk, size: 14)),
              ],
              selected: {_profile},
              onSelectionChanged: (s) {
                setState(() => _profile = s.first);
                _fetchRoute();
              },
            ),
          ),
        ],
      ),
      body: _loading
          ? const Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CircularProgressIndicator(color: Color(0xFFB71C1C)),
                  SizedBox(height: 16),
                  Text('Finding safe route…'),
                ],
              ),
            )
          : _error != null
              ? _buildError()
              : _buildContent(),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.location_off, size: 48, color: Colors.grey),
            const SizedBox(height: 16),
            Text(_error!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.red)),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _fetchRoute,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent() {
    final route   = _route!;
    final userPos = LatLng(widget.position.latitude, widget.position.longitude);
    final shelter = LatLng(route.shelter.latitude, route.shelter.longitude);

    // Build route polyline
    final routePoints = route.coordinates
        .map((c) => LatLng(c[0], c[1]))
        .toList();

    // Bounds to fit both user + shelter
    final bounds = LatLngBounds.fromPoints([userPos, shelter, ...routePoints]);

    return Column(
      children: [
        // ── Map ──────────────────────────────────────────────────────────────
        Expanded(
          flex: 3,
          child: FlutterMap(
            options: MapOptions(
              initialCameraFit: CameraFit.bounds(
                bounds: bounds,
                padding: const EdgeInsets.all(40),
              ),
            ),
            children: [
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.ecoflood.app',
              ),
              // Route polyline
              if (routePoints.isNotEmpty)
                PolylineLayer(
                  polylines: [
                    Polyline(
                      points: routePoints,
                      strokeWidth: 5,
                      color: const Color(0xFFB71C1C),
                    ),
                  ],
                ),
              MarkerLayer(
                markers: [
                  // User location
                  Marker(
                    point: userPos,
                    width: 44,
                    height: 44,
                    child: Container(
                      decoration: BoxDecoration(
                        color: const Color(0xFF1565C0),
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 2.5),
                      ),
                      child: const Icon(Icons.person_pin,
                          color: Colors.white, size: 22),
                    ),
                  ),
                  // Shelter marker
                  Marker(
                    point: shelter,
                    width: 48,
                    height: 48,
                    child: Container(
                      decoration: BoxDecoration(
                        color: Colors.green.shade700,
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 2.5),
                        boxShadow: [
                          BoxShadow(
                              color: Colors.green.withOpacity(0.4),
                              blurRadius: 8)
                        ],
                      ),
                      child: const Icon(Icons.home, color: Colors.white, size: 22),
                    ),
                  ),
                  // Other shelters (grey)
                  ...route.allShelters.skip(1).map((p) => Marker(
                        point: LatLng(p.latitude, p.longitude),
                        width: 32,
                        height: 32,
                        child: Container(
                          decoration: BoxDecoration(
                            color: Colors.grey.shade500,
                            shape: BoxShape.circle,
                            border: Border.all(color: Colors.white, width: 1.5),
                          ),
                          child: const Icon(Icons.home_outlined,
                              color: Colors.white, size: 14),
                        ),
                      )),
                ],
              ),
            ],
          ),
        ),

        // ── Info panel ───────────────────────────────────────────────────────
        Container(
          color: Colors.white,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Shelter info + stats
              Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: Colors.green.shade50,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(Icons.home,
                          color: Colors.green.shade700, size: 24),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(route.shelter.name,
                              style: const TextStyle(
                                  fontWeight: FontWeight.bold, fontSize: 15)),
                          Text(route.shelter.typeLabel,
                              style: TextStyle(
                                  color: Colors.grey.shade600, fontSize: 12)),
                        ],
                      ),
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text('${route.distanceKm} km',
                            style: const TextStyle(
                                fontWeight: FontWeight.bold, fontSize: 16,
                                color: Color(0xFFB71C1C))),
                        Text('~${route.durationMin} min',
                            style: TextStyle(
                                color: Colors.grey.shade600, fontSize: 12)),
                      ],
                    ),
                  ],
                ),
              ),

              const Divider(height: 1),

              // Show/hide steps
              InkWell(
                onTap: () => setState(() => _showSteps = !_showSteps),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 10),
                  child: Row(
                    children: [
                      const Icon(Icons.turn_right, size: 16,
                          color: Color(0xFF1565C0)),
                      const SizedBox(width: 8),
                      Text(
                        '${route.steps.length} turn-by-turn directions',
                        style: const TextStyle(
                            color: Color(0xFF1565C0),
                            fontWeight: FontWeight.w500,
                            fontSize: 13),
                      ),
                      const Spacer(),
                      Icon(
                        _showSteps
                            ? Icons.keyboard_arrow_up
                            : Icons.keyboard_arrow_down,
                        color: Colors.grey,
                      ),
                    ],
                  ),
                ),
              ),

              if (_showSteps)
                ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 200),
                  child: ListView.separated(
                    shrinkWrap: true,
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                    itemCount: route.steps.length,
                    separatorBuilder: (_, __) =>
                        const Divider(height: 1, indent: 32),
                    itemBuilder: (_, i) {
                      final step = route.steps[i];
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              width: 22,
                              height: 22,
                              decoration: BoxDecoration(
                                color: const Color(0xFF1565C0).withOpacity(0.1),
                                shape: BoxShape.circle,
                              ),
                              child: Center(
                                child: Text('${i + 1}',
                                    style: const TextStyle(
                                        fontSize: 10,
                                        color: Color(0xFF1565C0),
                                        fontWeight: FontWeight.bold)),
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(step.instruction,
                                  style: const TextStyle(fontSize: 13)),
                            ),
                            const SizedBox(width: 8),
                            Text('${step.distanceM}m',
                                style: TextStyle(
                                    fontSize: 11, color: Colors.grey.shade500)),
                          ],
                        ),
                      );
                    },
                  ),
                ),

              // Nearby shelters
              if (route.allShelters.length > 1)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Divider(height: 1),
                      const SizedBox(height: 8),
                      Text('Other nearby shelters',
                          style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: Colors.grey.shade600)),
                      const SizedBox(height: 6),
                      SizedBox(
                        height: 36,
                        child: ListView(
                          scrollDirection: Axis.horizontal,
                          children: route.allShelters.skip(1).map((p) {
                            return Padding(
                              padding: const EdgeInsets.only(right: 8),
                              child: ActionChip(
                                avatar: const Icon(Icons.home_outlined, size: 14),
                                label: Text('${p.name} (${p.distanceKm}km)',
                                    style: const TextStyle(fontSize: 11)),
                                onPressed: () {},
                              ),
                            );
                          }).toList(),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
