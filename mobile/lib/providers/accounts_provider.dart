import 'package:flutter/foundation.dart';
import '../models/account.dart';
import '../services/account_service.dart';

/// CareerMail AI — Accounts & Sync Provider.
class AccountsProvider with ChangeNotifier {
  final AccountService _service;

  AccountsProvider({AccountService? service}) : _service = service ?? AccountService();

  List<EmailAccount> _accounts = [];
  bool _isLoading = false;
  bool _hasFetched = false;
  bool _isSyncing = false;
  String? _errorMessage;
  String? _syncStatusMessage;

  List<EmailAccount> get accounts => _accounts;
  bool get isLoading => _isLoading;
  bool get hasFetched => _hasFetched;
  bool get isSyncing => _isSyncing;
  String? get errorMessage => _errorMessage;
  String? get syncStatusMessage => _syncStatusMessage;

  Future<void> fetchAccounts() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      _accounts = await _service.getAccounts();
    } catch (e) {
      _errorMessage = e.toString();
    } finally {
      _isLoading = false;
      _hasFetched = true;
      notifyListeners();
    }
  }

  Future<bool> syncAccount(int id) async {
    _isSyncing = true;
    _syncStatusMessage = null;
    notifyListeners();

    try {
      final res = await _service.syncAccount(id);
      _syncStatusMessage = res['message']?.toString() ?? 'Account synced successfully.';
      await fetchAccounts();
      return true;
    } catch (e) {
      _errorMessage = 'Sync failed: $e';
      return false;
    } finally {
      _isSyncing = false;
      notifyListeners();
    }
  }

  Future<void> syncAll() async {
    if (_accounts.isEmpty) {
      await fetchAccounts();
    }
    for (final acc in _accounts) {
      await syncAccount(acc.id);
    }
  }
}
