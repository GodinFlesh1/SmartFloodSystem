import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:geolocator/geolocator.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:workmanager/workmanager.dart';
import 'api_service.dart';

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

    // 2. Firebase must be initialised in every isolate
    if (Firebase.apps.isEmpty) {
      await Firebase.initializeApp();
    }

    // 3. Get current position (prefer last known for speed; fall back to fresh fix)
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

    // 4. Fetch nearby stations via the backend
    final stations = await ApiService().getNearbyStations(
      lat: position.latitude,
      lon: position.longitude,
    );

    // 5. Find the worst HIGH/SEVERE station
    const alertLevels = {'SEVERE', 'HIGH'};
    final alerts = stations
        .where((s) => alertLevels.contains(s.riskLevel.toUpperCase()))
        .toList()
      ..sort((a, b) => _score(b.riskLevel) - _score(a.riskLevel));

    if (alerts.isEmpty) return;

    // 6. Show local notification
    final worst = alerts.first;
    await _showNotification(worst.riskLevel, worst.stationName);
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
