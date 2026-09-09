/// CareerMail AI — Daily Digest Models.
library;

class DigestCounts {
  final int newOpportunities;
  final int statusChanges;
  final int urgentActions;
  final int deadlinesToday;
  final int deadlinesTomorrow;
  final int deadlinesThisWeek;
  final int hackathonUpdates;
  final int internshipUpdates;
  final int placementUpdates;
  final int collegeUpdates;

  DigestCounts({
    this.newOpportunities = 0,
    this.statusChanges = 0,
    this.urgentActions = 0,
    this.deadlinesToday = 0,
    this.deadlinesTomorrow = 0,
    this.deadlinesThisWeek = 0,
    this.hackathonUpdates = 0,
    this.internshipUpdates = 0,
    this.placementUpdates = 0,
    this.collegeUpdates = 0,
  });

  factory DigestCounts.fromJson(Map<String, dynamic> json) {
    return DigestCounts(
      newOpportunities: json['new_opportunities'] as int? ?? 0,
      statusChanges: json['status_changes'] as int? ?? 0,
      urgentActions: json['urgent_actions'] as int? ?? 0,
      deadlinesToday: json['deadlines_today'] as int? ?? 0,
      deadlinesTomorrow: json['deadlines_tomorrow'] as int? ?? 0,
      deadlinesThisWeek: json['deadlines_this_week'] as int? ?? 0,
      hackathonUpdates: json['hackathon_updates'] as int? ?? 0,
      internshipUpdates: json['internship_updates'] as int? ?? 0,
      placementUpdates: json['placement_updates'] as int? ?? 0,
      collegeUpdates: json['college_updates'] as int? ?? 0,
    );
  }
}

class DigestActionItem {
  final int opportunityId;
  final String title;
  final String? organization;
  final String category;
  final String action;
  final String priority;
  final DateTime? deadline;
  final int? daysRemaining;
  final bool isOverdue;

  DigestActionItem({
    required this.opportunityId,
    required this.title,
    this.organization,
    required this.category,
    required this.action,
    required this.priority,
    this.deadline,
    this.daysRemaining,
    this.isOverdue = false,
  });

  factory DigestActionItem.fromJson(Map<String, dynamic> json) {
    return DigestActionItem(
      opportunityId: json['opportunity_id'] as int? ?? 0,
      title: json['title'] as String? ?? '(Untitled)',
      organization: json['organization'] as String?,
      category: json['category'] as String? ?? 'general',
      action: json['action'] as String? ?? 'Action Required',
      priority: json['priority'] as String? ?? 'medium',
      deadline: json['deadline'] != null
          ? DateTime.tryParse(json['deadline'].toString())
          : null,
      daysRemaining: json['days_remaining'] as int?,
      isOverdue: json['is_overdue'] as bool? ?? false,
    );
  }
}

class DigestStatusChangeItem {
  final int opportunityId;
  final String title;
  final String? organization;
  final String category;
  final String oldStatus;
  final String newStatus;
  final String? roundName;
  final DateTime changedAt;

  DigestStatusChangeItem({
    required this.opportunityId,
    required this.title,
    this.organization,
    required this.category,
    required this.oldStatus,
    required this.newStatus,
    this.roundName,
    required this.changedAt,
  });

