import '../models/account.dart';
import 'api_client.dart';

/// CareerMail AI — Account Service.
class AccountService {
  final ApiClient _client;

  AccountService({ApiClient? client}) : _client = client ?? ApiClient();

  Future<List<EmailAccount>> getAccounts() async {
    final response = await _client.get('/accounts');
    if (response is List) {
      return response
          .map((a) => EmailAccount.fromJson(a as Map<String, dynamic>))
          .toList();
    }
    if (response is Map<String, dynamic> && response['accounts'] is List) {
      return (response['accounts'] as List)
          .map((a) => EmailAccount.fromJson(a as Map<String, dynamic>))
          .toList();
    }
    throw ParseException('Invalid format for accounts list');
  }

  Future<String> getOAuthStartUrl() async {
    final response = await _client.get('/auth/google/start');
    if (response is Map<String, dynamic> && response.containsKey('authorization_url')) {
      return response['authorization_url'] as String;
    }
    throw ParseException('Failed to retrieve OAuth authorization URL');
  }

  Future<Map<String, dynamic>> syncAccount(int id) async {
    final response = await _client.post('/accounts/$id/sync');
    if (response is Map<String, dynamic>) {
      return response;
    }
    return {'status': 'ok'};
  }

  Future<Map<String, dynamic>> disconnectAccount(int id) async {
    final response = await _client.delete('/accounts/$id');
    if (response is Map<String, dynamic>) {
      return response;
    }
    return {'message': 'Account disconnected'};
  }
}
