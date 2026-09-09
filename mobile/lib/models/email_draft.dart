/// CareerMail AI — Email Draft & Copilot Models.
///
/// Models for AI-generated drafts, Gmail draft creation responses,
/// and explicit send responses with null-safety and list deserialization.
library;

class EmailDraft {

  final List<String> to;
  final List<String> cc;
  final List<String> bcc;
  final String subject;
  final String bodyText;
  final String? inReplyTo;
  final String? threadId;
  final int? suggestedAccountId;

  const EmailDraft({
    this.to = const [],
    this.cc = const [],
    this.bcc = const [],
    required this.subject,
    required this.bodyText,
    this.inReplyTo,
    this.threadId,
    this.suggestedAccountId,
  });

  factory EmailDraft.fromJson(Map<String, dynamic> json) {
    List<String> parseList(dynamic val) {
      if (val is List) {
        return val.map((e) => e.toString().trim()).where((e) => e.isNotEmpty).toList();
      }
      if (val is String && val.trim().isNotEmpty) {
        return [val.trim()];
      }
      return const [];
    }

    return EmailDraft(
      to: parseList(json['to']),
      cc: parseList(json['cc']),
      bcc: parseList(json['bcc']),
      subject: json['subject'] as String? ?? '',
      bodyText: json['body_text'] as String? ?? '',
      inReplyTo: json['in_reply_to'] as String?,
      threadId: json['thread_id'] as String?,
      suggestedAccountId: json['suggested_account_id'] as int?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'to': to,
      'cc': cc,
      'bcc': bcc,
      'subject': subject,
      'body_text': bodyText,
      'in_reply_to': ?inReplyTo,
      'thread_id': ?threadId,
      'suggested_account_id': ?suggestedAccountId,
    };
  }


  EmailDraft copyWith({
    List<String>? to,
    List<String>? cc,
    List<String>? bcc,
    String? subject,
    String? bodyText,
    String? inReplyTo,
    String? threadId,
    int? suggestedAccountId,
  }) {
    return EmailDraft(
      to: to ?? this.to,
      cc: cc ?? this.cc,
      bcc: bcc ?? this.bcc,
      subject: subject ?? this.subject,
      bodyText: bodyText ?? this.bodyText,
      inReplyTo: inReplyTo ?? this.inReplyTo,
      threadId: threadId ?? this.threadId,
      suggestedAccountId: suggestedAccountId ?? this.suggestedAccountId,
    );
  }
}

class GmailDraftResponse {
  final String draftId;
  final String messageId;
  final int accountId;
  final String subject;

  const GmailDraftResponse({
    required this.draftId,
    required this.messageId,
    required this.accountId,
    required this.subject,
  });

  factory GmailDraftResponse.fromJson(Map<String, dynamic> json) {
    return GmailDraftResponse(
      draftId: json['draft_id'] as String? ?? '',
      messageId: json['message_id'] as String? ?? '',
      accountId: json['account_id'] as int? ?? 0,
      subject: json['subject'] as String? ?? '',
    );
  }
}

class EmailSendResponse {
  final String messageId;
  final String? threadId;
  final DateTime sentAt;
  final int accountId;
  final List<String> to;
  final String subject;

  const EmailSendResponse({
    required this.messageId,
    this.threadId,
    required this.sentAt,
    required this.accountId,
    required this.to,
    required this.subject,
  });

  factory EmailSendResponse.fromJson(Map<String, dynamic> json) {
    final toVal = json['to'];
    List<String> recipients = const [];
    if (toVal is List) {
      recipients = toVal.map((e) => e.toString()).toList();
    } else if (toVal is String) {
      recipients = [toVal];
    }

    final sentAtStr = json['sent_at'] as String?;
    final sentAt = sentAtStr != null
        ? DateTime.tryParse(sentAtStr) ?? DateTime.now()
        : DateTime.now();

    return EmailSendResponse(
      messageId: json['message_id'] as String? ?? '',
      threadId: json['thread_id'] as String?,
      sentAt: sentAt,
      accountId: json['account_id'] as int? ?? 0,
      to: recipients,
      subject: json['subject'] as String? ?? '',
    );
  }
}
