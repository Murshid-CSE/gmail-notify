import '../models/scheduler_status.dart';
import 'api_client.dart';

/// CareerMail AI — Scheduler API Service.
///
/// Communicates with backend endpoints for background scheduler status,
/// manual pipeline execution, and daily brief triggers.
class SchedulerService {
  final ApiClient _client;

  SchedulerService({ApiClient? client}) : _client = client ?? ApiClient();

  /// Retrieve operational status and registered background jobs from the backend.
  Future<SchedulerStatus> getStatus() async {
    final response = await _client.get('/scheduler/status');
    if (response is Map<String, dynamic>) {
      return SchedulerStatus.fromJson(response);
    }
    throw ParseException('Invalid scheduler status response format');
  }

  /// Manually invoke the full sync, AI extraction, and deadline alert pipeline.
  Future<Map<String, dynamic>> triggerSync() async {
    final response = await _client.post('/scheduler/trigger/sync');
    if (response is Map<String, dynamic>) {
      return response;
    }
    throw ParseException('Invalid trigger sync response format');
  }

  /// Manually invoke the morning daily career brief.
  Future<Map<String, dynamic>> triggerDigest({int userId = 1}) async {
    final response = await _client.post(
      '/scheduler/trigger/digest',
      queryParams: {'user_id': userId},
    );
    if (response is Map<String, dynamic>) {
      return response;
    }
    throw ParseException('Invalid trigger digest response format');
  }

  /// Pause the backend scheduler.
  Future<bool> pauseScheduler() async {
    final response = await _client.post('/scheduler/pause');
    if (response is Map<String, dynamic>) {
      return response['success'] as bool? ?? false;
    }
    return false;
  }

  /// Resume the backend scheduler.
  Future<bool> resumeScheduler() async {
    final response = await _client.post('/scheduler/resume');
    if (response is Map<String, dynamic>) {
      return response['success'] as bool? ?? false;
    }
    return false;
  }
}
