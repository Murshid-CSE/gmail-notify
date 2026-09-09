import 'package:flutter/foundation.dart';

/// CareerMail AI — API Configuration & Base URL Management.
///
/// Automatically determines the appropriate default URL for Android emulator
/// (`http://10.0.2.2:8000`), Chrome/Desktop (`http://localhost:8000`), or
/// physical devices, while supporting custom user overrides in Settings.
class ApiConfig with ChangeNotifier {
  static final ApiConfig _instance = ApiConfig._internal();
  factory ApiConfig() => _instance;

  ApiConfig._internal() {
    _baseUrl = _resolveDefaultBaseUrl();
  }

  late String _baseUrl;
  String _userTimezone = 'Asia/Kolkata';

  String get baseUrl => _baseUrl;
  String get userTimezone => _userTimezone;

  static String _resolveDefaultBaseUrl() {
    if (kIsWeb) {
      return 'http://localhost:8000';
    }
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        // Android emulator maps host localhost to 10.0.2.2
        return 'http://10.0.2.2:8000';
      case TargetPlatform.iOS:
      case TargetPlatform.macOS:
      case TargetPlatform.windows:
      case TargetPlatform.linux:
      default:
        return 'http://localhost:8000';
    }
  }

  void setBaseUrl(String newUrl) {
    String cleaned = newUrl.trim();
    if (cleaned.endsWith('/')) {
      cleaned = cleaned.substring(0, cleaned.length - 1);
    }
    if (cleaned.isNotEmpty && cleaned != _baseUrl) {
      _baseUrl = cleaned;
      notifyListeners();
    }
  }

  void setUserTimezone(String tz) {
    if (tz.trim().isNotEmpty && tz != _userTimezone) {
      _userTimezone = tz.trim();
      notifyListeners();
    }
  }

  void resetToDefault() {
    _baseUrl = _resolveDefaultBaseUrl();
    _userTimezone = 'Asia/Kolkata';
    notifyListeners();
  }
}
