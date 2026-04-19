import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/safe_route.dart';
import '../services/api_service.dart';

class SafeRouteScreen extends StatefulWidget {
  final Position position;

  const SafeRouteScreen({super.key, required this.position});

  @override
  State<SafeRouteScreen> createState() => _SafeRouteScreenState();
}

class _SafeRouteScreenState extends State<SafeRouteScreen> {
  final _api         = ApiService();
  final _mapController = MapController();

  // ── Data ──────────────────────────────────────────────────────────────────
  List<SafePlace> _shelters  = [];
  int            _selIdx     = 0;
  List<List<double>> _coords = [];
  double         _distKm     = 0;
  int            _durMin     = 0;
  List<RouteStep> _steps     = [];
  String?        _routeWarn;

  // ── State ─────────────────────────────────────────────────────────────────
  bool    _loading   = true;
  bool    _rerouting = false;
  String? _error;
  String  _profile   = 'driving-car';
  bool    _showSteps = false;

  SafePlace? get _shelter =>
      _shelters.isNotEmpty ? _shelters[_selIdx] : null;

  LatLng get _userPos =>
      LatLng(widget.position.latitude, widget.position.longitude);

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  @override
  void initState() {
    super.initState();
    _fetchInitial();
  }

  // ── Fetching ───────────────────────────────────────────────────────────────

