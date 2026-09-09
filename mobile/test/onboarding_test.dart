import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:careermail/models/account.dart';
import 'package:careermail/models/deadline.dart';
import 'package:careermail/models/digest.dart';
import 'package:careermail/models/opportunity.dart';
import 'package:careermail/providers/accounts_provider.dart';
import 'package:careermail/providers/deadlines_provider.dart';
import 'package:careermail/providers/digest_provider.dart';
import 'package:careermail/providers/onboarding_provider.dart';
import 'package:careermail/providers/opportunities_provider.dart';
import 'package:careermail/providers/scheduler_provider.dart';
import 'package:careermail/screens/onboarding_screen.dart';
import 'package:careermail/screens/main_navigation_screen.dart';
import 'package:careermail/services/account_service.dart';
import 'package:careermail/services/api_client.dart';
import 'package:careermail/services/deadline_service.dart';
import 'package:careermail/services/digest_service.dart';
import 'package:careermail/services/extraction_service.dart';
import 'package:careermail/services/opportunity_service.dart';
import 'package:careermail/services/notification_service.dart';
import 'package:careermail/main.dart';

// ── Mock Services ────────────────────────────────────────────────────────────

class MockAccountService extends AccountService {
  List<EmailAccount> accountsToReturn;
  String authUrlToReturn;
  bool shouldThrow;

  MockAccountService({
    this.accountsToReturn = const [],
    this.authUrlToReturn = 'https://accounts.google.com/o/oauth2/auth?test=1',
    this.shouldThrow = false,
  });

  @override
  Future<List<EmailAccount>> getAccounts() async {
    if (shouldThrow) throw Exception('Backend unreachable');
    return accountsToReturn;
  }

  @override
  Future<String> getOAuthStartUrl() async {
    if (shouldThrow) throw Exception('OAuth endpoint failed');
    return authUrlToReturn;
  }

  @override
  Future<Map<String, dynamic>> syncAccount(int id) async {
    return {
      'account_id': id,
      'new_messages': 10,
      'total_messages_in_db': 10,
      'message': 'Synced 10 new messages.',
    };
  }
}

class MockExtractionService extends ExtractionService {
  bool processCalled = false;
  bool shouldFail = false;

  @override
  Future<Map<String, dynamic>> triggerProcess({int limit = 50}) async {
    if (shouldFail) throw Exception('AI extraction failure');
    processCalled = true;
    return {
      'total': 10,
      'extracted': 3,
      'filtered_out': 7,
    };
  }

  @override
  Future<Map<String, dynamic>> getStatus() async {
    return {
      'gemini_configured': true,
      'total_emails': 10,
    };
  }
}

class MockOpportunityService extends OpportunityService {
  @override
  Future<PaginatedOpportunities> getOpportunities({
    int page = 1,
    int pageSize = 20,
    String? category,
    String? status,
    String? priority,
    String? search,
    String? sortBy,
    String? sortOrder,
  }) async {
    return PaginatedOpportunities(
      items: [],
      pagination: PaginationMeta(
        page: 1,
        pageSize: 20,
        totalItems: 8,
        totalPages: 1,
        hasNext: false,
        hasPrevious: false,
      ),
    );
  }
}

class MockDeadlineService extends DeadlineService {
  @override
  Future<DeadlinesGrouped> getDeadlines({String? category, String? tz}) async {
    return DeadlinesGrouped(
      overdue: [],
      today: [],
      tomorrow: [],
      thisWeek: [],
      later: [],
      noDeadline: [],
      totalActive: 5,
    );
  }
}

class MockDigestService extends DigestService {
  @override
  Future<DailyDigest> getDailyDigest({String? date, String? tz}) async {
    return DailyDigest(
      generatedAt: DateTime.now(),
      targetDate: '2026-09-08',
      timezone: 'UTC',
      summary: 'Digest summary',
      counts: DigestCounts(
        newOpportunities: 8,
        deadlinesToday: 5,
        urgentActions: 3,
        statusChanges: 2,
      ),
      urgentActions: [],
      recentStatusChanges: [],
      upcomingDeadlines: [],
      newOpportunities: [],
    );
  }
}

