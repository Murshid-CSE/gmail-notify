/// CareerMail AI — Deadline Models.
library;

class DeadlineCardItem {
  final int id;
  final String title;
  final String? organization;
  final String category;
  final String status;
  final DateTime? deadline;
  final String priority;
  final bool actionRequired;
  final String? action;
  final int? daysRemaining;
  final double? hoursRemaining;
  final bool isOverdue;
  final bool isDueToday;
  final bool isDueTomorrow;

  DeadlineCardItem({
    required this.id,
    required this.title,
    this.organization,
    required this.category,
    required this.status,
    this.deadline,
    required this.priority,
    required this.actionRequired,
    this.action,
    this.daysRemaining,
    this.hoursRemaining,
    this.isOverdue = false,
    this.isDueToday = false,
    this.isDueTomorrow = false,
  });

  factory DeadlineCardItem.fromJson(Map<String, dynamic> json) {
    return DeadlineCardItem(
      id: json['id'] as int? ?? 0,
      title: json['title'] as String? ?? '(Untitled)',
      organization: json['organization'] as String?,
      category: json['category'] as String? ?? 'general',
      status: json['status'] as String? ?? 'opportunity',
      deadline: json['deadline'] != null
          ? DateTime.tryParse(json['deadline'].toString())
          : null,
      priority: json['priority'] as String? ?? 'medium',
      actionRequired: json['action_required'] as bool? ?? false,
      action: json['action'] as String?,
      daysRemaining: json['days_remaining'] as int?,
      hoursRemaining: (json['hours_remaining'] as num?)?.toDouble(),
      isOverdue: json['is_overdue'] as bool? ?? false,
      isDueToday: json['is_due_today'] as bool? ?? false,
      isDueTomorrow: json['is_due_tomorrow'] as bool? ?? false,
    );
  }
}

class DeadlinesGrouped {
  final List<DeadlineCardItem> overdue;
  final List<DeadlineCardItem> today;
  final List<DeadlineCardItem> tomorrow;
  final List<DeadlineCardItem> thisWeek;
  final List<DeadlineCardItem> later;
  final List<DeadlineCardItem> noDeadline;
  final int totalActive;

  DeadlinesGrouped({
    required this.overdue,
    required this.today,
    required this.tomorrow,
    required this.thisWeek,
    required this.later,
    required this.noDeadline,
    required this.totalActive,
  });

  factory DeadlinesGrouped.fromJson(Map<String, dynamic> json) {
    List<DeadlineCardItem> parseGroup(String key) {
      if (json[key] is List) {
        return (json[key] as List)
            .map((e) => DeadlineCardItem.fromJson(e as Map<String, dynamic>))
            .toList();
      }
      return [];
    }

    return DeadlinesGrouped(
      overdue: parseGroup('overdue'),
      today: parseGroup('today'),
      tomorrow: parseGroup('tomorrow'),
      thisWeek: parseGroup('this_week'),
      later: parseGroup('later'),
      noDeadline: parseGroup('no_deadline'),
      totalActive: json['total_active'] as int? ?? 0,
    );
  }

  factory DeadlinesGrouped.empty() {
    return DeadlinesGrouped(
      overdue: [],
      today: [],
      tomorrow: [],
      thisWeek: [],
      later: [],
      noDeadline: [],
      totalActive: 0,
    );
  }
}