  Future<void> _fetchInitial() async {
    setState(() {
      _loading = true;
      _error   = null;
    });
    try {
      final route = await _api.getSafeRoute(
        lat:     widget.position.latitude,
        lon:     widget.position.longitude,
        profile: _profile,
      );
      if (!mounted) return;
      // Set _loading = false in the SAME setState as the data so the
      // FlutterMap is added to the tree before _fitMap() fires.
      setState(() {
        _shelters  = route.allShelters;
        _selIdx    = 0;
        _coords    = route.coordinates;
        _distKm    = route.distanceKm;
        _durMin    = route.durationMin;
        _steps     = route.steps;
        _routeWarn = route.routeWarning;
        _loading   = false;
      });
      _fitMap();
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _selectShelter(int index) async {
    if (index == _selIdx && _coords.isNotEmpty) {
      _fitMap();
      return;
    }

    setState(() {
      _selIdx    = index;
      _rerouting = true;
      _showSteps = false;
      _routeWarn = null;
    });

    final shelter = _shelters[index];

    // Move map immediately to approximate position while fetching route
    _fitMapTo(_userPos, LatLng(shelter.latitude, shelter.longitude));

    try {
      final routeData = await _api.getRouteTo(
        fromLat: widget.position.latitude,
        fromLon: widget.position.longitude,
        toLat:   shelter.latitude,
        toLon:   shelter.longitude,
        profile: _profile,
      );
      if (!mounted) return;
      setState(() {
        _coords = routeData.coordinates;
        _distKm = routeData.distanceKm;
        _durMin = routeData.durationMin;
        _steps  = routeData.steps;
      });
      _fitMap();
    } catch (_) {
      // ORS failed — still show the shelter, just without polyline
      if (!mounted) return;
      setState(() {
        _coords    = [];
        _distKm    = shelter.distanceKm;
        _durMin    = 0;
        _steps     = [];
        _routeWarn = 'Turn-by-turn routing unavailable';
      });
    } finally {
      if (mounted) setState(() => _rerouting = false);
    }
  }

  Future<void> _changeProfile(String profile) async {
    setState(() => _profile = profile);
    // Re-fetch route to current shelter with new travel mode
    if (_shelter == null) return;
    final idx = _selIdx;
    setState(() {
      _selIdx    = idx;
      _rerouting = true;
      _showSteps = false;
    });
    try {
      final routeData = await _api.getRouteTo(
        fromLat: widget.position.latitude,
        fromLon: widget.position.longitude,
        toLat:   _shelters[idx].latitude,
        toLon:   _shelters[idx].longitude,
        profile: profile,
      );
      if (!mounted) return;
      setState(() {
        _coords = routeData.coordinates;
        _distKm = routeData.distanceKm;
        _durMin = routeData.durationMin;
        _steps  = routeData.steps;
        _routeWarn = null;
      });
      _fitMap();
    } catch (_) {
      if (mounted) {
        setState(() {
          _coords    = [];
          _routeWarn = 'Routing unavailable for this mode';
        });
      }
    } finally {
      if (mounted) setState(() => _rerouting = false);
    }
  }

  // ── Map helpers ────────────────────────────────────────────────────────────

  void _fitMapTo(LatLng a, LatLng b, {List<LatLng> extra = const []}) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final pts = [a, b, ...extra];
      final bounds = LatLngBounds.fromPoints(pts);
      try {
        _mapController.fitCamera(
          CameraFit.bounds(
            bounds:  bounds,
            padding: const EdgeInsets.all(50),
          ),
        );
      } catch (_) {}
    });
  }

  void _fitMap() {
    final s = _shelter;
    if (s == null) return;
    final shelterPt = LatLng(s.latitude, s.longitude);
    final routePts  = _coords.map((c) => LatLng(c[0], c[1])).toList();
    _fitMapTo(_userPos, shelterPt, extra: routePts);
  }

  // ── Navigation ────────────────────────────────────────────────────────────

  Future<void> _openNavigation() async {
    final s = _shelter;
    if (s == null) return;

    final mode = _profile == 'driving-car' ? 'driving' : 'walking';
    final url  = Uri.parse(
      'https://www.google.com/maps/dir/?api=1'
      '&origin=${widget.position.latitude},${widget.position.longitude}'
      '&destination=${s.latitude},${s.longitude}'
      '&travelmode=$mode',
    );

    if (await canLaunchUrl(url)) {
      await launchUrl(url, mode: LaunchMode.externalApplication);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open Maps app')),
        );
      }
    }
  }

  // ── Build ─────────────────────────────────────────────────────────────────

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
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: SegmentedButton<String>(
              style: SegmentedButton.styleFrom(
                backgroundColor:         Colors.red.shade800,
                selectedBackgroundColor: Colors.white,
                selectedForegroundColor: Colors.red.shade900,
                foregroundColor:         Colors.white,
                textStyle:               const TextStyle(fontSize: 11),
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
              onSelectionChanged: (s) => _changeProfile(s.first),
            ),
          ),
        ],
      ),
      body: _loading
          ? _buildLoader()
          : _error != null
              ? _buildError()
              : _buildContent(),
    );
  }

  // ── Loading ────────────────────────────────────────────────────────────────

  Widget _buildLoader() {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(color: Color(0xFFB71C1C)),
          SizedBox(height: 16),
          Text('Finding safe shelters…',
              style: TextStyle(fontSize: 14, color: Colors.grey)),
          SizedBox(height: 6),
          Text('This may take up to 30 s',
              style: TextStyle(fontSize: 12, color: Colors.grey)),
        ],
      ),
    );
  }

  // ── Error ─────────────────────────────────────────────────────────────────

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.location_off, size: 56, color: Colors.grey),
            const SizedBox(height: 16),
            Text(
              _error!.contains('No safe shelters')
                  ? 'No safe shelters found nearby.\nTry a different location or expand your search.'
                  : 'Could not load safe route.\nCheck your connection and try again.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.red, fontSize: 14),
            ),
            const SizedBox(height: 8),
            Text(
              _error!,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.grey, fontSize: 11),
            ),
            const SizedBox(height: 20),
            ElevatedButton.icon(
              onPressed: _fetchInitial,
              icon:  const Icon(Icons.refresh),
              label: const Text('Retry'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFB71C1C),
                foregroundColor: Colors.white,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Main content ───────────────────────────────────────────────────────────

  Widget _buildContent() {
    final shelter = _shelter;
    if (shelter == null) return _buildError();

    final shelterPt  = LatLng(shelter.latitude, shelter.longitude);
    final routePts   = _coords.map((c) => LatLng(c[0], c[1])).toList();
    final allPts     = [_userPos, shelterPt, ...routePts];
    final bounds     = LatLngBounds.fromPoints(allPts);

    return Column(
      children: [
        // ── Route-warning banner ────────────────────────────────────────────
        if (_routeWarn != null)
          Container(
            width: double.infinity,
            color: Colors.orange.shade700,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            child: Row(
              children: [
                const Icon(Icons.warning_amber_rounded,
                    color: Colors.white, size: 16),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    _routeWarn!,
                    style: const TextStyle(
                        color: Colors.white, fontSize: 12),
                  ),
                ),
              ],
            ),
          ),

        // ── Map ─────────────────────────────────────────────────────────────
        Expanded(
          flex: 3,
          child: Stack(
            children: [
              FlutterMap(
                mapController: _mapController,
                options: MapOptions(
                  initialCameraFit: CameraFit.bounds(
                    bounds:  bounds,
                    padding: const EdgeInsets.all(50),
                  ),
                ),
                children: [
                  TileLayer(
                    urlTemplate:
                        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                    userAgentPackageName: 'com.ecoflood.app',
                  ),
                  if (routePts.isNotEmpty)
                    PolylineLayer(
                      polylines: [
                        Polyline(
                          points:      routePts,
                          strokeWidth: 5,
                          color:       const Color(0xFFB71C1C),
                        ),
                      ],
                    ),
                  MarkerLayer(
                    markers: [
                      // User
                      Marker(
                        point:  _userPos,
                        width:  44,
                        height: 44,
                        child: Container(
                          decoration: BoxDecoration(
                            color:  const Color(0xFF1565C0),
                            shape:  BoxShape.circle,
                            border: Border.all(color: Colors.white, width: 2.5),
                          ),
                          child: const Icon(Icons.person_pin,
                              color: Colors.white, size: 22),
                        ),
                      ),
                      // Non-selected shelters — tappable grey dots
                      ..._shelters.asMap().entries
                          .where((e) => e.key != _selIdx)
                          .map((e) => Marker(
                                point:  LatLng(e.value.latitude, e.value.longitude),
                                width:  36,
                                height: 36,
                                child: GestureDetector(
                                  onTap: () => _selectShelter(e.key),
                                  child: Container(
                                    decoration: BoxDecoration(
                                      color:  Colors.grey.shade500,
                                      shape:  BoxShape.circle,
                                      border: Border.all(
                                          color: Colors.white, width: 1.5),
                                    ),
                                    child: const Icon(Icons.home_outlined,
                                        color: Colors.white, size: 16),
                                  ),
                                ),
                              )),
                      // Selected shelter — highlighted green
                      Marker(
                        point:  shelterPt,
                        width:  52,
                        height: 52,
                        child: Container(
                          decoration: BoxDecoration(
                            color:  Colors.green.shade700,
                            shape:  BoxShape.circle,
                            border: Border.all(color: Colors.white, width: 2.5),
                            boxShadow: [
                              BoxShadow(
                                  color: Colors.green.withValues(alpha: 0.4),
                                  blurRadius: 10)
                            ],
                          ),
                          child: const Icon(Icons.home,
                              color: Colors.white, size: 24),
                        ),
                      ),
                    ],
                  ),
                ],
              ),

              // Rerouting spinner overlay
              if (_rerouting)
                Positioned.fill(
                  child: Container(
                    color: Colors.black26,
                    child: const Center(
                      child: Card(
                        child: Padding(
                          padding: EdgeInsets.all(16),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              CircularProgressIndicator(strokeWidth: 2),
                              SizedBox(width: 12),
                              Text('Calculating route…'),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),

        // ── Bottom info panel ─────────────────────────────────────────────
        Container(
          color: Colors.white,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Shelter info row
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color:        Colors.green.shade50,
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
                          Text(shelter.name,
                              style: const TextStyle(
                                  fontWeight: FontWeight.bold, fontSize: 15)),
                          Text(shelter.typeLabel,
                              style: TextStyle(
                                  color: Colors.grey.shade600, fontSize: 12)),
                          if (shelter.address.isNotEmpty)
                            Text(shelter.address,
                                style: TextStyle(
                                    color: Colors.grey.shade500, fontSize: 11)),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text('${_distKm.toStringAsFixed(1)} km',
                            style: const TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 16,
                                color: Color(0xFFB71C1C))),
                        if (_durMin > 0)
                          Text('~$_durMin min',
                              style: TextStyle(
                                  color: Colors.grey.shade600, fontSize: 12)),
                      ],
                    ),
                  ],
                ),
              ),

              // Navigate button
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
                child: SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _openNavigation,
                    icon:  const Icon(Icons.navigation, size: 18),
                    label: Text(
                      'Navigate with Google Maps  '
                      '(${_profile == 'driving-car' ? 'Driving' : 'Walking'})',
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green.shade700,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                  ),
                ),
              ),

              const Divider(height: 1),

              // Turn-by-turn toggle
              if (_steps.isNotEmpty)
                InkWell(
                  onTap: () => setState(() => _showSteps = !_showSteps),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 10),
                    child: Row(
                      children: [
                        const Icon(Icons.turn_right,
                            size: 16, color: Color(0xFF1565C0)),
                        const SizedBox(width: 8),
                        Text(
                          '${_steps.length} turn-by-turn directions',
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

              if (_showSteps && _steps.isNotEmpty)
                ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 200),
                  child: ListView.separated(
                    shrinkWrap:      true,
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                    itemCount:       _steps.length,
                    separatorBuilder: (ctx, i) =>
                        const Divider(height: 1, indent: 32),
                    itemBuilder: (_, i) {
                      final step = _steps[i];
                      return Padding(
                        padding:
                            const EdgeInsets.symmetric(vertical: 8),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              width:  22,
                              height: 22,
                              decoration: BoxDecoration(
                                color: const Color(0xFF1565C0)
                                    .withValues(alpha: 0.1),
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
                            Text('${step.distanceM} m',
                                style: TextStyle(
                                    fontSize: 11,
                                    color: Colors.grey.shade500)),
                          ],
                        ),
                      );
                    },
                  ),
                ),

              // Nearby shelters chips
              if (_shelters.length > 1)
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
                          children: _shelters
                              .asMap()
                              .entries
                              .where((e) => e.key != _selIdx)
                              .map((e) {
                            final p = e.value;
                            return Padding(
                              padding: const EdgeInsets.only(right: 8),
                              child: ActionChip(
                                avatar: const Icon(Icons.home_outlined,
                                    size: 14),
                                label: Text(
                                  '${p.name} (${p.distanceKm} km)',
                                  style: const TextStyle(fontSize: 11),
                                ),
                                onPressed: () => _selectShelter(e.key),
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
