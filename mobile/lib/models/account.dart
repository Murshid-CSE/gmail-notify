/// CareerMail AI — Email Account Model.
library;

class EmailAccount {
  final int id;
  final String emailAddress;
  final String provider;
  final bool isActive;
  final DateTime? lastSyncAt;
  final DateTime createdAt;

  EmailAccount({
    required this.id,
    required this.emailAddress,
    required this.provider,
    required this.isActive,
    this.lastSyncAt,
    required this.createdAt,
  });

  factory EmailAccount.fromJson(Map<String, dynamic> json) {
    return EmailAccount(
      id: json['id'] as int? ?? 0,
      emailAddress: json['email_address'] as String? ?? '',
      provider: json['provider'] as String? ?? 'gmail',
      isActive: json['is_active'] as bool? ?? true,
      lastSyncAt: json['last_sync_at'] != null
          ? DateTime.tryParse(json['last_sync_at'].toString())
          : null,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}
