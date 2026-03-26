import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import '../models/station.dart';
import '../services/api_service.dart';
import '../services/geocoding_service.dart';
import 'home_screen.dart';
import 'map_screen.dart';
import 'alerts_screen.dart';

class ShellScreen extends StatefulWidget {
  const ShellScreen({super.key});

  @override
  State<ShellScreen> createState() => _ShellScreenState();
}

class _ShellScreenState extends State<ShellScreen> {
  final _apiService = ApiService();
  final _geocodingService = GeocodingService();

  int _currentIndex = 0;

  Position? _position;
  CountryResult? _country;
  List<Station> _stations = [];

  bool _loadingLocation = false;
  bool _loadingCountry = false;
  bool _loadingStations = false;

  String? _locationError;
  String? _stationsError;

  bool get _isBusy =>
      _loadingLocation || _loadingCountry || _loadingStations;

  @override
  void initState() {
    super.initState();
    _fetchAll();
  }

  Future<void> _fetchAll() async {
    await _getLocation();
    if (_position == null) return;
    await _resolveCountry();
    if (_country != null && _country!.isUK) {
      await _fetchStations();
    }
  }

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
    try {
      final stations = await _apiService.getNearbyStations(
        lat: _position!.latitude,
        lon: _position!.longitude,
      );
      setState(() => _stations = stations);
    } catch (e) {
      setState(() => _stationsError = e.toString());
    } finally {
      setState(() => _loadingStations = false);
    }
  }

  // ── TAB DEFINITIONS ───────────────────────────────────────────────────────

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
              'EcoFlood — $_appBarTitle',
              style: const TextStyle(
                  color: Colors.white, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        actions: [
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
