import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:careermail/providers/accounts_provider.dart';

import 'package:careermail/providers/deadlines_provider.dart';
import 'package:careermail/providers/digest_provider.dart';
import 'package:careermail/providers/opportunities_provider.dart';
import 'package:careermail/providers/scheduler_provider.dart';
import 'package:careermail/screens/settings_screen.dart';
import 'package:careermail/services/account_service.dart';
import 'package:careermail/services/api_client.dart';
import 'package:careermail/services/deadline_service.dart';
import 'package:careermail/services/digest_service.dart';
import 'package:careermail/services/notification_service.dart';
import 'package:careermail/services/opportunity_service.dart';
import 'package:careermail/services/scheduler_service.dart';


class MockApiClient extends ApiClient {
  bool registerCalled = false;
  bool deleteCalled = false;
  bool testCalled = false;

  @override
  Future<dynamic> post(
    String path, {
    Map<String, dynamic>? body,
    Map<String, dynamic>? queryParams,
  }) async {
    if (path == '/devices/register') {
      registerCalled = true;
      return {
        'id': 1,
        'user_id': 1,
        'device_type': body?['device_type'] ?? 'android',
        'device_name': body?['device_name'] ?? 'Test Device',
        'is_active': true,
        'fcm_token_snippet': 'test-token...',
      };
    }
    if (path == '/notifications/test') {
      testCalled = true;
      return {
        'success': true,
        'status': 'mock_sent',
        'recipient_count': 1,
        'detail': 'Test notification triggered!',
      };
    }
    return super.post(path, body: body, queryParams: queryParams);
  }

  @override
  Future<dynamic> delete(
    String path, {
    Map<String, dynamic>? queryParams,
  }) async {
    if (path.startsWith('/devices/')) {
      deleteCalled = true;
      return {'message': 'Device token deactivated successfully.', 'deactivated': true};
    }
    return super.delete(path, queryParams: queryParams);
  }

  @override
  Future<dynamic> get(
    String path, {
    Map<String, dynamic>? queryParams,
  }) async {
    if (path == '/accounts') {
      return {'accounts': []};
    }
    if (path == '/scheduler/status') {
      return {
        'is_running': true,
        'is_paused': false,
        'scheduler_enabled': true,
        'sync_interval_minutes': 15,
        'daily_digest_time': '08:00',
        'timezone': 'Asia/Kolkata',
        'jobs': [],
      };
    }
    return super.get(path, queryParams: queryParams);
  }
}

