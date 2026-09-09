import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/account.dart';
import '../services/account_service.dart';
import '../services/extraction_service.dart';
import '../services/opportunity_service.dart';
import '../services/deadline_service.dart';
import '../services/digest_service.dart';

enum OnboardingStep {
  welcome,
  selectAccountCount,
  connectAccounts,
  syncProgress,
  completed,
}

enum SyncProgressStage {
  idle,
  gmailConnected,
  accountSecured,
  readingEmails,
  findingOpportunities,
  detectingDeadlines,
  organizingInbox,
  dashboardReady,
  failed,
}

/// CareerMail AI — Onboarding & Automated Initial Sync State Management.
class OnboardingProvider with ChangeNotifier {
  final AccountService _accountService;
  final ExtractionService _extractionService;
  final OpportunityService _opportunityService;
  final DeadlineService _deadlineService;
  final DigestService _digestService;

  OnboardingProvider({
    AccountService? accountService,
    ExtractionService? extractionService,
    OpportunityService? opportunityService,
    DeadlineService? deadlineService,
    DigestService? digestService,
  })  : _accountService = accountService ?? AccountService(),
        _extractionService = extractionService ?? ExtractionService(),
        _opportunityService = opportunityService ?? OpportunityService(),
        _deadlineService = deadlineService ?? DeadlineService(),
        _digestService = digestService ?? DigestService();

  OnboardingStep _currentStep = OnboardingStep.welcome;
  int _targetAccountCount = 1; // 1 or 2
  List<EmailAccount> _connectedAccounts = [];
  bool _isConnecting = false;
  bool _isPolling = false;
  Timer? _pollingTimer;

  SyncProgressStage _syncStage = SyncProgressStage.idle;
  String _statusMessage = '';
  double _progressPercentage = 0.0;
  String? _errorMessage;

  // Summary metrics once initial sync and extraction completes
  int _totalEmailsIngested = 0;
  int _opportunitiesFound = 0;
  int _deadlinesFound = 0;
  int _urgentActionsFound = 0;

  // Getters
  OnboardingStep get currentStep => _currentStep;
  int get targetAccountCount => _targetAccountCount;
  List<EmailAccount> get connectedAccounts => _connectedAccounts;
  bool get isConnecting => _isConnecting;
  bool get isPolling => _isPolling;
  SyncProgressStage get syncStage => _syncStage;
  String get statusMessage => _statusMessage;
  double get progressPercentage => _progressPercentage;
  String? get errorMessage => _errorMessage;

  int get totalEmailsIngested => _totalEmailsIngested;
  int get opportunitiesFound => _opportunitiesFound;
  int get deadlinesFound => _deadlinesFound;
  int get urgentActionsFound => _urgentActionsFound;

  bool get hasRequiredAccounts => _connectedAccounts.length >= _targetAccountCount;

  @override
  void dispose() {
    _pollingTimer?.cancel();
    super.dispose();
  }

  // ── Step Navigation ────────────────────────────────────────────────────────

  void setStep(OnboardingStep step) {
    _currentStep = step;
    _errorMessage = null;
    notifyListeners();
  }

  void goToAccountSelection() {
    setStep(OnboardingStep.selectAccountCount);
  }

  void setTargetAccountCount(int count) {
    if (count == 1 || count == 2) {
      _targetAccountCount = count;
      notifyListeners();
    }
  }

  void confirmAccountSelection() {
    setStep(OnboardingStep.connectAccounts);
    // Initial fetch to see if any accounts are already connected
    refreshConnectedAccounts();
  }

  // ── Account Polling & OAuth Connection ──────────────────────────────────────

  Future<void> refreshConnectedAccounts() async {
    try {
      final accounts = await _accountService.getAccounts();
      _connectedAccounts = accounts;
      notifyListeners();
    } catch (_) {
      // Non-fatal if server is unreachable temporarily
    }
  }

