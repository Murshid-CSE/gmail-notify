import '../config/api_config.dart';
import '../models/digest.dart';
import 'api_client.dart';

/// CareerMail AI — Daily Digest Service.
class DigestService {
  final ApiClient _client;
  final ApiConfig _config;

  DigestService({ApiClient? client, ApiConfig? config})
      : _client = client ?? ApiClient(),
        _config = config ?? ApiConfig();

  Future<DailyDigest> getDailyDigest({String? tz}) async {
    final Map<String, dynamic> params = {
      'tz': tz ?? _config.userTimezone,
    };

    final response = await _client.get('/digest/today', queryParams: params);
    if (response is Map<String, dynamic>) {
      return DailyDigest.fromJson(response);
    }
    throw ParseException('Invalid format for daily digest response');
  }
}
