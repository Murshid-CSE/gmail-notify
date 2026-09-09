import 'dart:async';
import 'package:flutter/foundation.dart';
import 'api_client.dart';

/// Notification payload received from FCM.
class NotificationPayload {
  final String type;
  final int? opportunityId;
  final int? emailId;
  final String? date;
  final Map<String, dynamic> rawData;

  NotificationPayload({
    required this.type,
    this.opportunityId,
    this.emailId,
    this.date,
    this.rawData = const {},
  });

  factory NotificationPayload.fromData(Map<String, dynamic> data) {
    int? parsedOppId;
    if (data.containsKey('opportunity_id') && data['opportunity_id'] != null) {
      parsedOppId = int.tryParse(data['opportunity_id'].toString());
    }

    int? parsedEmailId;
    if (data.containsKey('email_id') && data['email_id'] != null) {
      parsedEmailId = int.tryParse(data['email_id'].toString());
    }

    return NotificationPayload(
      type: data['type']?.toString() ?? 'general',
      opportunityId: parsedOppId,
      emailId: parsedEmailId,
      date: data['date']?.toString(),
      rawData: data,
    );
  }

  bool get isOpportunity => type == 'opportunity' && opportunityId != null;
  bool get isDigest => type == 'digest';
}

/// User's local push notification notification category preferences.
class NotificationPreferences {
  final bool urgentActions;
  final bool approachingDeadlines;
  final bool statusUpdates;
  final bool dailyBrief;

  const NotificationPreferences({
    this.urgentActions = true,
    this.approachingDeadlines = true,
    this.statusUpdates = true,
    this.dailyBrief = true,
  });

  NotificationPreferences copyWith({
    bool? urgentActions,
    bool? approachingDeadlines,
    bool? statusUpdates,
    bool? dailyBrief,
  }) {
    return NotificationPreferences(
      urgentActions: urgentActions ?? this.urgentActions,
      approachingDeadlines: approachingDeadlines ?? this.approachingDeadlines,
      statusUpdates: statusUpdates ?? this.statusUpdates,
      dailyBrief: dailyBrief ?? this.dailyBrief,
    );
  }

  Map<String, dynamic> toJson() => {
        'urgent_actions': urgentActions,
        'approaching_deadlines': approachingDeadlines,
        'status_updates': statusUpdates,
        'daily_brief': dailyBrief,
      };

  factory NotificationPreferences.fromJson(Map<String, dynamic> json) {
    return NotificationPreferences(
      urgentActions: json['urgent_actions'] as bool? ?? true,
      approachingDeadlines: json['approaching_deadlines'] as bool? ?? true,
      statusUpdates: json['status_updates'] as bool? ?? true,
      dailyBrief: json['daily_brief'] as bool? ?? true,
    );
  }
}

/// Status of device registration with CareerMail AI backend.
class NotificationRegistrationStatus {
  final bool isRegistered;
  final String? fcmToken;
  final String deviceType;
  final bool permissionGranted;
  final String? errorMessage;

  const NotificationRegistrationStatus({
    this.isRegistered = false,
    this.fcmToken,
    this.deviceType = 'android',
    this.permissionGranted = false,
    this.errorMessage,
  });

  NotificationRegistrationStatus copyWith({
    bool? isRegistered,
    String? fcmToken,
    String? deviceType,
    bool? permissionGranted,
    String? errorMessage,
  }) {
    return NotificationRegistrationStatus(
      isRegistered: isRegistered ?? this.isRegistered,
      fcmToken: fcmToken ?? this.fcmToken,
      deviceType: deviceType ?? this.deviceType,
      permissionGranted: permissionGranted ?? this.permissionGranted,
      errorMessage: errorMessage ?? this.errorMessage,
    );
  }
}

/// CareerMail AI — Push Notification Service.
///
/// Handles:
///   • Permission requests
///   • Token registration and deactivation with backend
///   • Payload parsing and notification tap routing
///   • Local preference toggles
///   • On-demand test push triggers
class NotificationService extends ChangeNotifier {
  final ApiClient _apiClient;
  NotificationRegistrationStatus _status = const NotificationRegistrationStatus();
  NotificationPreferences _preferences = const NotificationPreferences();

  final StreamController<NotificationPayload> _tapStreamController =
      StreamController<NotificationPayload>.broadcast();

  NotificationService({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  NotificationRegistrationStatus get status => _status;
  NotificationPreferences get preferences => _preferences;
  Stream<NotificationPayload> get onNotificationTapped =>
      _tapStreamController.stream;

  /// Initialize service and verify backend connectivity.
  Future<void> initialize() async {
    // In production, flutter_local_notifications / firebase_messaging
    // initializes here. Default to permission granted in mock/dry-run mode.
    _status = _status.copyWith(permissionGranted: true);
    notifyListeners();
  }

  /// Request notification permission from the OS.
  Future<bool> requestPermissions() async {
    // Graceful permission handling: don't break app if denied.
    _status = _status.copyWith(permissionGranted: true);
    notifyListeners();
    return true;
  }

  /// Register an FCM token with the CareerMail AI backend.
  Future<bool> registerDevice({
    required String fcmToken,
    String deviceType = 'android',
    String? deviceName,
  }) async {
    try {
      await _apiClient.post(
        '/devices/register',
        body: {
          'fcm_token': fcmToken,
          'device_type': deviceType,
          'device_name': deviceName ?? 'Mobile Client',
        },
      );

      _status = _status.copyWith(
        isRegistered: true,
        fcmToken: fcmToken,
        deviceType: deviceType,
        errorMessage: null,
      );
      notifyListeners();
      return true;
    } catch (e) {
      _status = _status.copyWith(
        errorMessage: e.toString(),
      );
      notifyListeners();
      return false;
    }
  }

  /// Deactivate current registered token on backend.
  Future<bool> unregisterDevice() async {
    final token = _status.fcmToken;
    if (token == null || !_status.isRegistered) {
      return true;
    }

    try {
      await _apiClient.delete('/devices/$token');
      _status = _status.copyWith(
        isRegistered: false,
        errorMessage: null,
      );
      notifyListeners();
      return true;
    } catch (e) {
      _status = _status.copyWith(
        errorMessage: e.toString(),
      );
      notifyListeners();
      return false;
    }
  }

  /// Dispatch an on-demand test notification via backend.
  Future<Map<String, dynamic>> sendTestNotification({
    String? title,
    String? body,
    int? opportunityId,
  }) async {
    try {
      final Map<String, dynamic> payload = {};
      if (title != null) payload['title'] = title;
      if (body != null) payload['body'] = body;
      if (opportunityId != null) payload['opportunity_id'] = opportunityId;

      final response = await _apiClient.post(
        '/notifications/test',
        body: payload,
      );
      return response is Map<String, dynamic>
          ? response
          : {'status': 'mock_sent', 'detail': 'Test sent successfully'};
    } catch (e) {
      rethrow;
    }
  }


  /// Invoked when a user taps a push notification banner.
  void handleNotificationTap(Map<String, dynamic> rawPayload) {
    final payload = NotificationPayload.fromData(rawPayload);
    _tapStreamController.add(payload);
  }

  /// Update local category preference settings.
  void updatePreferences(NotificationPreferences newPreferences) {
    _preferences = newPreferences;
    notifyListeners();
  }

  @override
  void dispose() {
    _tapStreamController.close();
    super.dispose();
  }
}
