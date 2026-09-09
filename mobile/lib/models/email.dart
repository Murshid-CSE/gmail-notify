/// CareerMail AI — Email Models.
library;

class SourceEmailReference {
  final int id;
  final String gmailMessageId;
  final String subject;
  final DateTime receivedAt;
  final String sender;

  SourceEmailReference({
    required this.id,
    required this.gmailMessageId,
    required this.subject,
    required this.receivedAt,
    required this.sender,
  });

  factory SourceEmailReference.fromJson(Map<String, dynamic> json) {
    return SourceEmailReference(
      id: json['id'] as int? ?? 0,
      gmailMessageId: json['gmail_message_id'] as String? ?? '',
      subject: json['subject'] as String? ?? '(No Subject)',
      receivedAt: json['received_at'] != null
          ? DateTime.tryParse(json['received_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
      sender: json['sender'] as String? ?? 'Unknown',
    );
  }
}

class EmailDetail {
  final int id;
  final String gmailMessageId;
  final String gmailThreadId;
  final int accountId;
  final String sender;
  final List<String> recipients;
  final String subject;
  final DateTime receivedAt;
  final String? bodyText;
  final List<String> labels;
  final String processingStatus;
  final bool? isRelevant;
  final DateTime createdAt;

  EmailDetail({
    required this.id,
    required this.gmailMessageId,
    required this.gmailThreadId,
    required this.accountId,
    required this.sender,
    required this.recipients,
    required this.subject,
    required this.receivedAt,
    this.bodyText,
    required this.labels,
    required this.processingStatus,
    this.isRelevant,
    required this.createdAt,
  });

  factory EmailDetail.fromJson(Map<String, dynamic> json) {
    List<String> parseStringList(dynamic raw) {
      if (raw == null) return [];
      if (raw is List) {
        return raw.map((e) => e.toString()).toList();
      }
      return [];
    }

    return EmailDetail(
      id: json['id'] as int? ?? 0,
      gmailMessageId: json['gmail_message_id'] as String? ?? '',
      gmailThreadId: json['gmail_thread_id'] as String? ?? '',
      accountId: json['account_id'] as int? ?? 0,
      sender: json['sender'] as String? ?? 'Unknown',
      recipients: parseStringList(json['recipients']),
      subject: json['subject'] as String? ?? '(No Subject)',
      receivedAt: json['received_at'] != null
          ? DateTime.tryParse(json['received_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
      bodyText: json['body_text'] as String?,
      labels: parseStringList(json['labels']),
      processingStatus: json['processing_status'] as String? ?? 'unprocessed',
      isRelevant: json['is_relevant'] as bool?,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}
