import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:careermail/models/scheduler_status.dart';
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

class MockSchedulerApiClient extends ApiClient {
  bool getStatusCalled = false;
  bool triggerSyncCalled = false;
  bool triggerDigestCalled = false;
  bool pauseCalled = false;
  bool resumeCalled = false;
  bool shouldFail = false;

  @override
  Future<dynamic> get(String path, {Map<String, dynamic>? queryParams}) async {
    if (path == '/scheduler/status') {
      getStatusCalled = true;
      if (shouldFail) {
        throw ApiException('Failed to fetch status', 500);
      }
      return {
        'is_running': true,
        'is_paused': false,
        'scheduler_enabled': true,
        'sync_interval_minutes': 15,
        'daily_digest_time': '08:00',
        'timezone': 'Asia/Kolkata',
        'jobs': [
          {
            'id': 'periodic_sync',
            'name': 'Periodic Gmail Sync',
            'next_run_time': '2026-09-08T18:00:00Z',
            'is_paused': false,
            'trigger': 'interval[0:15:00]',
          },
          {
            'id': 'daily_digest',
            'name': 'Daily Career Brief',
            'next_run_time': '2026-09-09T08:00:00Z',
            'is_paused': false,
            'trigger': 'cron[hour=8, minute=0]',
          }
        ],
        'last_sync_success': true,
        'last_sync_result': {'accounts_succeeded': 2, 'emails_ingested': 5},
      };
    }
    if (path == '/accounts') {
      return {'accounts': []};
    }
    return super.get(path, queryParams: queryParams);
  }

  @override
  Future<dynamic> post(
    String path, {
    Map<String, dynamic>? body,
    Map<String, dynamic>? queryParams,
  }) async {
    if (path == '/scheduler/trigger/sync') {
      triggerSyncCalled = true;
      if (shouldFail) {
        throw ApiException('Sync trigger failed', 500);
      }
      return {
        'success': true,
        'message': 'Pipeline completed: 2/2 accounts synced, 5 emails ingested, 4 extracted, 1 alerts',
        'details': {
          'accounts_total': 2,
          'accounts_succeeded': 2,
          'accounts_failed': 0,
          'emails_ingested': 5,
          'emails_extracted': 4,
          'deadline_alerts_sent': 1,
          'success': true,
        },
      };
    }
    if (path == '/scheduler/trigger/digest') {
      triggerDigestCalled = true;
      if (shouldFail) {
        throw ApiException('Digest trigger failed', 500);
      }
      return {
        'success': true,
        'message': 'Daily digest triggered: status=mock_sent, notification_id=42',
        'details': {
          'user_id': queryParams?['user_id'] ?? 1,
          'status': 'mock_sent',
          'notification_id': 42,
        },
      };
    }
    if (path == '/scheduler/pause') {
      pauseCalled = true;
      return {'success': true, 'message': 'Paused', 'is_paused': true};
    }
    if (path == '/scheduler/resume') {
      resumeCalled = true;
      return {'success': true, 'message': 'Resumed', 'is_paused': false};
    }
    return super.post(path, body: body, queryParams: queryParams);
  }
}

