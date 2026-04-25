import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/station.dart';
import '../models/flood_prediction.dart';
import '../services/api_service.dart';
import '../services/cache_service.dart';
import '../services/geocoding_service.dart';
import '../services/notification_service.dart';
import 'home_screen.dart';
import 'map_screen.dart';
import 'alerts_screen.dart';

class ShellScreen extends StatefulWidget {
  const ShellScreen({super.key});

  @override
  State<ShellScreen> createState() => _ShellScreenState();
}

class _ShellScreenState extends State<ShellScreen> with WidgetsBindingObserver {
  final _apiService = ApiService();
  final _cache = CacheService();
  final _geocodingService = GeocodingService();

  int _currentIndex = 0;

  Position? _position;
  CountryResult? _country;
  List<Station> _stations = [];

  bool _loadingLocation = false;
  bool _loadingCountry = false;
  bool _loadingStations = false;
  bool _loadingPrediction = false;

  String? _locationError;
  String? _stationsError;
  FloodPrediction? _prediction;
  String? _predictionError;

  // ── Simulation state ──────────────────────────────────────────────────────
  bool _isSimulating = false;
  List<Station> _realStations = [];
  FloodPrediction? _realPrediction;

  // ── Live location tracking ────────────────────────────────────────────────
  StreamSubscription<Position>? _positionStream;
  Position? _lastCheckedPosition;
  DateTime? _lastRiskCheckTime;

