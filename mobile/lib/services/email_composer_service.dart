import '../models/email_draft.dart';
import 'api_client.dart';

/// CareerMail AI — Email Composer Service.
///
/// Handles AI draft generation, saving drafts to Gmail, and explicit sending.
class EmailComposerService {
  final ApiClient _apiClient;

  EmailComposerService({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  /// Generate a context-aware email draft using the AI orchestrator.
  Future<EmailDraft> generateDraft({
    required int opportunityId,
    required String instruction,
    int? accountId,
  }) async {
    final body = <String, dynamic>{
      'opportunity_id': opportunityId,
      'instruction': instruction,
      'account_id': ?accountId,
    };


    final response = await _apiClient.post('/email-composer/draft', body: body);
    if (response is Map<String, dynamic>) {
      return EmailDraft.fromJson(response);
    }
    throw ParseException('Unexpected response format from draft generator');
  }

  /// Create an actual draft in the user's connected Gmail account.
  Future<GmailDraftResponse> createGmailDraft({
    required int accountId,
    required int opportunityId,
    required EmailDraft draft,
  }) async {
    final body = <String, dynamic>{
      'account_id': accountId,
      'opportunity_id': opportunityId,
      'draft': draft.toJson(),
    };

    final response = await _apiClient.post('/email-composer/gmail-draft', body: body);
    if (response is Map<String, dynamic>) {
      return GmailDraftResponse.fromJson(response);
    }
    throw ParseException('Unexpected response format from draft creation');
  }

  /// Explicitly send an email via the user's connected Gmail account.
  /// Requires confirmed == true.
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
    final body = <String, dynamic>{
      'account_id': accountId,
      'opportunity_id': opportunityId,
      'to': to,
      'cc': cc,
      'bcc': bcc,
      'subject': subject,
      'body_text': bodyText,
      'in_reply_to': ?inReplyTo,
      'thread_id': ?threadId,
      'confirmed': confirmed,
    };


    final response = await _apiClient.post('/email-composer/send', body: body);
    if (response is Map<String, dynamic>) {
      return EmailSendResponse.fromJson(response);
    }
    throw ParseException('Unexpected response format from email send');
  }
}
