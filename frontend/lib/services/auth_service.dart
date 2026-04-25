import 'dart:math';
import 'dart:io' show Platform;
import 'package:device_info_plus/device_info_plus.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:google_sign_in/google_sign_in.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AuthService {
  static const String _tokenKey = 'firebase_id_token';
  static const String _deviceKey = 'device_id';

  final FirebaseAuth _auth = FirebaseAuth.instance;
  final GoogleSignIn _googleSignIn = GoogleSignIn(
    clientId: const String.fromEnvironment('GOOGLE_WEB_CLIENT_ID'),
  );

  Stream<User?> get authStateChanges => _auth.authStateChanges();

  User? get currentUser => _auth.currentUser;

  /// Returns a fresh ID token and caches it for background isolates.
  /// Waits up to 5 seconds for auth state to restore on cold page load.
  Future<String?> getIdToken() async {
    User? user = _auth.currentUser;
    if (user == null) {
      user = await _auth
          .authStateChanges()
          .firstWhere((u) => u != null, orElse: () => null)
          .timeout(const Duration(seconds: 5), onTimeout: () => null);
    }
    final token = await user?.getIdToken();
    if (token != null) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_tokenKey, token);
    }
    return token;
  }

  /// Reads the last saved token from SharedPreferences.
  /// Use this in background isolates instead of getIdToken().
  static Future<String?> getStoredToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_tokenKey);
  }

  /// Signs in with Google and returns the Firebase User.
  Future<User?> signInWithGoogle() async {
    final googleUser = await _googleSignIn.signIn();
    if (googleUser == null) return null; // user cancelled

    final googleAuth = await googleUser.authentication;
    final credential = GoogleAuthProvider.credential(
      accessToken: googleAuth.accessToken,
      idToken: googleAuth.idToken,
    );
    final result = await _auth.signInWithCredential(credential);
    return result.user;
  }

  /// Returns a stable device ID, generating and persisting one on first call.
  static Future<String> getDeviceId() async {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString(_deviceKey);
    if (stored != null) return stored;

    String deviceId;
    if (kIsWeb) {
      deviceId = _generateId();
    } else if (Platform.isAndroid) {
      final info = await DeviceInfoPlugin().androidInfo;
      deviceId = info.id;
    } else if (Platform.isIOS) {
      final info = await DeviceInfoPlugin().iosInfo;
      deviceId = info.identifierForVendor ?? _generateId();
    } else {
      deviceId = _generateId();
    }

    await prefs.setString(_deviceKey, deviceId);
    return deviceId;
  }

  static String _generateId() {
    final random = Random.secure();
    return List.generate(32, (_) => random.nextInt(16).toRadixString(16)).join();
  }

  Future<void> signOut() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    await _googleSignIn.signOut();
    await _auth.signOut();
  }
}
