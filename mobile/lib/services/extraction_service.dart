import 'api_client.dart';

/// CareerMail AI — Extraction Service.
class ExtractionService {
  final ApiClient _client;

  ExtractionService({ApiClient? client}) : _client = client ?? ApiClient();

  /// Trigger batch processing of pending emails through the relevance + AI pipeline.
  Future<Map<String, dynamic>> triggerProcess({int limit = 50}) async {
    final response = await _client.post(
      '/extraction/process',
      queryParams: {'limit': limit},
    );
    if (response is Map<String, dynamic>) {
      return response;
    }
    return {'status': 'ok'};
  }

  /// Get status breakdown of emails across processing states and AI provider metrics.
  Future<Map<String, dynamic>> getStatus() async {
    final response = await _client.get('/extraction/status');
    if (response is Map<String, dynamic>) {
      return response;
    }
    return {};
  }
}