  factory DigestStatusChangeItem.fromJson(Map<String, dynamic> json) {
    return DigestStatusChangeItem(
      opportunityId: json['opportunity_id'] as int? ?? 0,
      title: json['title'] as String? ?? '(Untitled)',
      organization: json['organization'] as String?,
      category: json['category'] as String? ?? 'general',
      oldStatus: json['old_status'] as String? ?? 'unknown',
      newStatus: json['new_status'] as String? ?? 'unknown',
      roundName: json['round_name'] as String?,
      changedAt: json['changed_at'] != null
          ? DateTime.tryParse(json['changed_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}

class DigestOpportunityItem {
  final int opportunityId;
  final String title;
  final String? organization;
  final String category;
  final String status;
  final String priority;
  final DateTime? deadline;
  final DateTime firstSeenAt;

  DigestOpportunityItem({
    required this.opportunityId,
    required this.title,
    this.organization,
    required this.category,
    required this.status,
    required this.priority,
    this.deadline,
    required this.firstSeenAt,
  });

  factory DigestOpportunityItem.fromJson(Map<String, dynamic> json) {
    return DigestOpportunityItem(
      opportunityId: json['opportunity_id'] as int? ?? 0,
      title: json['title'] as String? ?? '(Untitled)',
      organization: json['organization'] as String?,
      category: json['category'] as String? ?? 'general',
      status: json['status'] as String? ?? 'opportunity',
      priority: json['priority'] as String? ?? 'medium',
      deadline: json['deadline'] != null
          ? DateTime.tryParse(json['deadline'].toString())
          : null,
      firstSeenAt: json['first_seen_at'] != null
          ? DateTime.tryParse(json['first_seen_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}

class DigestDeadlineItem {
  final int opportunityId;
  final String title;
  final String? organization;
  final String category;
  final DateTime deadline;
  final String urgencyLabel;
  final int daysRemaining;

  DigestDeadlineItem({
    required this.opportunityId,
    required this.title,
    this.organization,
    required this.category,
    required this.deadline,
    required this.urgencyLabel,
    required this.daysRemaining,
  });

  factory DigestDeadlineItem.fromJson(Map<String, dynamic> json) {
    return DigestDeadlineItem(
      opportunityId: json['opportunity_id'] as int? ?? 0,
      title: json['title'] as String? ?? '(Untitled)',
      organization: json['organization'] as String?,
      category: json['category'] as String? ?? 'general',
      deadline: json['deadline'] != null
          ? DateTime.tryParse(json['deadline'].toString()) ?? DateTime.now()
          : DateTime.now(),
      urgencyLabel: json['urgency_label'] as String? ?? 'upcoming',
      daysRemaining: json['days_remaining'] as int? ?? 0,
    );
  }
}

class DailyDigest {
  final DateTime generatedAt;
  final String targetDate;
  final String timezone;
  final String summary;
  final DigestCounts counts;
  final List<DigestActionItem> urgentActions;
  final List<DigestStatusChangeItem> recentStatusChanges;
  final List<DigestOpportunityItem> newOpportunities;
  final List<DigestDeadlineItem> upcomingDeadlines;

  DailyDigest({
    required this.generatedAt,
    required this.targetDate,
    required this.timezone,
    required this.summary,
    required this.counts,
    this.urgentActions = const [],
    this.recentStatusChanges = const [],
    this.newOpportunities = const [],
    this.upcomingDeadlines = const [],
  });

  factory DailyDigest.fromJson(Map<String, dynamic> json) {
    List<DigestActionItem> actions = [];
    if (json['urgent_actions'] is List) {
      actions = (json['urgent_actions'] as List)
          .map((a) => DigestActionItem.fromJson(a as Map<String, dynamic>))
          .toList();
    }

    List<DigestStatusChangeItem> statusChanges = [];
    if (json['recent_status_changes'] is List) {
      statusChanges = (json['recent_status_changes'] as List)
          .map((s) => DigestStatusChangeItem.fromJson(s as Map<String, dynamic>))
          .toList();
    }

    List<DigestOpportunityItem> newOpps = [];
    if (json['new_opportunities'] is List) {
      newOpps = (json['new_opportunities'] as List)
          .map((o) => DigestOpportunityItem.fromJson(o as Map<String, dynamic>))
          .toList();
    }

    List<DigestDeadlineItem> deadlines = [];
    if (json['upcoming_deadlines'] is List) {
      deadlines = (json['upcoming_deadlines'] as List)
          .map((d) => DigestDeadlineItem.fromJson(d as Map<String, dynamic>))
          .toList();
    }

    return DailyDigest(
      generatedAt: json['generated_at'] != null
          ? DateTime.tryParse(json['generated_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
      targetDate: json['target_date'] as String? ?? '',
      timezone: json['timezone'] as String? ?? 'UTC',
      summary: json['summary'] as String? ??
          json['summary_text'] as String? ??
          'Your daily career brief is ready.',
      counts: json['counts'] != null
          ? DigestCounts.fromJson(json['counts'] as Map<String, dynamic>)
          : DigestCounts(),
      urgentActions: actions,
      recentStatusChanges: statusChanges,
      newOpportunities: newOpps,
      upcomingDeadlines: deadlines,
    );
  }

  factory DailyDigest.empty() {
    return DailyDigest(
      generatedAt: DateTime.now(),
      targetDate: '',
      timezone: 'UTC',
      summary: 'No pending actions or urgent updates for today. You are all caught up!',
      counts: DigestCounts(),
      urgentActions: [],
      recentStatusChanges: [],
      newOpportunities: [],
      upcomingDeadlines: [],
    );
  }
}
