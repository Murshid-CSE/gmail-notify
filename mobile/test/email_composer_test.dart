import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';

import 'package:careermail/models/account.dart';
import 'package:careermail/models/email_draft.dart';
import 'package:careermail/providers/accounts_provider.dart';
import 'package:careermail/services/account_service.dart';
import 'package:careermail/services/api_client.dart';
import 'package:careermail/services/email_composer_service.dart';
import 'package:careermail/widgets/email_composer_sheet.dart';

// ── Mock Http Client ─────────────────────────────────────────────────────────

class MockHttpClient extends http.BaseClient {
  final Future<http.Response> Function(http.BaseRequest request) handler;
  MockHttpClient(this.handler);

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final response = await handler(request);
    return http.StreamedResponse(
      Stream.value(utf8.encode(response.body)),
      response.statusCode,
      headers: response.headers,
    );
  }
}

// ── Mock Services ────────────────────────────────────────────────────────────

class MockEmailComposerService extends EmailComposerService {
  EmailDraft? draftToReturn;
  GmailDraftResponse? gmailDraftToReturn;
  EmailSendResponse? sendResponseToReturn;

  bool shouldThrowReauthOnGenerate = false;
  bool shouldThrowGenericOnGenerate = false;

  bool shouldThrowReauthOnDraft = false;
  bool shouldThrowGenericOnDraft = false;

  bool shouldThrowReauthOnSend = false;
  bool shouldThrowGenericOnSend = false;

  String? lastInstruction;
  bool? lastConfirmed;
  int? lastAccountId;
  List<String>? lastTo;
  String? lastSubject;
  String? lastBodyText;
  EmailDraft? lastDraft;

  MockEmailComposerService({
    this.draftToReturn,
    this.gmailDraftToReturn,
    this.sendResponseToReturn,
  });

  @override
  Future<EmailDraft> generateDraft({
    required int opportunityId,
    required String instruction,
    int? accountId,
  }) async {
    lastInstruction = instruction;
    lastAccountId = accountId;

    if (shouldThrowReauthOnGenerate) {
      throw ReauthRequiredException(
        'Insufficient permissions',
        accountId: 1,
      );
    }
    if (shouldThrowGenericOnGenerate) {
      throw Exception('AI generation failed');
    }

    return draftToReturn ??
        const EmailDraft(
          to: ['recruiter@example.com'],
          cc: ['mentor@example.com'],
          bcc: [],
          subject: 'Request for Late Submission – Google Hackathon',
          bodyText:
              'Dear Organizing Team,\n\nI am writing to inquire if I could submit after the deadline.',
          inReplyTo: '<orig-msg-123@mail.gmail.com>',
          threadId: 'thread_xyz',
          suggestedAccountId: 1,
        );
  }

  @override
  Future<GmailDraftResponse> createGmailDraft({
    required int accountId,
    required int opportunityId,
    required EmailDraft draft,
  }) async {
    lastAccountId = accountId;
    lastDraft = draft;

    if (shouldThrowReauthOnDraft) {
      throw ReauthRequiredException(
        'Insufficient permissions to compose draft',
        accountId: accountId,
      );
    }
    if (shouldThrowGenericOnDraft) {
      throw Exception('Failed to save draft to Gmail');
    }

    return gmailDraftToReturn ??
        const GmailDraftResponse(
          draftId: 'draft_123',
          messageId: 'msg_123',
          accountId: 1,
          subject: 'Request for Late Submission – Google Hackathon',
        );
  }

  @override
  Future<EmailSendResponse> sendEmail({
    required int accountId,
    required int opportunityId,
    required List<String> to,
    List<String> cc = const [],
    List<String> bcc = const [],
    required String subject,
    required String bodyText,
    String? inReplyTo,
    String? threadId,
    bool confirmed = true,
  }) async {
    lastAccountId = accountId;
    lastTo = to;
    lastSubject = subject;
    lastBodyText = bodyText;
    lastConfirmed = confirmed;

    if (shouldThrowReauthOnSend) {
      throw ReauthRequiredException(
        'Insufficient permissions to send email',
        accountId: accountId,
      );
    }
    if (shouldThrowGenericOnSend) {
      throw Exception('Gmail send failed');
    }

    return sendResponseToReturn ??
        EmailSendResponse(
          messageId: 'msg_send_456',
          threadId: 'thread_xyz',
          sentAt: DateTime.parse('2026-09-09T10:00:00Z'),
          accountId: accountId,
          to: to,
          subject: subject,
        );
  }
}

