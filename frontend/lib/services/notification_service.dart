import 'dart:typed_data';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart' show Color;
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:workmanager/workmanager.dart';
import '../models/station.dart';
import 'background_task.dart';

// Risk levels ordered lowest → highest
const List<String> kRiskLevels = ['MINIMAL', 'MODERATE', 'HIGH', 'SEVERE'];

// ── FCM background handler (top-level, called by Firebase when app is killed) ─
// FCM can still wake the app via data messages in the future.
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  debugPrint('[FCM background] ${message.notification?.title}');
}

// ── Shared notification channel ───────────────────────────────────────────────
const AndroidNotificationChannel floodChannel = AndroidNotificationChannel(
  'flood_alerts',
  'Flood Alerts',
  description: 'Emergency flood risk notifications from EcoFlood',
  importance: Importance.max,
  playSound: true,
  enableVibration: true,
);

final FlutterLocalNotificationsPlugin localNotifications =
    FlutterLocalNotificationsPlugin();

// ── NotificationService ───────────────────────────────────────────────────────

class NotificationService {
  static final NotificationService _instance = NotificationService._();
  factory NotificationService() => _instance;
  NotificationService._();

  bool _ready = false;

  /// Call once after Firebase.initializeApp() — sets up local notifications,
  /// requests permission, and registers the workmanager background task.
  Future<void> init() async {
    if (_ready) return;
    _ready = true;
    if (!kIsWeb) {
      await _setupChannel();     // Android/iOS only
      await _startWorkmanager(); // Android/iOS only
    }
    await _requestPermission();  // works on web (Firebase web push)
  }

  // ── Local notification channel setup ────────────────────────────────────────

  Future<void> _setupChannel() async {
    // Android: create the notification channel (required for Android 8+)
    await localNotifications
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(floodChannel);

    await localNotifications.initialize(
      const InitializationSettings(
        android: AndroidInitializationSettings('@mipmap/ic_launcher'),
        iOS: DarwinInitializationSettings(),
      ),
      onDidReceiveNotificationResponse: (_) => _flagNavigateToAlerts(),
    );
  }

  // ── Permission ───────────────────────────────────────────────────────────────

  Future<void> _requestPermission() async {
    // Firebase Messaging requests permission on both Android 13+ and iOS
    final settings = await FirebaseMessaging.instance.requestPermission(
      alert: true,
      badge: true,
      sound: true,
      criticalAlert: true, // iOS: bypasses Do Not Disturb for flood alerts
    );
    debugPrint('[Notifications] Permission: ${settings.authorizationStatus}');
  }

  // ── Workmanager background task ──────────────────────────────────────────────

  Future<void> _startWorkmanager() async {
    await Workmanager().initialize(
      callbackDispatcher,
      isInDebugMode: false,
    );
    // Registers a periodic background task.
    // Android: fires every ~15 min (OS minimum).
    // iOS: best-effort — iOS controls the actual schedule via BGTaskScheduler.
    await Workmanager().registerPeriodicTask(
      'ecoflood_flood_check',
      floodCheckTask,
      frequency: const Duration(minutes: 15),
      constraints: Constraints(networkType: NetworkType.connected),
      existingWorkPolicy: ExistingPeriodicWorkPolicy.keep,
    );
  }

  // ── Show alert from foreground ───────────────────────────────────────────────