  bool get _isBusy =>
      _loadingLocation || _loadingCountry || _loadingStations;

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _fetchAll();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _positionStream?.cancel();
    super.dispose();
  }

  /// Check notification-tap flag whenever the app comes back to foreground.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _checkNotificationTap();
    }
  }

  Future<void> _checkNotificationTap() async {
    final shouldNav = await NotificationService.shouldNavigateToAlerts();
    if (shouldNav && mounted) {
      setState(() => _currentIndex = 2);
    }
  }

  // ── Initial data fetch ────────────────────────────────────────────────────

  Future<void> _fetchAll() async {
    // Init notifications first — must not be blocked by location
    try { await NotificationService().init(); } catch (_) {}
    await _getLocation();
    if (_position == null) return;
    await _resolveCountry();
    if (_country != null && _country!.isUK) {
      await _fetchStations();
    }
    // Fetch AI prediction
    await _fetchPrediction();
    // Start streaming live location for foreground risk monitoring
    _startLocationStream();
  }

  // ── Location (one-shot) ───────────────────────────────────────────────────

  Future<void> _getLocation() async {
    setState(() {
      _loadingLocation = true;
      _locationError = null;
      _country = null;
      _stations = [];
    });
    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) throw Exception('Location services are disabled.');

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) {
          throw Exception('Location permission denied.');
        }
      }
      if (permission == LocationPermission.deniedForever) {
        throw Exception('Location permission permanently denied.');
      }

      final pos = await Geolocator.getCurrentPosition(
        locationSettings:
            const LocationSettings(accuracy: LocationAccuracy.high),
      );
      setState(() => _position = pos);
    } catch (e) {
      setState(() => _locationError = e.toString());
    } finally {
      setState(() => _loadingLocation = false);
    }
  }

  // ── Continuous location stream (foreground risk monitoring) ───────────────

  void _startLocationStream() {
    _positionStream?.cancel();
    _positionStream = Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.medium,
        // Only emit when the device has moved at least 200 m — avoids GPS noise
        distanceFilter: 200,
      ),
    ).listen(_onPositionUpdate, onError: (_) {});
  }

  Future<void> _onPositionUpdate(Position pos) async {
    // Rate-limit: don't check the EA API more often than every 5 minutes
    final now = DateTime.now();
    if (_lastRiskCheckTime != null &&
        now.difference(_lastRiskCheckTime!) < const Duration(minutes: 5)) {
      return;
    }

    // Skip if we haven't moved more than 500 m since last check
    if (_lastCheckedPosition != null) {
      final moved = Geolocator.distanceBetween(
        _lastCheckedPosition!.latitude,
        _lastCheckedPosition!.longitude,
        pos.latitude,
        pos.longitude,
      );
      if (moved < 500) return;
    }

    _lastCheckedPosition = pos;
    _lastRiskCheckTime = now;

    // Update the displayed position and re-fetch stations for the new location
    setState(() => _position = pos);
    if (_country != null && _country!.isUK) {
      await _fetchStations();
    }

    // Check for HIGH / SEVERE risk and notify if needed
    await _checkAndNotifyRisk();
  }

  // ── AI Prediction ─────────────────────────────────────────────────────────

  Future<void> _fetchPrediction() async {
    if (_position == null) return;
    setState(() {
      _loadingPrediction = true;
      _predictionError = null;
    });

    // Show cached prediction immediately, then fetch fresh in background
    final cachedData = await _cache.loadPrediction();
    if (cachedData != null && mounted) {
      setState(() {
        _prediction = FloodPrediction.fromJson(cachedData);
        _loadingPrediction = false;
      });
    }

    try {
      final prediction = await _apiService.getAiPrediction(
        lat: _position!.latitude,
        lon: _position!.longitude,
      );
      await _cache.savePrediction(prediction.toJson());
      if (mounted) setState(() => _prediction = prediction);
    } catch (e) {
      if (_prediction == null && mounted) {
        setState(() => _predictionError = e.toString());
      }
    } finally {
      if (mounted) setState(() => _loadingPrediction = false);
    }
  }

  // ── Simulation ────────────────────────────────────────────────────────────

  void _showSimulateDialog() {
    final colors = {
      'MINIMAL': Colors.green,
      'MODERATE': Colors.orange,
      'HIGH': Colors.deepOrange,
      'SEVERE': Colors.red,
    };

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.science_outlined, size: 20),
            SizedBox(width: 8),
            Text('Simulate Flood Alert'),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Simulates a flood event — updates all screens, triggers notification with vibration.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
            const SizedBox(height: 12),
            ...kRiskLevels.map((level) {
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: colors[level],
                      foregroundColor: Colors.white,
                    ),
                    onPressed: () {
                      Navigator.pop(ctx);
                      _triggerSimulatedAlert(level);
                    },
                    child: Text(level),
                  ),
                ),
              );
            }),
            if (_isSimulating) ...[
              const Divider(height: 20),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  icon: const Icon(Icons.refresh),
                  label: const Text('Reset to Real Data'),
                  onPressed: () {
                    Navigator.pop(ctx);
                    _resetSimulation();
                  },
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// Fake station sets for each risk level
  List<Station> _buildSimulatedStations(String riskLevel) {
    final base = _position != null
        ? {'lat': _position!.latitude, 'lon': _position!.longitude}
        : {'lat': 51.5, 'lon': -0.1};

    switch (riskLevel) {
      case 'SEVERE':
        return [
          Station(eaStationId: 'SIM-001', stationName: 'River Thames at Twickenham',
              latitude: base['lat']! + 0.01, longitude: base['lon']! + 0.01,
              town: 'Twickenham', riverName: 'River Thames',
              waterLevel: 3.85, riskLevel: 'SEVERE', distanceKm: 0.9),
          Station(eaStationId: 'SIM-002', stationName: 'River Brent at Hanwell',
              latitude: base['lat']! - 0.02, longitude: base['lon']! + 0.02,
              town: 'Hanwell', riverName: 'River Brent',
              waterLevel: 2.41, riskLevel: 'HIGH', distanceKm: 2.1),
          Station(eaStationId: 'SIM-003', stationName: 'Crane at Feltham',
              latitude: base['lat']! + 0.03, longitude: base['lon']! - 0.01,
              town: 'Feltham', riverName: 'River Crane',
              waterLevel: 1.92, riskLevel: 'HIGH', distanceKm: 3.4),
          Station(eaStationId: 'SIM-004', stationName: 'Hogsmill at Kingston',
              latitude: base['lat']! - 0.03, longitude: base['lon']! - 0.02,
              town: 'Kingston', riverName: 'Hogsmill',
              waterLevel: 1.21, riskLevel: 'ELEVATED', distanceKm: 5.7),
        ];
      case 'HIGH':
        return [
          Station(eaStationId: 'SIM-001', stationName: 'River Lea at Edmonton',
              latitude: base['lat']! + 0.01, longitude: base['lon']! + 0.01,
              town: 'Edmonton', riverName: 'River Lea',
              waterLevel: 2.63, riskLevel: 'HIGH', distanceKm: 1.3),
          Station(eaStationId: 'SIM-002', stationName: 'River Roding at Ilford',
              latitude: base['lat']! - 0.02, longitude: base['lon']! + 0.02,
              town: 'Ilford', riverName: 'River Roding',
              waterLevel: 1.88, riskLevel: 'ELEVATED', distanceKm: 2.8),
          Station(eaStationId: 'SIM-003', stationName: 'Pymmes Brook at Ponders End',
              latitude: base['lat']! + 0.03, longitude: base['lon']! - 0.01,
              town: 'Ponders End', riverName: 'Pymmes Brook',
              waterLevel: 1.47, riskLevel: 'ELEVATED', distanceKm: 4.2),
          Station(eaStationId: 'SIM-004', stationName: 'New River at Stoke Newington',
              latitude: base['lat']! - 0.03, longitude: base['lon']! - 0.02,
              town: 'Stoke Newington', riverName: 'New River',
              waterLevel: 0.92, riskLevel: 'NORMAL', distanceKm: 6.1),
        ];
      case 'MODERATE':
        return [
          Station(eaStationId: 'SIM-001', stationName: 'River Wandle at Mitcham',
              latitude: base['lat']! + 0.01, longitude: base['lon']! + 0.01,
              town: 'Mitcham', riverName: 'River Wandle',
              waterLevel: 1.54, riskLevel: 'ELEVATED', distanceKm: 1.8),
          Station(eaStationId: 'SIM-002', stationName: 'River Effra at Brixton',
              latitude: base['lat']! - 0.02, longitude: base['lon']! + 0.02,
              town: 'Brixton', riverName: 'River Effra',
              waterLevel: 1.12, riskLevel: 'ELEVATED', distanceKm: 3.2),
          Station(eaStationId: 'SIM-003', stationName: 'River Falcon at Clapham',
              latitude: base['lat']! + 0.03, longitude: base['lon']! - 0.01,
              town: 'Clapham', riverName: 'River Falcon',
              waterLevel: 0.78, riskLevel: 'NORMAL', distanceKm: 5.0),
        ];
      default: // MINIMAL
        return [
          Station(eaStationId: 'SIM-001', stationName: 'River Colne at Uxbridge',
              latitude: base['lat']! + 0.01, longitude: base['lon']! + 0.01,
              town: 'Uxbridge', riverName: 'River Colne',
              waterLevel: 0.65, riskLevel: 'NORMAL', distanceKm: 2.4),
          Station(eaStationId: 'SIM-002', stationName: 'River Chess at Chorleywood',
              latitude: base['lat']! - 0.02, longitude: base['lon']! + 0.02,
              town: 'Chorleywood', riverName: 'River Chess',
              waterLevel: 0.44, riskLevel: 'NORMAL', distanceKm: 4.1),
        ];
    }
  }

  FloodPrediction _buildSimulatedPrediction(String riskLevel) {
    switch (riskLevel) {
      case 'SEVERE':
        return FloodPrediction(
          riskLevel: 'SEVERE',
          probability: 0.91,
          confidence: 'high',
          reason: 'Extreme rainfall over 72 hours combined with saturated soil and rising river levels at multiple nearby stations.',
          topStation: 'River Thames at Twickenham',
        );
      case 'HIGH':
        return FloodPrediction(
          riskLevel: 'HIGH',
          probability: 0.74,
          confidence: 'high',
          reason: 'Sustained heavy rainfall and rapidly rising water levels detected at River Lea. River expected to exceed flood threshold within 24 hours.',
          topStation: 'River Lea at Edmonton',
        );
      case 'MODERATE':
        return FloodPrediction(
          riskLevel: 'MODERATE',
          probability: 0.43,
          confidence: 'medium',
          reason: 'Elevated water levels at two nearby stations following recent rainfall. Conditions could worsen if further rain occurs.',
          topStation: 'River Wandle at Mitcham',
        );
      default: // MINIMAL
        return FloodPrediction(
          riskLevel: 'MINIMAL',
          probability: 0.12,
          confidence: 'low',
          reason: 'Minor rainfall expected. Water levels within normal range at all nearby stations.',
          topStation: 'River Colne at Uxbridge',
        );
    }
  }

  Future<void> _triggerSimulatedAlert(String riskLevel) async {
    // Save real data before overwriting
    if (!_isSimulating) {
      _realStations  = List.from(_stations);
      _realPrediction = _prediction;
    }

    // Inject fake stations + prediction into state — all screens react automatically
    setState(() {
      _isSimulating = true;
      _stations     = _buildSimulatedStations(riskLevel);
      _prediction   = _buildSimulatedPrediction(riskLevel);
    });

    // Fire notification with vibration
    final sent = await NotificationService().simulateAlert(riskLevel);

    if (!mounted) return;

    // Auto-navigate to Alerts tab for HIGH/SEVERE
    if (riskLevel == 'HIGH' || riskLevel == 'SEVERE') {
      setState(() => _currentIndex = 2);
    }

    // Web fallback snackbar (local notifications not supported on web)
    if (!sent || kIsWeb) {
      final colors = {
        'MINIMAL': Colors.green,
        'MODERATE': Colors.orange,
        'HIGH': Colors.deepOrange,
        'SEVERE': Colors.red,
      };
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: colors[riskLevel],
          duration: const Duration(seconds: 5),
          content: Text(
            '[SIM] ${riskLevel} Flood Alert — tap the bell icon to see alerts',
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
          ),
        ),
      );
    }
  }

  void _resetSimulation() {
    setState(() {
      _isSimulating = false;
      _stations     = _realStations;
      _prediction   = _realPrediction;
    });
  }

  Future<void> _checkAndNotifyRisk() async {
    if (_stations.isEmpty) return;

    const alertLevels = {'SEVERE', 'HIGH'};
    final alerts = _stations
        .where((s) => alertLevels.contains(s.riskLevel.toUpperCase()))
        .toList()
      ..sort((a, b) => _riskScore(b.riskLevel) - _riskScore(a.riskLevel));

    if (alerts.isNotEmpty) {
      await NotificationService().showFloodAlert(alerts.first);
    }
  }

  int _riskScore(String level) =>
      level.toUpperCase() == 'SEVERE' ? 2 : 1;

  // ── Country + stations ────────────────────────────────────────────────────

  Future<void> _resolveCountry() async {
    if (_position == null) return;
    setState(() => _loadingCountry = true);
    try {
      final result = await _geocodingService.getCountry(
        _position!.latitude,
        _position!.longitude,
      );
      setState(() => _country = result);
    } catch (_) {
      // leave _country null — don't block the app
    } finally {
      setState(() => _loadingCountry = false);
    }
  }

  Future<void> _fetchStations() async {
    if (_position == null) return;
    setState(() {
      _loadingStations = true;
      _stationsError = null;
    });

    // Show cached stations immediately, then fetch fresh in background
    final cachedList = await _cache.loadStations(
      lat: _position!.latitude,
      lon: _position!.longitude,
    );
    if (cachedList != null && mounted) {
      setState(() {
        _stations = cachedList.map(Station.fromJson).toList();
        _loadingStations = false;
      });
    }

    try {
      final stations = await _apiService.getNearbyStations(
        lat: _position!.latitude,
        lon: _position!.longitude,
      );
      await _cache.saveStations(
        stations.map((s) => s.toJson()).toList(),
        _position!.latitude,
        _position!.longitude,
      );
      if (mounted) setState(() => _stations = stations);
    } catch (e) {
      if (_stations.isEmpty && mounted) {
        setState(() => _stationsError = e.toString());
      }
    } finally {
      if (mounted) setState(() => _loadingStations = false);
    }
  }

  // ── Tab definitions ───────────────────────────────────────────────────────

  static const _tabs = [
    _TabMeta(label: 'Dashboard', icon: Icons.dashboard_outlined, activeIcon: Icons.dashboard),
    _TabMeta(label: 'Map', icon: Icons.map_outlined, activeIcon: Icons.map),
    _TabMeta(label: 'Alerts', icon: Icons.notifications_outlined, activeIcon: Icons.notifications),
  ];

  String get _appBarTitle => _tabs[_currentIndex].label;

  int get _alertCount => _stations
      .where((s) => ['SEVERE', 'HIGH', 'ELEVATED']
          .contains(s.riskLevel.toUpperCase()))
      .length;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4F8),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1565C0),
        title: Row(
          children: [
            const Icon(Icons.water, color: Colors.white, size: 22),
            const SizedBox(width: 8),
            Text(
              'FloodSense — $_appBarTitle',
              style: const TextStyle(
                  color: Colors.white, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.science_outlined, color: Colors.white),
            onPressed: _showSimulateDialog,
            tooltip: 'Simulate Flood Alert',
          ),
          IconButton(
            icon: _isBusy
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white),
                  )
                : const Icon(Icons.refresh, color: Colors.white),
            onPressed: _isBusy ? null : _fetchAll,
            tooltip: 'Refresh',
          ),
        ],
      ),
      // Simulation banner shown below AppBar
      bottomSheet: _isSimulating
          ? Material(
              color: Colors.deepOrange.shade700,
              child: SafeArea(
                top: false,
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                  child: Row(
                    children: [
                      const Icon(Icons.science, color: Colors.white, size: 14),
                      const SizedBox(width: 6),
                      const Expanded(
                        child: Text(
                          'SIMULATION MODE — tap the flask icon to reset',
                          style: TextStyle(color: Colors.white, fontSize: 11,
                              fontWeight: FontWeight.bold),
                        ),
                      ),
                      GestureDetector(
                        onTap: _resetSimulation,
                        child: const Icon(Icons.close, color: Colors.white, size: 16),
                      ),
                    ],
                  ),
                ),
              ),
            )
          : null,
      body: IndexedStack(
        index: _currentIndex,
        children: [
          DashboardTab(
            position: _position,
            country: _country,
            stations: _stations,
            loadingLocation: _loadingLocation,
            loadingCountry: _loadingCountry,
            loadingStations: _loadingStations,
            locationError: _locationError,
            stationsError: _stationsError,
            prediction: _prediction,
            loadingPrediction: _loadingPrediction,
            predictionError: _predictionError,
          ),
          MapTab(
            position: _position,
            stations: _stations,
            loading: _isBusy,
          ),
          AlertsTab(
            stations: _stations,
            loading: _loadingStations,
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (i) => setState(() => _currentIndex = i),
        backgroundColor: Colors.white,
        indicatorColor: const Color(0xFF1565C0).withOpacity(0.12),
        destinations: [
          NavigationDestination(
            icon: Icon(_tabs[0].icon),
            selectedIcon: Icon(_tabs[0].activeIcon,
                color: const Color(0xFF1565C0)),
            label: _tabs[0].label,
          ),
          NavigationDestination(
            icon: Icon(_tabs[1].icon),
            selectedIcon: Icon(_tabs[1].activeIcon,
                color: const Color(0xFF1565C0)),
            label: _tabs[1].label,
          ),
          NavigationDestination(
            icon: Badge(
              isLabelVisible: _alertCount > 0,
              label: Text('$_alertCount'),
              child: Icon(_tabs[2].icon),
            ),
            selectedIcon: Badge(
              isLabelVisible: _alertCount > 0,
              label: Text('$_alertCount'),
              child: Icon(_tabs[2].activeIcon,
                  color: const Color(0xFF1565C0)),
            ),
            label: _tabs[2].label,
          ),
        ],
      ),
    );
  }
}

class _TabMeta {
  final String label;
  final IconData icon;
  final IconData activeIcon;

  const _TabMeta(
      {required this.label,
      required this.icon,
      required this.activeIcon});
}
