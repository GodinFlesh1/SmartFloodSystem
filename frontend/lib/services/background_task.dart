import 'dart:convert';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:workmanager/workmanager.dart';
import '../config/app_config.dart';
import 'auth_service.dart';

const String floodCheckTask = 'flood_check_task';

// ── Workmanager entry point ────────────────────────────────────────────────────
// Must be top-level and annotated — runs in a separate Dart isolate.
@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, _) async {
    if (task == floodCheckTask) {
      await _runFloodCheck();
    }
    return true; // always return true to avoid workmanager cancelling the task
  });
}

// ── Core background check ──────────────────────────────────────────────────────

Future<void> _runFloodCheck() async {
  try {
    // 1. Cooldown — skip if we already notified within the last hour
    final prefs = await SharedPreferences.getInstance();
    final lastMs = prefs.getInt('last_flood_notification_ms') ?? 0;
    final nowMs = DateTime.now().millisecondsSinceEpoch;
    if (nowMs - lastMs < 3600000) return;

    // 2. Firebase must be initialised in every isolate (for SharedPreferences
    //    plugin compatibility — FirebaseAuth state is NOT available here)
    if (Firebase.apps.isEmpty) {
      await Firebase.initializeApp();
    }

    // 3. Read the cached auth token — FirebaseAuth.currentUser is null in
    //    background isolates, so we use the token saved by the foreground app.
    final token = await AuthService.getStoredToken();
    if (token == null) {
      debugPrint('[BG] No stored auth token — skipping flood check.');
      return;
    }

    // 4. Get current position (prefer last known for speed; fall back to fresh fix)
    Position? position;
    try {
      position = await Geolocator.getLastKnownPosition();
      if (position == null) {
        position = await Geolocator.getCurrentPosition(
          locationSettings: const LocationSettings(
            accuracy: LocationAccuracy.medium,
          ),
        ).timeout(const Duration(seconds: 20));
      }
    } catch (e) {
      debugPrint('[BG] Could not get position: $e');
      return;
    }

    // 5. Fetch nearby stations directly — ApiService cannot be used in
    //    isolates because it depends on FirebaseAuth state.
    final uri = Uri.parse(
      '${AppConfig.apiBaseUrl}/api/live/stations/nearby'
      '?lat=${position.latitude}&lon=${position.longitude}&radius_km=5',
    );
    final response = await http
        .get(uri, headers: {'Authorization': 'Bearer $token'})
        .timeout(const Duration(seconds: 15));

    if (response.statusCode != 200) {
      debugPrint('[BG] API error ${response.statusCode}');
      return;
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    if (data['success'] != true) return;

    final stationsRaw = data['stations'] as List<dynamic>? ?? [];

    // 6. Find the worst HIGH/SEVERE station
    const alertLevels = {'SEVERE', 'HIGH'};
    final alerts = stationsRaw
        .cast<Map<String, dynamic>>()
        .where((s) => alertLevels.contains(
              (s['risk_level'] as String? ?? '').toUpperCase(),
            ))
        .toList()
      ..sort((a, b) =>
          _score(b['risk_level'] as String) - _score(a['risk_level'] as String));

    if (alerts.isEmpty) return;

    // 7. Show local notification
    final worst = alerts.first;
    await _showNotification(
      worst['risk_level'] as String,
      worst['station_name'] as String? ?? 'Nearby station',
    );
    await prefs.setInt('last_flood_notification_ms', nowMs);
  } catch (e) {
    debugPrint('[BG] Flood check error: $e');
  }
}

int _score(String level) => level.toUpperCase() == 'SEVERE' ? 2 : 1;

// ── Notification display (background isolate — no app context available) ───────

Future<void> _showNotification(String riskLevel, String stationName) async {
  final plugin = FlutterLocalNotificationsPlugin();

  const initSettings = InitializationSettings(
    android: AndroidInitializationSettings('@mipmap/ic_launcher'),
    iOS: DarwinInitializationSettings(),
  );
  await plugin.initialize(initSettings);

  final isSevere = riskLevel.toUpperCase() == 'SEVERE';

  await plugin.show(
    riskLevel.hashCode,
    isSevere ? 'SEVERE Flood Warning' : 'Flood Risk Alert',
    isSevere
        ? '$stationName near you — SEVERE risk. Take immediate action.'
        : '$stationName near you — HIGH flood risk. Stay alert.',
    const NotificationDetails(
      android: AndroidNotificationDetails(
        'flood_alerts',
        'Flood Alerts',
        channelDescription: 'Emergency flood risk notifications from EcoFlood',
        importance: Importance.max,
        priority: Priority.max,
        playSound: true,
        enableVibration: true,
      ),
      iOS: DarwinNotificationDetails(
        presentAlert: true,
        presentBadge: true,
        presentSound: true,
        interruptionLevel: InterruptionLevel.critical,
      ),
    ),
  );
}
