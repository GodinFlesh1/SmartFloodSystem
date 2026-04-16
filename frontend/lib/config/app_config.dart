class AppConfig {
  /// Backend API base URL.
  /// Injected at build time via --dart-define-from-file=.env.json
  /// Dev:  flutter run --dart-define-from-file=.env.json
  /// Prod: flutter build apk --dart-define-from-file=.env.prod.json
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );
}