void main() {
  group('Notification Model & Payload Parsing Tests', () {
    test('NotificationPayload parses valid opportunity payload', () {
      final raw = {
        'type': 'opportunity',
        'opportunity_id': '42',
        'email_id': '15',
      };
      final payload = NotificationPayload.fromData(raw);
      expect(payload.type, 'opportunity');
      expect(payload.opportunityId, 42);
      expect(payload.emailId, 15);
      expect(payload.isOpportunity, isTrue);
      expect(payload.isDigest, isFalse);
    });

    test('NotificationPayload parses integer IDs and digest payloads', () {
      final raw = {
        'type': 'digest',
        'date': '2026-09-08',
      };
      final payload = NotificationPayload.fromData(raw);
      expect(payload.type, 'digest');
      expect(payload.opportunityId, isNull);
      expect(payload.date, '2026-09-08');
      expect(payload.isOpportunity, isFalse);
      expect(payload.isDigest, isTrue);
    });

    test('NotificationPreferences handles copyWith and JSON roundtrip', () {
      const prefs = NotificationPreferences();
      expect(prefs.urgentActions, isTrue);
      expect(prefs.approachingDeadlines, isTrue);
      expect(prefs.statusUpdates, isTrue);
      expect(prefs.dailyBrief, isTrue);

      final updated = prefs.copyWith(urgentActions: false, dailyBrief: false);
      expect(updated.urgentActions, isFalse);
      expect(updated.approachingDeadlines, isTrue);
      expect(updated.dailyBrief, isFalse);

      final json = updated.toJson();
      final fromJson = NotificationPreferences.fromJson(json);
      expect(fromJson.urgentActions, isFalse);
      expect(fromJson.approachingDeadlines, isTrue);
    });
  });

  group('NotificationService Lifecycle & Navigation Stream Tests', () {
    late MockApiClient mockApi;
    late NotificationService service;

    setUp(() {
      mockApi = MockApiClient();
      service = NotificationService(apiClient: mockApi);
    });

    test('registerDevice updates registration status', () async {
      expect(service.status.isRegistered, isFalse);

      final success = await service.registerDevice(
        fcmToken: 'fcm-unit-test-token-12345',
        deviceType: 'android',
        deviceName: 'Pixel Unit Test',
      );

      expect(success, isTrue);
      expect(mockApi.registerCalled, isTrue);
      expect(service.status.isRegistered, isTrue);
      expect(service.status.fcmToken, 'fcm-unit-test-token-12345');
    });

    test('unregisterDevice deactivates registered device', () async {
      await service.registerDevice(
        fcmToken: 'fcm-token-to-unregister',
      );
      expect(service.status.isRegistered, isTrue);

      final success = await service.unregisterDevice();
      expect(success, isTrue);
      expect(mockApi.deleteCalled, isTrue);
      expect(service.status.isRegistered, isFalse);
    });

    test('sendTestNotification invokes backend endpoint', () async {
      final res = await service.sendTestNotification(
        title: 'Custom Title',
        body: 'Custom Body',
      );
      expect(mockApi.testCalled, isTrue);
      expect(res['status'], 'mock_sent');
    });

    test('handleNotificationTap broadcasts payload to onNotificationTapped stream', () async {
      final emittedPayloads = <NotificationPayload>[];
      final subscription = service.onNotificationTapped.listen((p) {
        emittedPayloads.add(p);
      });

      service.handleNotificationTap({
        'type': 'opportunity',
        'opportunity_id': '99',
      });

      // Allow stream microtask to fire
      await Future<void>.delayed(Duration.zero);

      expect(emittedPayloads.length, 1);
      expect(emittedPayloads.first.opportunityId, 99);
      expect(emittedPayloads.first.isOpportunity, isTrue);

      await subscription.cancel();
    });
  });

  group('Settings Screen Push Notification Section UI Tests', () {
    testWidgets('SettingsScreen renders Push Notifications card and toggles preferences',
        (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockApi = MockApiClient();
      final notifService = NotificationService(apiClient: mockApi);

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<NotificationService>.value(value: notifService),
            ChangeNotifierProvider(create: (_) => AccountsProvider(service: AccountService(client: mockApi))),
            ChangeNotifierProvider(create: (_) => DigestProvider(service: DigestService(client: mockApi))),
            ChangeNotifierProvider(create: (_) => OpportunitiesProvider(service: OpportunityService(client: mockApi))),
            ChangeNotifierProvider(create: (_) => DeadlinesProvider(service: DeadlineService(client: mockApi))),
            ChangeNotifierProvider(create: (_) => SchedulerProvider(service: SchedulerService(client: mockApi))),
          ],


          child: const MaterialApp(
            home: SettingsScreen(),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Verify Section Header
      expect(find.text('PUSH NOTIFICATIONS'), findsOneWidget);

      // Verify Status label
      expect(find.text('Status'), findsOneWidget);
      expect(find.text('Not Registered'), findsOneWidget);

      // Verify Send Test Notification button
      expect(find.text('Send Test Notification'), findsOneWidget);

      // Verify Category preference switches
      expect(find.text('Urgent Actions'), findsOneWidget);
      expect(find.text('Approaching Deadlines'), findsOneWidget);
      expect(find.text('Status Updates'), findsOneWidget);
      expect(find.text('Daily Brief'), findsOneWidget);

      // Tap Register button
      final registerBtn = find.widgetWithText(OutlinedButton, 'Register');
      expect(registerBtn, findsOneWidget);
      await tester.tap(registerBtn);
      await tester.pumpAndSettle();

      expect(mockApi.registerCalled, isTrue);
      expect(find.text('Registered with Backend'), findsOneWidget);

      // Tap Send Test Notification button
      final testBtn = find.widgetWithText(FilledButton, 'Send Test Notification');
      expect(testBtn, findsOneWidget);
      await tester.tap(testBtn);
      await tester.pumpAndSettle();

      expect(mockApi.testCalled, isTrue);
    });
  });
}
