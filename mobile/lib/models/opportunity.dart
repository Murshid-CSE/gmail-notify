import 'email.dart';

/// CareerMail AI — Opportunity Models.

class StatusHistoryItem {
  final int id;
  final String? oldStatus;
  final String newStatus;
  final int? sourceEmailId;
  final DateTime changedAt;

  StatusHistoryItem({
    required this.id,
    this.oldStatus,
    required this.newStatus,
    this.sourceEmailId,
    required this.changedAt,
  });

  factory StatusHistoryItem.fromJson(Map<String, dynamic> json) {
    return StatusHistoryItem(
      id: json['id'] as int? ?? 0,
      oldStatus: json['old_status'] as String?,
      newStatus: json['new_status'] as String? ?? 'opportunity',
      sourceEmailId: json['source_email_id'] as int?,
      changedAt: json['changed_at'] != null
          ? DateTime.tryParse(json['changed_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}

class Opportunity {
  final int id;
  final String category;
  final String title;
  final String? organization;
  final String? description;
  final String status;
  final String? roundName;
  final DateTime? deadline;
  final String? eventDate;
  final String? location;
  final String? eligibility;
  final String? applyUrl;
  final String? eventUrl;
  final bool actionRequired;
  final String? action;
  final String priority;
  final double confidence;
  final DateTime firstSeenAt;
  final DateTime lastUpdatedAt;

  // Computed deadline metrics
  final int? daysRemaining;
  final double? hoursRemaining;
  final bool isOverdue;
  final bool isDueToday;
  final bool isDueTomorrow;

  // Detail view fields
  final List<SourceEmailReference> sourceEmails;
  final List<StatusHistoryItem> statusHistory;

  Opportunity({
    required this.id,
    required this.category,
    required this.title,
    this.organization,
    this.description,
    required this.status,
    this.roundName,
    this.deadline,
    this.eventDate,
    this.location,
    this.eligibility,
    this.applyUrl,
    this.eventUrl,
    required this.actionRequired,
    this.action,
    required this.priority,
    required this.confidence,
    required this.firstSeenAt,
    required this.lastUpdatedAt,
    this.daysRemaining,
    this.hoursRemaining,
    this.isOverdue = false,
    this.isDueToday = false,
    this.isDueTomorrow = false,
    this.sourceEmails = const [],
    this.statusHistory = const [],
  });

  factory Opportunity.fromJson(Map<String, dynamic> json) {
    List<SourceEmailReference> emails = [];
    if (json['source_emails'] is List) {
      emails = (json['source_emails'] as List)
          .map((e) => SourceEmailReference.fromJson(e as Map<String, dynamic>))
          .toList();
    }

    List<StatusHistoryItem> history = [];
    if (json['status_history'] is List) {
      history = (json['status_history'] as List)
          .map((h) => StatusHistoryItem.fromJson(h as Map<String, dynamic>))
          .toList();
    }

    return Opportunity(
      id: json['id'] as int? ?? 0,
      category: json['category'] as String? ?? 'general',
      title: json['title'] as String? ?? '(Untitled Opportunity)',
      organization: json['organization'] as String?,
      description: json['description'] as String?,
      status: json['status'] as String? ?? 'opportunity',
      roundName: json['round_name'] as String?,
      deadline: json['deadline'] != null
          ? DateTime.tryParse(json['deadline'].toString())
          : null,
      eventDate: json['event_date'] as String?,
      location: json['location'] as String?,
      eligibility: json['eligibility'] as String?,
      applyUrl: json['apply_url'] as String?,
      eventUrl: json['event_url'] as String?,
      actionRequired: json['action_required'] as bool? ?? false,
      action: json['action'] as String?,
      priority: json['priority'] as String? ?? 'medium',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.8,
      firstSeenAt: json['first_seen_at'] != null
          ? DateTime.tryParse(json['first_seen_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
      lastUpdatedAt: json['last_updated_at'] != null
          ? DateTime.tryParse(json['last_updated_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
      daysRemaining: json['days_remaining'] as int?,
      hoursRemaining: (json['hours_remaining'] as num?)?.toDouble(),
      isOverdue: json['is_overdue'] as bool? ?? false,
      isDueToday: json['is_due_today'] as bool? ?? false,
      isDueTomorrow: json['is_due_tomorrow'] as bool? ?? false,
      sourceEmails: emails,
      statusHistory: history,
    );
  }
}

class PaginationMeta {
  final int page;
  final int pageSize;
  final int totalItems;
  final int totalPages;
  final bool hasNext;
  final bool hasPrevious;

  PaginationMeta({
    required this.page,
    required this.pageSize,
    required this.totalItems,
    required this.totalPages,
    required this.hasNext,
    required this.hasPrevious,
  });

  factory PaginationMeta.fromJson(Map<String, dynamic> json) {
    return PaginationMeta(
      page: json['page'] as int? ?? 1,
      pageSize: json['page_size'] as int? ?? 20,
      totalItems: json['total_items'] as int? ?? 0,
      totalPages: json['total_pages'] as int? ?? 1,
      hasNext: json['has_next'] as bool? ?? false,
      hasPrevious: json['has_previous'] as bool? ?? false,
    );
  }
}

class PaginatedOpportunities {
  final List<Opportunity> items;
  final PaginationMeta pagination;

  PaginatedOpportunities({
    required this.items,
    required this.pagination,
  });

  factory PaginatedOpportunities.fromJson(Map<String, dynamic> json) {
    List<Opportunity> parsedItems = [];
    if (json['items'] is List) {
      parsedItems = (json['items'] as List)
          .map((e) => Opportunity.fromJson(e as Map<String, dynamic>))
          .toList();
    }

    PaginationMeta meta = json['pagination'] != null
        ? PaginationMeta.fromJson(json['pagination'] as Map<String, dynamic>)
        : PaginationMeta(
            page: 1,
            pageSize: parsedItems.length,
            totalItems: parsedItems.length,
            totalPages: 1,
            hasNext: false,
            hasPrevious: false,
          );

    return PaginatedOpportunities(
      items: parsedItems,
      pagination: meta,
    );
  }
}