void main() {
  group('Scheduler Model & Serialization Tests', () {
    test('SchedulerStatus.fromJson parses valid payload and provides helper getters', () {
      final json = {
        'is_running': true,
        'is_paused': false,
        'scheduler_enabled': true,
        'sync_interval_minutes': 15,
        'daily_digest_time': '08:00',
        'timezone': 'Asia/Kolkata',
        'jobs': [
          {
            'id': 'periodic_sync',
            'name': 'Periodic Gmail Sync',
            'next_run_time': '2026-09-08T18:00:00Z',
            'is_paused': false,
            'trigger': 'interval[0:15:00]',
          },
          {
            'id': 'daily_digest',
            'name': 'Daily Career Brief',
            'next_run_time': '2026-09-09T08:00:00Z',
            'is_paused': false,
            'trigger': 'cron[hour=8, minute=0]',
          }
        ],
        'last_sync_success': true,
        'last_sync_result': {'accounts_succeeded': 2},
      };

      final status = SchedulerStatus.fromJson(json);

      expect(status.isRunning, isTrue);
      expect(status.isPaused, isFalse);
      expect(status.schedulerEnabled, isTrue);
      expect(status.syncIntervalMinutes, 15);
      expect(status.dailyDigestTime, '08:00');
      expect(status.timezone, 'Asia/Kolkata');
      expect(status.jobs.length, 2);
      expect(status.syncJob?.id, 'periodic_sync');
      expect(status.syncJob?.name, 'Periodic Gmail Sync');
      expect(status.digestJob?.id, 'daily_digest');
      expect(status.lastSyncSuccess, isTrue);
    });

    test('SchedulerStatus.fromJson handles empty and missing fields safely', () {
      final status = SchedulerStatus.fromJson({});

      expect(status.isRunning, isFalse);
      expect(status.isPaused, isFalse);
      expect(status.schedulerEnabled, isFalse);
      expect(status.syncIntervalMinutes, 15);
      expect(status.dailyDigestTime, '08:00');
      expect(status.timezone, 'Asia/Kolkata');
      expect(status.jobs, isEmpty);
      expect(status.syncJob, isNull);
      expect(status.digestJob, isNull);
    });
  });

  group('SchedulerService & SchedulerProvider State Tests', () {
    test('SchedulerService executes getStatus, triggerSync, and triggerDigest', () async {
      final mockClient = MockSchedulerApiClient();
      final service = SchedulerService(client: mockClient);

      final status = await service.getStatus();
      expect(mockClient.getStatusCalled, isTrue);
      expect(status.isRunning, isTrue);

      final syncResp = await service.triggerSync();
      expect(mockClient.triggerSyncCalled, isTrue);
      expect(syncResp['success'], isTrue);

      final digestResp = await service.triggerDigest(userId: 1);
      expect(mockClient.triggerDigestCalled, isTrue);
      expect(digestResp['success'], isTrue);

      final pauseOk = await service.pauseScheduler();
      expect(mockClient.pauseCalled, isTrue);
      expect(pauseOk, isTrue);

      final resumeOk = await service.resumeScheduler();
      expect(mockClient.resumeCalled, isTrue);
      expect(resumeOk, isTrue);
    });

    test('SchedulerProvider manages loading state, success state, and error state', () async {
      final mockClient = MockSchedulerApiClient();
      final service = SchedulerService(client: mockClient);
      final provider = SchedulerProvider(service: service);

      expect(provider.status, isNull);
      expect(provider.isLoading, isFalse);
      expect(provider.isTriggeringSync, isFalse);
      expect(provider.isTriggeringDigest, isFalse);

      // 1. Success state: fetchStatus
      await provider.fetchStatus();
      expect(provider.status, isNotNull);
      expect(provider.status!.isRunning, isTrue);
      expect(provider.errorMessage, isNull);

      // 2. Success state: triggerPipelineNow
      final syncResult = await provider.triggerPipelineNow();
      expect(syncResult, isNotNull);
      expect(syncResult!['success'], isTrue);
      expect(provider.isTriggeringSync, isFalse);

      // 3. Success state: triggerDailyBriefNow
      final digestResult = await provider.triggerDailyBriefNow(userId: 1);
      expect(digestResult, isNotNull);
      expect(digestResult!['success'], isTrue);
      expect(provider.isTriggeringDigest, isFalse);

      // 4. Error state: network / server failure
      mockClient.shouldFail = true;
      final failResult = await provider.triggerPipelineNow();
      expect(failResult, isNull);
      expect(provider.errorMessage, isNotNull);
      expect(provider.errorMessage, contains('Sync trigger failed'));
    });
  });

  group('Settings Screen Automated Sync & Scheduling Card UI Tests', () {
    testWidgets('SettingsScreen renders scheduler details, Run Pipeline Now, and Trigger Daily Brief buttons',
        (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockClient = MockSchedulerApiClient();
      final schedulerService = SchedulerService(client: mockClient);
      final schedulerProvider = SchedulerProvider(service: schedulerService);

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<NotificationService>(create: (_) => NotificationService(apiClient: mockClient)),
            ChangeNotifierProvider(create: (_) => AccountsProvider(service: AccountService(client: mockClient))),
            ChangeNotifierProvider(create: (_) => DigestProvider(service: DigestService(client: mockClient))),
            ChangeNotifierProvider(create: (_) => OpportunitiesProvider(service: OpportunityService(client: mockClient))),
            ChangeNotifierProvider(create: (_) => DeadlinesProvider(service: DeadlineService(client: mockClient))),
            ChangeNotifierProvider<SchedulerProvider>.value(value: schedulerProvider),
          ],
          child: const MaterialApp(
            home: SettingsScreen(),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Verify Section Header
      expect(find.text('AUTOMATED SYNC & SCHEDULING'), findsOneWidget);

      // Verify Card text
      expect(find.text('Background Automation'), findsOneWidget);
      expect(find.text('Automatic Sync'), findsOneWidget);
      expect(find.text('Every 15 minutes'), findsOneWidget);
      expect(find.text('Daily Career Brief'), findsOneWidget);
      expect(find.text('08:00 AM'), findsOneWidget);
      expect(find.text('Timezone'), findsWidgets);
      expect(find.text('Asia/Kolkata'), findsWidgets);

      // Verify action buttons
      final runPipelineBtn = find.widgetWithText(FilledButton, 'Run Pipeline Now');
      expect(runPipelineBtn, findsOneWidget);

      final triggerBriefBtn = find.widgetWithText(OutlinedButton, 'Trigger Daily Brief');
      expect(triggerBriefBtn, findsOneWidget);

      // Tap Run Pipeline Now
      await tester.tap(runPipelineBtn);
      await tester.pumpAndSettle();

      expect(mockClient.triggerSyncCalled, isTrue);

      // Tap Trigger Daily Brief
      await tester.tap(triggerBriefBtn);
      await tester.pumpAndSettle();

      expect(mockClient.triggerDigestCalled, isTrue);
    });
  });
}