  /// Called by ShellScreen when a HIGH/SEVERE station is detected in the
  /// foreground location stream. Respects the same 1-hour cooldown as the
  /// background task so the user is not double-notified.
  Future<void> showFloodAlert(Station station) async {
    final prefs = await SharedPreferences.getInstance();
    final lastMs = prefs.getInt('last_flood_notification_ms') ?? 0;
    final nowMs = DateTime.now().millisecondsSinceEpoch;
    if (nowMs - lastMs < 3600000) return; // 1-hour cooldown

    final isSevere = station.riskLevel.toUpperCase() == 'SEVERE';
    final title =
        isSevere ? 'SEVERE Flood Warning' : 'Flood Risk Alert';
    final body = isSevere
        ? '${station.stationName} near you — SEVERE risk. Take immediate action.'
        : '${station.stationName} near you — HIGH flood risk. Stay alert.';

    await localNotifications.show(
      station.riskLevel.hashCode,
      title,
      body,
      NotificationDetails(
        android: AndroidNotificationDetails(
          floodChannel.id,
          floodChannel.name,
          channelDescription: floodChannel.description,
          importance: Importance.max,
          priority: Priority.max,
          playSound: true,
          enableVibration: true,
        ),
        iOS: const DarwinNotificationDetails(
          presentAlert: true,
          presentBadge: true,
          presentSound: true,
          interruptionLevel: InterruptionLevel.critical,
        ),
      ),
    );

    await prefs.setInt('last_flood_notification_ms', nowMs);
    await _flagNavigateToAlerts();
  }

  // ── Simulation (dev/testing only) ────────────────────────────────────────────

  /// Bypasses the 1-hour cooldown and fires a fake flood alert at [riskLevel].
  /// Returns false on web (flutter_local_notifications unsupported) so the
  /// caller can show an in-app fallback instead.
  Future<bool> simulateAlert(String riskLevel) async {
    if (kIsWeb) return false;

    final fakeStation = Station(
      eaStationId: 'SIM-001',
      stationName: 'Simulated River Station',
      latitude: 51.5,
      longitude: -0.1,
      town: 'Nearby Town',
      riverName: 'River Test',
      waterLevel: 2.5,
      riskLevel: riskLevel,
      distanceKm: 1.2,
    );

    final titles = {
      'MINIMAL': 'Low Flood Risk Nearby',
      'MODERATE': 'Moderate Flood Risk',
      'HIGH': 'Flood Risk Alert',
      'SEVERE': 'SEVERE Flood Warning',
    };
    final bodies = {
      'MINIMAL': '${fakeStation.stationName} — minimal flood risk. Stay informed.',
      'MODERATE': '${fakeStation.stationName} — moderate flood risk in your area.',
      'HIGH': '${fakeStation.stationName} — HIGH flood risk nearby. Stay alert.',
      'SEVERE': '${fakeStation.stationName} — SEVERE risk. Take immediate action!',
    };

    // Stronger vibration for HIGH/SEVERE: long-short-long pattern
    final vibrationPattern = (riskLevel == 'HIGH' || riskLevel == 'SEVERE')
        ? Int64List.fromList([0, 500, 200, 500, 200, 800])
        : Int64List.fromList([0, 300, 150, 300]);

    await localNotifications.show(
      riskLevel.hashCode,
      titles[riskLevel] ?? 'Flood Alert',
      bodies[riskLevel] ?? 'Flood risk detected near you.',
      NotificationDetails(
        android: AndroidNotificationDetails(
          floodChannel.id,
          floodChannel.name,
          channelDescription: floodChannel.description,
          importance: Importance.max,
          priority: Priority.max,
          playSound: true,
          enableVibration: true,
          vibrationPattern: vibrationPattern,
          color: riskLevel == 'SEVERE'
              ? const Color(0xFFB71C1C)
              : riskLevel == 'HIGH'
                  ? const Color(0xFFE64A19)
                  : const Color(0xFFF57C00),
        ),
        iOS: const DarwinNotificationDetails(
          presentAlert: true,
          presentBadge: true,
          presentSound: true,
          interruptionLevel: InterruptionLevel.critical,
        ),
      ),
    );
    return true;
  }

  // ── Navigation flag ──────────────────────────────────────────────────────────

  Future<void> _flagNavigateToAlerts() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('navigate_to_alerts', true);
  }

  /// Returns true (and clears the flag) if the user tapped a flood notification
  /// and should be taken to the Alerts tab.
  static Future<bool> shouldNavigateToAlerts() async {
    final prefs = await SharedPreferences.getInstance();
    final flag = prefs.getBool('navigate_to_alerts') ?? false;
    if (flag) await prefs.remove('navigate_to_alerts');
    return flag;
  }
}