class MockAccountService extends AccountService {
  final List<EmailAccount> accountsToReturn;
  final String authUrl;

  MockAccountService({
    this.accountsToReturn = const [],
    this.authUrl = 'https://accounts.google.com/o/oauth2/auth?test=1',
  });

  @override
  Future<List<EmailAccount>> getAccounts() async => accountsToReturn;

  @override
  Future<String> getOAuthStartUrl() async => authUrl;
}

// ── Test Setup Helper ────────────────────────────────────────────────────────

Widget createComposerTestApp({
  required Widget child,
  List<EmailAccount> accounts = const [],
}) {
  final accountService = MockAccountService(accountsToReturn: accounts);
  final accountsProvider = AccountsProvider(service: accountService);
  if (accounts.isNotEmpty) {
    accountsProvider.fetchAccounts();
  }

  return MaterialApp(
    home: Scaffold(
      body: ChangeNotifierProvider<AccountsProvider>.value(
        value: accountsProvider,
        child: child,
      ),
    ),
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

void main() {
  group('EmailDraft Models Serialization & Deserialization', () {
    test('EmailDraft round-trips correctly with full fields', () {
      final json = {
        'to': ['contact@google.com'],
        'cc': ['team@google.com'],
        'bcc': ['archive@example.com'],
        'subject': 'Inquiry on Submission',
        'body_text': 'Dear Team,\nHere is my inquiry.',
        'in_reply_to': '<parent@mail.com>',
        'thread_id': 'th_123',
        'suggested_account_id': 2,
      };

      final draft = EmailDraft.fromJson(json);

      expect(draft.to, ['contact@google.com']);
      expect(draft.cc, ['team@google.com']);
      expect(draft.bcc, ['archive@example.com']);
      expect(draft.subject, 'Inquiry on Submission');
      expect(draft.bodyText, 'Dear Team,\nHere is my inquiry.');
      expect(draft.inReplyTo, '<parent@mail.com>');
      expect(draft.threadId, 'th_123');
      expect(draft.suggestedAccountId, 2);

      final serialized = draft.toJson();
      expect(serialized['to'], ['contact@google.com']);
      expect(serialized['subject'], 'Inquiry on Submission');
      expect(serialized['body_text'], 'Dear Team,\nHere is my inquiry.');
      expect(serialized['in_reply_to'], '<parent@mail.com>');
      expect(serialized['thread_id'], 'th_123');
      expect(serialized['suggested_account_id'], 2);
    });

    test('EmailDraft.fromJson handles minimal and null fields safely', () {
      final json = {
        'to': null,
        'cc': null,
        'subject': null,
        'body_text': null,
      };

      final draft = EmailDraft.fromJson(json);

      expect(draft.to, isEmpty);
      expect(draft.cc, isEmpty);
      expect(draft.bcc, isEmpty);
      expect(draft.subject, '');
      expect(draft.bodyText, '');
      expect(draft.inReplyTo, isNull);
      expect(draft.threadId, isNull);
    });

    test('GmailDraftResponse parses correctly', () {
      final json = {
        'draft_id': 'd_abc',
        'message_id': 'm_xyz',
        'account_id': 1,
        'subject': 'Draft subject',
      };

      final res = GmailDraftResponse.fromJson(json);
      expect(res.draftId, 'd_abc');
      expect(res.messageId, 'm_xyz');
      expect(res.accountId, 1);
      expect(res.subject, 'Draft subject');
    });

    test('EmailSendResponse parses correctly', () {
      final json = {
        'message_id': 'msg_001',
        'thread_id': 'th_001',
        'sent_at': '2026-09-09T08:00:00Z',
        'account_id': 1,
        'to': ['recipient@gmail.com'],
        'subject': 'Sent Subject',
      };

      final res = EmailSendResponse.fromJson(json);
      expect(res.messageId, 'msg_001');
      expect(res.threadId, 'th_001');
      expect(res.sentAt, DateTime.parse('2026-09-09T08:00:00Z'));
      expect(res.accountId, 1);
      expect(res.to, ['recipient@gmail.com']);
      expect(res.subject, 'Sent Subject');
    });
  });

  group('EmailComposerService API Client Requests', () {
    test('generateDraft sends correct POST body and parses EmailDraft', () async {
      final mock = MockHttpClient((req) async {
        expect(req.url.path, '/email-composer/draft');
        expect(req.method, 'POST');
        final body = jsonDecode((req as http.Request).body);
        expect(body['opportunity_id'], 42);
        expect(body['instruction'], 'Ask for status update');
        expect(body['account_id'], 1);

        return http.Response(
          jsonEncode({
            'to': ['recruiter@corp.com'],
            'cc': [],
            'bcc': [],
            'subject': 'Application Status Inquiry',
            'body_text': 'Dear Team, any update on my application?',
            'suggested_account_id': 1,
          }),
          200,
        );
      });

      final service = EmailComposerService(apiClient: ApiClient(client: mock));
      final draft = await service.generateDraft(
        opportunityId: 42,
        instruction: 'Ask for status update',
        accountId: 1,
      );

      expect(draft.to, ['recruiter@corp.com']);
      expect(draft.subject, 'Application Status Inquiry');
    });

    test('createGmailDraft sends correct POST body and parses response', () async {
      final mock = MockHttpClient((req) async {
        expect(req.url.path, '/email-composer/gmail-draft');
        expect(req.method, 'POST');
        final body = jsonDecode((req as http.Request).body);
        expect(body['account_id'], 1);
        expect(body['opportunity_id'], 42);
        expect(body['draft']['subject'], 'Test Draft Subject');

        return http.Response(
          jsonEncode({
            'draft_id': 'draft_999',
            'message_id': 'msg_999',
            'account_id': 1,
            'subject': 'Test Draft Subject',
          }),
          200,
        );
      });

      final service = EmailComposerService(apiClient: ApiClient(client: mock));
      final res = await service.createGmailDraft(
        accountId: 1,
        opportunityId: 42,
        draft: const EmailDraft(
          to: ['test@example.com'],
          subject: 'Test Draft Subject',
          bodyText: 'Body content here',
        ),
      );

      expect(res.draftId, 'draft_999');
      expect(res.messageId, 'msg_999');
      expect(res.accountId, 1);
    });

    test('sendEmail sends correct POST body with confirmed: true', () async {
      final mock = MockHttpClient((req) async {
        expect(req.url.path, '/email-composer/send');
        expect(req.method, 'POST');
        final body = jsonDecode((req as http.Request).body);
        expect(body['account_id'], 1);
        expect(body['opportunity_id'], 42);
        expect(body['confirmed'], true);
        expect(body['to'], ['target@example.com']);
        expect(body['subject'], 'Important Update');
        expect(body['body_text'], 'Email body text here');

        return http.Response(
          jsonEncode({
            'message_id': 'msg_sent_1',
            'thread_id': 'thread_sent_1',
            'sent_at': '2026-09-09T09:00:00Z',
            'account_id': 1,
            'to': ['target@example.com'],
            'subject': 'Important Update',
          }),
          200,
        );
      });

      final service = EmailComposerService(apiClient: ApiClient(client: mock));
      final res = await service.sendEmail(
        accountId: 1,
        opportunityId: 42,
        to: ['target@example.com'],
        subject: 'Important Update',
        bodyText: 'Email body text here',
        confirmed: true,
      );

      expect(res.messageId, 'msg_sent_1');
      expect(res.accountId, 1);
    });

    test('throws ReauthRequiredException when backend returns 403 reauth_required', () async {
      final mock = MockHttpClient((req) async {
        return http.Response(
          jsonEncode({
            'detail': 'Gmail permissions insufficient. Re-authorization required.',
            'error_code': 'reauth_required',
            'account_id': 2,
          }),
          403,
        );
      });

      final service = EmailComposerService(apiClient: ApiClient(client: mock));

      expect(
        () => service.sendEmail(
          accountId: 2,
          opportunityId: 10,
          to: ['x@y.com'],
          subject: 'Hi',
          bodyText: 'Hey',
          confirmed: true,
        ),
        throwsA(
          isA<ReauthRequiredException>()
              .having((e) => e.accountId, 'accountId', 2)
              .having((e) => e.message, 'message', contains('Gmail permissions')),
        ),
      );
    });
  });

  group('EmailComposerSheet Widget Tests', () {
    final testAccount1 = EmailAccount(
      id: 1,
      emailAddress: 'primary@gmail.com',
      provider: 'gmail',
      isActive: true,
      createdAt: DateTime.now(),
    );

    final testAccount2 = EmailAccount(
      id: 2,
      emailAddress: 'secondary@gmail.com',
      provider: 'gmail',
      isActive: true,
      createdAt: DateTime.now(),
    );

    testWidgets('renders header, instruction field, chips and generate button', (tester) async {
      final mockService = MockEmailComposerService();

      await tester.pumpWidget(
        createComposerTestApp(
          accounts: [testAccount1],
          child: EmailComposerSheet(
            opportunityId: 10,
            opportunityTitle: 'Google Summer of Code 2026',
            organization: 'Google',
            composerService: mockService,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('AI Email Copilot'), findsOneWidget);
      expect(find.text('Google Summer of Code 2026'), findsOneWidget);
      expect(find.text('What do you want to say?'), findsOneWidget);
      expect(find.text('Generate Draft with AI'), findsOneWidget);

      // Verify suggestion chips
      expect(find.text('Ask for extension'), findsOneWidget);
      expect(find.text('Inquire about application status'), findsOneWidget);
      expect(find.text('Confirm interview attendance'), findsOneWidget);
      expect(find.text('Ask about remote / stipend'), findsOneWidget);
      expect(find.text('Express interest'), findsOneWidget);
    });

    testWidgets('tapping suggestion chip populates instruction input', (tester) async {
      final mockService = MockEmailComposerService();

      await tester.pumpWidget(
        createComposerTestApp(
          accounts: [testAccount1],
          child: EmailComposerSheet(
            opportunityId: 10,
            opportunityTitle: 'HackNITR',
            composerService: mockService,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Ask for extension'));
      await tester.pumpAndSettle();

      expect(find.text('Ask for extension'), findsWidgets);
      final textField = tester.widget<TextField>(
        find.widgetWithText(TextField, 'Ask for extension'),
      );
      expect(textField.controller?.text, 'Ask for extension');
    });

    testWidgets('generates draft, reveals editable fields and toggles Cc/Bcc', (tester) async {
      final mockService = MockEmailComposerService(
        draftToReturn: const EmailDraft(
          to: ['recruiter@google.com'],
          cc: ['lead@google.com'],
          bcc: [],
          subject: 'Extension Request for Application',
          bodyText: 'Hello Team,\nI would like to request an extension.',
        ),
      );

      await tester.pumpWidget(
        createComposerTestApp(
          accounts: [testAccount1],
          child: EmailComposerSheet(
            opportunityId: 10,
            opportunityTitle: 'Google Hackathon',
            composerService: mockService,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Enter instruction and tap Generate
      await tester.tap(find.text('Ask for extension'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Generate Draft with AI'));
      await tester.pumpAndSettle();

      // Verify review & edit section is shown
      expect(find.text('REVIEW & EDIT DRAFT'), findsOneWidget);
      expect(find.text('recruiter@google.com'), findsOneWidget);
      expect(find.text('Extension Request for Application'), findsOneWidget);
      expect(find.textContaining('request an extension'), findsOneWidget);

      // Verify Save Draft and Send buttons appeared
      expect(find.text('Save Draft'), findsOneWidget);
      expect(find.text('Send Email'), findsOneWidget);

      // Toggle Cc/Bcc
      expect(find.text('Show Cc/Bcc'), findsOneWidget);
      await tester.tap(find.text('Show Cc/Bcc'));
      await tester.pumpAndSettle();

      expect(find.text('Hide Cc/Bcc'), findsOneWidget);
      expect(find.text('lead@google.com'), findsOneWidget);
    });

    testWidgets('multi-account selector allows picking sender account', (tester) async {
      final mockService = MockEmailComposerService();

      await tester.pumpWidget(
        createComposerTestApp(
          accounts: [testAccount1, testAccount2],
          child: EmailComposerSheet(
            opportunityId: 10,
            opportunityTitle: 'MIT Research Fellowship',
            composerService: mockService,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Send from: '), findsOneWidget);
      expect(find.text('primary@gmail.com'), findsOneWidget);

      // Tap dropdown to select secondary account
      await tester.tap(find.text('primary@gmail.com'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('secondary@gmail.com').last);
      await tester.pumpAndSettle();

      expect(find.text('secondary@gmail.com'), findsOneWidget);
    });

    testWidgets('Save Draft triggers createGmailDraft and shows SnackBar', (tester) async {
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockService = MockEmailComposerService(
        draftToReturn: const EmailDraft(
          to: ['hiring@startup.io'],
          subject: 'Application Followup',
          bodyText: 'Following up on status.',
        ),
      );

      await tester.pumpWidget(
        createComposerTestApp(
          accounts: [testAccount1],
          child: EmailComposerSheet(
            opportunityId: 10,
            opportunityTitle: 'Startup Fellowship',
            composerService: mockService,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Inquire about application status'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Generate Draft with AI'));
      await tester.pumpAndSettle();

      await tester.ensureVisible(find.text('Save Draft'));
      await tester.tap(find.text('Save Draft'));
      await tester.pumpAndSettle();

      expect(mockService.lastAccountId, 1);
      expect(mockService.lastDraft?.subject, 'Application Followup');
      expect(find.textContaining('Draft saved to Gmail'), findsOneWidget);
    });

    testWidgets('Send Email requires explicit confirmation modal', (tester) async {
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockService = MockEmailComposerService(
        draftToReturn: const EmailDraft(
          to: ['admissions@university.edu'],
          subject: 'Interview Attendance Confirmation',
          bodyText: 'I confirm my attendance.',
        ),
      );

      bool emailSentCallbackTriggered = false;

      await tester.pumpWidget(
        createComposerTestApp(
          accounts: [testAccount1],
          child: EmailComposerSheet(
            opportunityId: 20,
            opportunityTitle: 'Graduate Program',
            composerService: mockService,
            onEmailSent: () => emailSentCallbackTriggered = true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Confirm interview attendance'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Generate Draft with AI'));
      await tester.pumpAndSettle();

      // Tap Send Email
      await tester.ensureVisible(find.text('Send Email'));
      await tester.tap(find.text('Send Email'));
      await tester.pumpAndSettle();

      // Verify explicit confirmation dialog is displayed
      expect(find.text('Confirm Email Send'), findsOneWidget);
      expect(find.textContaining('Are you sure you want to send this email now?'), findsOneWidget);
      expect(find.text('From: primary@gmail.com'), findsOneWidget);
      expect(find.text('To: admissions@university.edu'), findsOneWidget);

      // Tap Cancel -> should NOT send
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(find.text('Confirm Email Send'), findsNothing);
      expect(mockService.lastConfirmed, isNull);
      expect(emailSentCallbackTriggered, isFalse);

      // Tap Send Email again -> Confirm & Send
      await tester.ensureVisible(find.text('Send Email'));
      await tester.tap(find.text('Send Email'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Send Now'));
      await tester.pumpAndSettle();

      expect(mockService.lastConfirmed, true);
      expect(emailSentCallbackTriggered, true);
    });

    testWidgets('shows error banner when send fails', (tester) async {
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockService = MockEmailComposerService(
        draftToReturn: const EmailDraft(
          to: ['test@example.com'],
          subject: 'Subject',
          bodyText: 'Body',
        ),
      )..shouldThrowGenericOnSend = true;

      await tester.pumpWidget(
        createComposerTestApp(
          accounts: [testAccount1],
          child: EmailComposerSheet(
            opportunityId: 20,
            opportunityTitle: 'Job Opening',
            composerService: mockService,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Express interest'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Generate Draft with AI'));
      await tester.pumpAndSettle();

      await tester.ensureVisible(find.text('Send Email'));
      await tester.tap(find.text('Send Email'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Send Now'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Gmail send failed'), findsOneWidget);
    });

    testWidgets('shows Re-authorization card when ReauthRequiredException thrown', (tester) async {
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockService = MockEmailComposerService()
        ..shouldThrowReauthOnGenerate = true;

      await tester.pumpWidget(
        createComposerTestApp(
          accounts: [testAccount1],
          child: EmailComposerSheet(
            opportunityId: 30,
            opportunityTitle: 'Contest Entry',
            composerService: mockService,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Ask for extension'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Generate Draft with AI'));
      await tester.pumpAndSettle();

      // Verify reauthorization UI
      expect(find.text('Gmail Permission Refresh Required'), findsOneWidget);
      expect(find.text('Re-authorize with Google'), findsOneWidget);
      expect(find.textContaining('Account requiring re-authorization: primary@gmail.com'), findsOneWidget);
    });
  });
}
