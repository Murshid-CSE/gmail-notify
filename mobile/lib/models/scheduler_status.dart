// CareerMail AI — Scheduler Status & Job Models.

class SchedulerJobItem {
  final String id;
  final String name;
  final DateTime? nextRunTime;
  final bool isPaused;
  final String? trigger;

  SchedulerJobItem({
    required this.id,
    required this.name,
    this.nextRunTime,
    this.isPaused = false,
    this.trigger,
  });

  factory SchedulerJobItem.fromJson(Map<String, dynamic> json) {
    return SchedulerJobItem(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      nextRunTime: json['next_run_time'] != null
          ? DateTime.tryParse(json['next_run_time'].toString())
          : null,
      isPaused: json['is_paused'] as bool? ?? false,
      trigger: json['trigger'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'next_run_time': nextRunTime?.toIso8601String(),
      'is_paused': isPaused,
      'trigger': trigger,
    };
  }
}

class SchedulerStatus {
  final bool isRunning;
  final bool isPaused;
  final bool schedulerEnabled;
  final int syncIntervalMinutes;
  final String dailyDigestTime;
  final String timezone;
  final List<SchedulerJobItem> jobs;
  final DateTime? lastSyncStartedAt;
  final DateTime? lastSyncFinishedAt;
  final bool? lastSyncSuccess;
  final Map<String, dynamic>? lastSyncResult;
  final DateTime? lastDigestStartedAt;
  final DateTime? lastDigestFinishedAt;
  final bool? lastDigestSuccess;

  SchedulerStatus({
    required this.isRunning,
    required this.isPaused,
    required this.schedulerEnabled,
    required this.syncIntervalMinutes,
    required this.dailyDigestTime,
    required this.timezone,
    this.jobs = const [],
    this.lastSyncStartedAt,
    this.lastSyncFinishedAt,
    this.lastSyncSuccess,
    this.lastSyncResult,
    this.lastDigestStartedAt,
    this.lastDigestFinishedAt,
    this.lastDigestSuccess,
  });

  factory SchedulerStatus.fromJson(Map<String, dynamic> json) {
    final jobsList = (json['jobs'] as List<dynamic>?)
            ?.map((e) => SchedulerJobItem.fromJson(e as Map<String, dynamic>))
            .toList() ??
        [];

    return SchedulerStatus(
      isRunning: json['is_running'] as bool? ?? false,
      isPaused: json['is_paused'] as bool? ?? false,
      schedulerEnabled: json['scheduler_enabled'] as bool? ?? false,
      syncIntervalMinutes: json['sync_interval_minutes'] as int? ?? 15,
      dailyDigestTime: json['daily_digest_time'] as String? ?? '08:00',
      timezone: json['timezone'] as String? ?? 'Asia/Kolkata',
      jobs: jobsList,
      lastSyncStartedAt: json['last_sync_started_at'] != null
          ? DateTime.tryParse(json['last_sync_started_at'].toString())
          : null,
      lastSyncFinishedAt: json['last_sync_finished_at'] != null
          ? DateTime.tryParse(json['last_sync_finished_at'].toString())
          : null,
      lastSyncSuccess: json['last_sync_success'] as bool?,
      lastSyncResult: json['last_sync_result'] as Map<String, dynamic>?,
      lastDigestStartedAt: json['last_digest_started_at'] != null
          ? DateTime.tryParse(json['last_digest_started_at'].toString())
          : null,
      lastDigestFinishedAt: json['last_digest_finished_at'] != null
          ? DateTime.tryParse(json['last_digest_finished_at'].toString())
          : null,
      lastDigestSuccess: json['last_digest_success'] as bool?,
    );
  }

  SchedulerJobItem? get syncJob {
    try {
      return jobs.firstWhere((j) => j.id == 'periodic_sync');
    } catch (_) {
      return null;
    }
  }

  SchedulerJobItem? get digestJob {
    try {
      return jobs.firstWhere((j) => j.id == 'daily_digest');
    } catch (_) {
      return null;
    }
  }
}