// ── Test Helpers ─────────────────────────────────────────────────────────────

Widget createOnboardingTestWidget({required OnboardingProvider onboardingProvider}) {
  return MultiProvider(
    providers: [
      ChangeNotifierProvider.value(value: onboardingProvider),
      ChangeNotifierProvider(create: (_) => NotificationService()),
      ChangeNotifierProvider(create: (_) => DigestProvider()),
      ChangeNotifierProvider(create: (_) => OpportunitiesProvider()),
      ChangeNotifierProvider(create: (_) => DeadlinesProvider()),
      ChangeNotifierProvider(create: (_) => AccountsProvider()),
      ChangeNotifierProvider(create: (_) => SchedulerProvider()),
    ],
    child: const MaterialApp(
      home: OnboardingScreen(),
    ),
  );
}

void main() {
  group('AccountService API Parsing & Handling', () {
    test('getAccounts parses wrapped Map {"accounts": [...], "total": 1}', () async {
      final mockClient = MockApiClient({
        'accounts': [
          {
            'id': 1,
            'email_address': 'test@gmail.com',
            'provider': 'gmail',
            'is_active': true,
            'created_at': '2026-09-08T12:00:00',
          }
        ],
        'total': 1,
      });

      final service = AccountService(client: mockClient);
      final accounts = await service.getAccounts();
      expect(accounts.length, 1);
      expect(accounts[0].emailAddress, 'test@gmail.com');
      expect(accounts[0].id, 1);
    });

    test('getAccounts parses raw List format as well', () async {
      final mockClient = MockApiClient([
        {
          'id': 2,
          'email_address': 'second@gmail.com',
          'provider': 'gmail',
          'is_active': true,
          'created_at': '2026-09-08T12:00:00',
        }
      ]);

      final service = AccountService(client: mockClient);
      final accounts = await service.getAccounts();
      expect(accounts.length, 1);
      expect(accounts[0].emailAddress, 'second@gmail.com');
    });

    test('getAccounts throws ParseException on malformed response', () async {
      final mockClient = MockApiClient('invalid response string');
      final service = AccountService(client: mockClient);
      expect(() => service.getAccounts(), throwsA(isA<ParseException>()));
    });

    test('getOAuthStartUrl extracts authorization_url', () async {
      final mockClient = MockApiClient({
        'authorization_url': 'https://accounts.google.com/o/oauth2/auth?test=yes',
        'message': 'Open URL',
      });

      final service = AccountService(client: mockClient);
      final url = await service.getOAuthStartUrl();
      expect(url, 'https://accounts.google.com/o/oauth2/auth?test=yes');
    });
  });

  group('OnboardingProvider State & Pipeline Unit Tests', () {
    late MockAccountService mockAccountService;
    late MockExtractionService mockExtractionService;
    late OnboardingProvider provider;

    setUp(() {
      mockAccountService = MockAccountService();
      mockExtractionService = MockExtractionService();
      provider = OnboardingProvider(
        accountService: mockAccountService,
        extractionService: mockExtractionService,
        opportunityService: MockOpportunityService(),
        deadlineService: MockDeadlineService(),
        digestService: MockDigestService(),
      );
    });

    test('initial state is Welcome step with targetAccountCount = 1', () {
      expect(provider.currentStep, OnboardingStep.welcome);
      expect(provider.targetAccountCount, 1);
      expect(provider.connectedAccounts, isEmpty);
      expect(provider.hasRequiredAccounts, isFalse);
    });

    test('step navigation and account-count selection works', () {
      provider.goToAccountSelection();
      expect(provider.currentStep, OnboardingStep.selectAccountCount);

      provider.setTargetAccountCount(2);
      expect(provider.targetAccountCount, 2);

      provider.setTargetAccountCount(1);
      expect(provider.targetAccountCount, 1);

      provider.confirmAccountSelection();
      expect(provider.currentStep, OnboardingStep.connectAccounts);
    });

    test('initial sync pipeline executes all stages and populates summary', () async {
      final testAccount = EmailAccount(
        id: 1,
        emailAddress: 'test@gmail.com',
        provider: 'gmail',
        isActive: true,
        createdAt: DateTime.now(),
      );
      mockAccountService.accountsToReturn = [testAccount];
      await provider.refreshConnectedAccounts();

      await provider.startInitialSyncPipeline();

      expect(provider.currentStep, OnboardingStep.syncProgress);
      expect(provider.syncStage, SyncProgressStage.dashboardReady);
      expect(provider.progressPercentage, 1.0);
      expect(provider.opportunitiesFound, 8);
      expect(provider.deadlinesFound, 5);
      expect(provider.urgentActionsFound, 3);
      expect(provider.totalEmailsIngested, 10);
      expect(mockExtractionService.processCalled, isTrue);
    });

    test('error state and retry pipeline works', () async {
      mockExtractionService.shouldFail = true;

      await provider.startInitialSyncPipeline();

      expect(provider.syncStage, SyncProgressStage.failed);
      expect(provider.errorMessage, isNotNull);

      // Reset failure and retry
      mockExtractionService.shouldFail = false;
      await provider.startInitialSyncPipeline();
      expect(provider.syncStage, SyncProgressStage.dashboardReady);
    });
  });

  group('Onboarding UI & Widget Navigation Tests', () {
    testWidgets('renders Welcome screen and navigates to Account Selection', (tester) async {
      final provider = OnboardingProvider(
        accountService: MockAccountService(),
        extractionService: MockExtractionService(),
      );

      await tester.pumpWidget(createOnboardingTestWidget(onboardingProvider: provider));
      await tester.pumpAndSettle();

      expect(find.text('CareerMail AI'), findsOneWidget);
      expect(find.text('Your career inbox,\norganized automatically.'), findsOneWidget);
      expect(find.byKey(const Key('getStartedButton')), findsOneWidget);

      await tester.tap(find.byKey(const Key('getStartedButton')));
      await tester.pumpAndSettle();

      expect(find.text('Connect your Gmail'), findsOneWidget);
      expect(find.byKey(const Key('accountOption1')), findsOneWidget);
      expect(find.byKey(const Key('accountOption2')), findsOneWidget);
    });

    testWidgets('allows selecting 2 accounts and displays 2 connection slots', (tester) async {
      final provider = OnboardingProvider(
        accountService: MockAccountService(),
        extractionService: MockExtractionService(),
      );

      await tester.pumpWidget(createOnboardingTestWidget(onboardingProvider: provider));
      await tester.pumpAndSettle();

      // Go to account selection
      await tester.tap(find.byKey(const Key('getStartedButton')));
      await tester.pumpAndSettle();

      // Select 2 Accounts
      await tester.tap(find.byKey(const Key('accountOption2')));
      await tester.pumpAndSettle();
      expect(provider.targetAccountCount, 2);

      // Continue to Connect Accounts
      await tester.tap(find.byKey(const Key('confirmCountButton')));
      await tester.pumpAndSettle();

      expect(find.text('Gmail Account 1'), findsOneWidget);
      expect(find.text('Gmail Account 2'), findsOneWidget);
    });

    testWidgets('displays Sync Progress checklist and Open Dashboard CTA when ready', (tester) async {
      final provider = OnboardingProvider(
        accountService: MockAccountService(),
        extractionService: MockExtractionService(),
        opportunityService: MockOpportunityService(),
        deadlineService: MockDeadlineService(),
        digestService: MockDigestService(),
      );

      final testAccount = EmailAccount(
        id: 1,
        emailAddress: 'murshid@gmail.com',
        provider: 'gmail',
        isActive: true,
        createdAt: DateTime.now(),
      );
      provider.connectedAccounts.add(testAccount);

      await tester.pumpWidget(createOnboardingTestWidget(onboardingProvider: provider));
      await tester.pumpAndSettle();

      // Trigger sync
      final pipelineFuture = provider.startInitialSyncPipeline();
      await tester.pump(const Duration(milliseconds: 700));
      await tester.pump(const Duration(milliseconds: 500));
      await pipelineFuture;
      await tester.pumpAndSettle();

      expect(find.text('Setup Complete!'), findsOneWidget);
      expect(find.text('Gmail Account Connected'), findsOneWidget);
      expect(find.text('Analyzing Opportunities with Gemini'), findsOneWidget);
      expect(find.text('Opportunities'), findsOneWidget);
      expect(find.text('8'), findsOneWidget);
      expect(find.byKey(const Key('openDashboardButton')), findsOneWidget);
    });
  });

  group('AppEntryScreen Routing Tests', () {
    testWidgets('routes to Onboarding when 0 accounts are connected', (tester) async {
      final mockAccountService = MockAccountService(accountsToReturn: []);
      final accountsProvider = AccountsProvider(service: mockAccountService);
      final onboardingProvider = OnboardingProvider(
        accountService: mockAccountService,
        extractionService: MockExtractionService(),
        opportunityService: MockOpportunityService(),
        deadlineService: MockDeadlineService(),
        digestService: MockDigestService(),
      );

      await accountsProvider.fetchAccounts();

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider.value(value: accountsProvider),
            ChangeNotifierProvider(create: (_) => NotificationService()),
            ChangeNotifierProvider(create: (_) => DigestProvider(service: MockDigestService())),
            ChangeNotifierProvider(create: (_) => OpportunitiesProvider(service: MockOpportunityService())),
            ChangeNotifierProvider(create: (_) => DeadlinesProvider(service: MockDeadlineService())),
            ChangeNotifierProvider(create: (_) => SchedulerProvider()),
            ChangeNotifierProvider.value(value: onboardingProvider),
          ],
          child: const MaterialApp(
            home: AppEntryScreen(),
          ),
        ),
      );

      await tester.pumpAndSettle();
      expect(find.byType(OnboardingScreen), findsOneWidget);
    });

    testWidgets('routes to MainNavigationScreen when 1+ accounts are connected', (tester) async {
      final mockAccountService = MockAccountService(accountsToReturn: [
        EmailAccount(
          id: 1,
          emailAddress: 'test@gmail.com',
          provider: 'gmail',
          isActive: true,
          createdAt: DateTime.now(),
        ),
      ]);
      final accountsProvider = AccountsProvider(service: mockAccountService);
      final onboardingProvider = OnboardingProvider(
        accountService: mockAccountService,
        extractionService: MockExtractionService(),
        opportunityService: MockOpportunityService(),
        deadlineService: MockDeadlineService(),
        digestService: MockDigestService(),
      );

      await accountsProvider.fetchAccounts();

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider.value(value: accountsProvider),
            ChangeNotifierProvider(create: (_) => NotificationService()),
            ChangeNotifierProvider(create: (_) => DigestProvider(service: MockDigestService())),
            ChangeNotifierProvider(create: (_) => OpportunitiesProvider(service: MockOpportunityService())),
            ChangeNotifierProvider(create: (_) => DeadlinesProvider(service: MockDeadlineService())),
            ChangeNotifierProvider(create: (_) => SchedulerProvider()),
            ChangeNotifierProvider.value(value: onboardingProvider),
          ],
          child: const MaterialApp(
            home: AppEntryScreen(),
          ),
        ),
      );

      await tester.pumpAndSettle();
      expect(find.byType(MainNavigationScreen), findsOneWidget);
    });
  });
}

// ── Mock Api Client Helper ───────────────────────────────────────────────────

class MockApiClient extends ApiClient {
  final dynamic mockResponse;

  MockApiClient(this.mockResponse);

  @override
  Future<dynamic> get(String path, {Map<String, dynamic>? queryParams}) async {
    return mockResponse;
  }

  @override
  Future<dynamic> post(String path, {Map<String, dynamic>? body, Map<String, dynamic>? queryParams}) async {
    return mockResponse;
  }

  @override
  Future<dynamic> delete(String path, {Map<String, dynamic>? queryParams}) async {
    return mockResponse;
  }
}
