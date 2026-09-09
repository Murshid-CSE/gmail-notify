import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:careermail/services/api_client.dart';

class MockHttpClient extends http.BaseClient {
  final Future<http.Response> Function(http.BaseRequest request) handler;

  MockHttpClient(this.handler);

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final response = await handler(request);
    return http.StreamedResponse(
      Stream.value(utf8.encode(response.body)),
      response.statusCode,
      headers: response.headers,
    );
  }
}

void main() {
  group('ApiClient Error Handling & Network Tests', () {
    test('Successful GET request returns parsed JSON', () async {
      final mock = MockHttpClient((req) async {
        return http.Response(jsonEncode({'status': 'ok', 'count': 5}), 200);
      });

      final client = ApiClient(client: mock);
      final res = await client.get('/test');

      expect(res, isA<Map<String, dynamic>>());
      expect(res['status'], 'ok');
      expect(res['count'], 5);
    });

    test('400 Bad Request throws ApiException with detail', () async {
      final mock = MockHttpClient((req) async {
        return http.Response(jsonEncode({'detail': 'Invalid query parameter'}), 400);
      });

      final client = ApiClient(client: mock);

      expect(
        () => client.get('/test'),
        throwsA(isA<ApiException>().having((e) => e.message, 'message', 'Invalid query parameter')),
      );
    });

    test('404 Not Found throws ApiException with 404 status', () async {
      final mock = MockHttpClient((req) async {
        return http.Response(jsonEncode({'detail': 'Opportunity not found'}), 404);
      });

      final client = ApiClient(client: mock);

      expect(
        () => client.get('/test'),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'statusCode', 404)),
      );
    });

    test('500 Server Error throws ApiException', () async {
      final mock = MockHttpClient((req) async {
        return http.Response('Internal Server Error', 500);
      });

      final client = ApiClient(client: mock);

      expect(
        () => client.get('/test'),
        throwsA(isA<ApiException>().having((e) => e.statusCode, 'statusCode', 500)),
      );
    });

    test('Network failure (SocketException) throws NetworkException', () async {
      final mock = MockHttpClient((req) async {
        throw const SocketException('Connection refused');
      });

      final client = ApiClient(client: mock);

      expect(
        () => client.get('/test'),
        throwsA(isA<NetworkException>()),
      );
    });

    test('Timeout throws ApiTimeoutException', () async {
      final mock = MockHttpClient((req) async {
        throw TimeoutException('Timed out');
      });

      final client = ApiClient(client: mock);

      expect(
        () => client.get('/test'),
        throwsA(isA<ApiTimeoutException>()),
      );
    });
  });
}