  /// Launch Google OAuth in system browser and begin polling for the callback.
  Future<bool> startOAuthConnection() async {
    _isConnecting = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final authUrl = await _accountService.getOAuthStartUrl();
      final uri = Uri.parse(authUrl);

      final launched = await launchUrl(
        uri,
        mode: LaunchMode.externalApplication,
      );

      if (!launched) {
        _errorMessage = 'Could not launch web browser for Google sign-in.';
        _isConnecting = false;
        notifyListeners();
        return false;
      }

      // Begin polling backend every 2 seconds for account presence
      startPolling();
      return true;
    } catch (e) {
      _errorMessage = 'Failed to start Google connection: $e';
      _isConnecting = false;
      notifyListeners();
      return false;
    }
  }

  void startPolling() {
    _pollingTimer?.cancel();
    _isPolling = true;
    notifyListeners();

    final initialCount = _connectedAccounts.length;

    _pollingTimer = Timer.periodic(const Duration(seconds: 2), (timer) async {
      try {
        final accounts = await _accountService.getAccounts();
        _connectedAccounts = accounts;
        notifyListeners();

        if (accounts.length > initialCount) {
          // A new account was successfully connected!
          _isConnecting = false;
          notifyListeners();

          if (accounts.length >= _targetAccountCount) {
            // Target satisfied! Stop polling and advance to sync progress
            stopPolling();
            startInitialSyncPipeline();
          }
        }
      } catch (e) {
        // Polling errors are ignored until timeout or manual cancel
      }
    });
  }

  void stopPolling() {
    _pollingTimer?.cancel();
    _pollingTimer = null;
    _isPolling = false;
    _isConnecting = false;
    notifyListeners();
  }

  // ── Automated Initial Sync & Extraction Pipeline ────────────────────────────

  Future<void> startInitialSyncPipeline() async {
    setStep(OnboardingStep.syncProgress);
    _syncStage = SyncProgressStage.gmailConnected;
    _statusMessage = 'Gmail connected securely';
    _progressPercentage = 0.15;
    _errorMessage = null;
    notifyListeners();

    try {
      // Stage 1: Account secured
      await Future.delayed(const Duration(milliseconds: 600));
      _syncStage = SyncProgressStage.accountSecured;
      _statusMessage = 'Encryption established for OAuth tokens';
      _progressPercentage = 0.30;
      notifyListeners();

      // Stage 2: Ingesting emails via /accounts/{id}/sync
      await Future.delayed(const Duration(milliseconds: 400));
      _syncStage = SyncProgressStage.readingEmails;
      _statusMessage = 'Reading recent emails from connected inbox...';
      _progressPercentage = 0.45;
      notifyListeners();

      int totalSynced = 0;
      for (final account in _connectedAccounts) {
        final syncRes = await _accountService.syncAccount(account.id);
        final newMsgs = syncRes['new_messages'] as int? ?? 0;
        final totalInDb = syncRes['total_messages_in_db'] as int? ?? newMsgs;
        totalSynced += totalInDb;
      }
      _totalEmailsIngested = totalSynced;

      // Stage 3: AI Extraction via /extraction/process
      _syncStage = SyncProgressStage.findingOpportunities;
      _statusMessage = 'Analyzing emails with Gemini 2.5 Flash...';
      _progressPercentage = 0.70;
      notifyListeners();

      await _extractionService.triggerProcess(limit: 50);

      // Stage 4: Detecting Deadlines & Organizing
      _syncStage = SyncProgressStage.detectingDeadlines;
      _statusMessage = 'Detecting deadlines and organizing career inbox...';
      _progressPercentage = 0.88;
      notifyListeners();

      // Fetch summary counts for the ready card
      try {
        final oppsRes = await _opportunityService.getOpportunities(pageSize: 1);
        _opportunitiesFound = oppsRes.pagination.totalItems;
      } catch (_) {
        _opportunitiesFound = 0;
      }

      try {
        final deadlines = await _deadlineService.getDeadlines();
        _deadlinesFound = deadlines.totalActive;
      } catch (_) {
        _deadlinesFound = 0;
      }

      try {
        final digest = await _digestService.getDailyDigest();
        _urgentActionsFound = digest.counts.urgentActions;
      } catch (_) {
        _urgentActionsFound = 0;
      }

      // Stage 5: Ready
      _syncStage = SyncProgressStage.dashboardReady;
      _statusMessage = 'Your Career Dashboard is ready!';
      _progressPercentage = 1.0;
      notifyListeners();
    } catch (e) {
      _syncStage = SyncProgressStage.failed;
      _errorMessage = 'Setup encountered an issue: $e';
      notifyListeners();
    }
  }

  /// Retry the initial sync pipeline in case of error
  void retrySync() {
    startInitialSyncPipeline();
  }

  /// Mark onboarding as fully completed and advance to dashboard
  void completeOnboarding() {
    setStep(OnboardingStep.completed);
  }
}
