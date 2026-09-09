import '../config/api_config.dart';
import '../models/deadline.dart';
import 'api_client.dart';

/// CareerMail AI — Deadline Service.
class DeadlineService {
  final ApiClient _client;
  final ApiConfig _config;

  DeadlineService({ApiClient? client, ApiConfig? config})
      : _client = client ?? ApiClient(),
        _config = config ?? ApiConfig();

  Future<DeadlinesGrouped> getDeadlines({String? category, String? tz}) async {
    final Map<String, dynamic> params = {};
    if (category != null && category.isNotEmpty && category != 'all') {
      params['category'] = category;
    }
    params['tz'] = tz ?? _config.userTimezone;

    final response = await _client.get('/deadlines', queryParams: params);
    if (response is Map<String, dynamic>) {
      return DeadlinesGrouped.fromJson(response);
    }
    throw ParseException('Invalid format for deadlines grouped response');
  }
}
