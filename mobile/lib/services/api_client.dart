import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';

/// CareerMail AI — Custom Exception Hierarchy.

abstract class AppException implements Exception {
  final String message;
  final int? statusCode;

  AppException(this.message, [this.statusCode]);

  @override
  String toString() => message;
}

class NetworkException extends AppException {
  NetworkException([super.message = 'Cannot connect to backend. Please check that FastAPI is running.']);
}

class ApiException extends AppException {
  ApiException(super.message, [super.statusCode]);
}

class ReauthRequiredException extends ApiException {
  final int? accountId;
  ReauthRequiredException(String message, {this.accountId}) : super(message, 403);
}


class ApiTimeoutException extends AppException {
  ApiTimeoutException([super.message = 'Request timed out. Please try again.']);
}

class ParseException extends AppException {
  ParseException([super.message = 'Failed to process server response.']);
}

/// CareerMail AI — Robust HTTP API Client.
class ApiClient {
  final http.Client _client;
  final ApiConfig _config;
  static const Duration _timeout = Duration(seconds: 15);

  ApiClient({http.Client? client, ApiConfig? config})
      : _client = client ?? http.Client(),
        _config = config ?? ApiConfig();

  String get baseUrl => _config.baseUrl;

  Uri _buildUri(String path, [Map<String, dynamic>? queryParameters]) {
    String cleanPath = path.startsWith('/') ? path : '/$path';
    String fullUrl = '$baseUrl$cleanPath';
    Uri uri = Uri.parse(fullUrl);

    if (queryParameters != null && queryParameters.isNotEmpty) {
      final Map<String, String> stringParams = {};
      queryParameters.forEach((key, value) {
        if (value != null) {
          stringParams[key] = value.toString();
        }
      });
      uri = uri.replace(queryParameters: stringParams);
    }
    return uri;
  }

  Future<dynamic> get(String path, {Map<String, dynamic>? queryParams}) async {
    final uri = _buildUri(path, queryParams);
    try {
      final response = await _client.get(
        uri,
        headers: {
          'Accept': 'application/json',
        },
      ).timeout(_timeout);

      return _handleResponse(response);
    } on SocketException {
      throw NetworkException();
    } on TimeoutException {
      throw ApiTimeoutException();
    } on http.ClientException {
      throw NetworkException();
    } catch (e) {
      if (e is AppException) rethrow;
      throw NetworkException(e.toString());
    }
  }

  Future<dynamic> post(
    String path, {
    Map<String, dynamic>? body,
    Map<String, dynamic>? queryParams,
  }) async {
    final uri = _buildUri(path, queryParams);
    try {
      final response = await _client.post(
        uri,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: body != null ? jsonEncode(body) : null,
      ).timeout(_timeout);

      return _handleResponse(response);
    } on SocketException {
      throw NetworkException();
    } on TimeoutException {
      throw ApiTimeoutException();
    } on http.ClientException {
      throw NetworkException();
    } catch (e) {
      if (e is AppException) rethrow;
      throw NetworkException(e.toString());
    }
  }

  Future<dynamic> delete(String path, {Map<String, dynamic>? queryParams}) async {
    final uri = _buildUri(path, queryParams);
    try {
      final response = await _client.delete(
        uri,
        headers: {
          'Accept': 'application/json',
        },
      ).timeout(_timeout);

      return _handleResponse(response);
    } on SocketException {
      throw NetworkException();
    } on TimeoutException {
      throw ApiTimeoutException();
    } on http.ClientException {
      throw NetworkException();
    } catch (e) {
      if (e is AppException) rethrow;
      throw NetworkException(e.toString());
    }
  }


  dynamic _handleResponse(http.Response response) {
    dynamic bodyJson;
    if (response.body.isNotEmpty) {
      try {
        bodyJson = jsonDecode(response.body);
      } catch (_) {
        bodyJson = response.body;
      }
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return bodyJson;
    }

    String errorMessage = 'Request failed with status code ${response.statusCode}';
    if (bodyJson is Map<String, dynamic>) {
      if (bodyJson.containsKey('detail')) {
        errorMessage = bodyJson['detail'].toString();
      }
      if (response.statusCode == 403 && bodyJson['error_code'] == 'reauth_required') {
        throw ReauthRequiredException(
          errorMessage,
          accountId: bodyJson['account_id'] is int ? bodyJson['account_id'] as int : null,
        );
      }
    }

    throw ApiException(errorMessage, response.statusCode);
  }

}
