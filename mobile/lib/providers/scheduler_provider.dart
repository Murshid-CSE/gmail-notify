import 'package:flutter/foundation.dart';
import '../models/scheduler_status.dart';
import '../services/scheduler_service.dart';

/// CareerMail AI — Scheduler State Management Provider.
class SchedulerProvider extends ChangeNotifier {
  final SchedulerService _service;

  SchedulerStatus? _status;
  bool _isLoading = false;
  bool _isTriggeringSync = false;
  bool _isTriggeringDigest = false;
  String? _errorMessage;

  SchedulerProvider({SchedulerService? service})
      : _service = service ?? SchedulerService();

  SchedulerStatus? get status => _status;
  bool get isLoading => _isLoading;
  bool get isTriggeringSync => _isTriggeringSync;
  bool get isTriggeringDigest => _isTriggeringDigest;
  String? get errorMessage => _errorMessage;

  Future<void> fetchStatus() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      _status = await _service.getStatus();
    } catch (e) {
      _errorMessage = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>?> triggerPipelineNow() async {
    _isTriggeringSync = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final res = await _service.triggerSync();
      await fetchStatus();
      return res;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return null;
    } finally {
      _isTriggeringSync = false;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>?> triggerDailyBriefNow({int userId = 1}) async {
    _isTriggeringDigest = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final res = await _service.triggerDigest(userId: userId);
      await fetchStatus();
      return res;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return null;
    } finally {
      _isTriggeringDigest = false;
      notifyListeners();
    }
  }
}
