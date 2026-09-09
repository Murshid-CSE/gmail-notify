import '../models/email.dart';
import 'api_client.dart';

/// CareerMail AI — Email Service.
class EmailService {
  final ApiClient _client;

  EmailService({ApiClient? client}) : _client = client ?? ApiClient();

  Future<EmailDetail> getEmailDetail(int id) async {
    final response = await _client.get('/emails/$id');
    if (response is Map<String, dynamic>) {
      return EmailDetail.fromJson(response);
    }
    throw ParseException('Invalid format for email details');
  }
}
