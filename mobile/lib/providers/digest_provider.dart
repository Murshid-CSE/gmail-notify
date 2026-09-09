import 'package:flutter/foundation.dart';
import '../models/digest.dart';
import '../services/digest_service.dart';

/// CareerMail AI — Daily Digest Provider.
class DigestProvider with ChangeNotifier {
  final DigestService _service;

  DigestProvider({DigestService? service}) : _service = service ?? DigestService();

  DailyDigest? _digest;
  bool _isLoading = false;
  String? _errorMessage;

  DailyDigest? get digest => _digest;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  Future<void> fetchDigest({bool force = false}) async {
    if (_digest != null && !force) return;

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      _digest = await _service.getDailyDigest();
    } catch (e) {
      _errorMessage = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> refresh() => fetchDigest(force: true);
}
