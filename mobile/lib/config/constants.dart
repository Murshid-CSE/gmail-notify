/// CareerMail AI — Application Constants.
library;

class AppConstants {
  static const String appName = 'CareerMail AI';
  static const String defaultTimezone = 'Asia/Kolkata';

  // Category identifiers
  static const String categoryAll = 'all';
  static const String categoryHackathon = 'hackathon';
  static const String categoryInternship = 'internship';
  static const String categoryPlacement = 'placement';
  static const String categoryCollege = 'college';
  static const String categoryGeneral = 'general';

  // Status identifiers
  static const List<String> allStatuses = [
    'opportunity',
    'registered',
    'shortlisted',
    'assessment',
    'next_round',
    'interview',
    'selected',
    'completed',
    'rejected',
  ];

  // Priority identifiers
  static const List<String> allPriorities = [
    'critical',
    'high',
    'medium',
    'low',
  ];

  // Sort fields
  static const String sortDeadline = 'deadline';
  static const String sortUpdatedAt = 'updated_at';
  static const String sortCreatedAt = 'created_at';
  static const String sortPriority = 'priority';
  static const String sortTitle = 'title';
}
