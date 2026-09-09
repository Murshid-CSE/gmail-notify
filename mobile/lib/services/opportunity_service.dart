import '../models/opportunity.dart';
import 'api_client.dart';

/// CareerMail AI — Opportunity Service.
class OpportunityService {
  final ApiClient _client;

  OpportunityService({ApiClient? client}) : _client = client ?? ApiClient();

  Future<PaginatedOpportunities> getOpportunities({
    String? category,
    String? status,
    String? priority,
    String? search,
    String? sortBy,
    String? sortOrder,
    int page = 1,
    int pageSize = 20,
  }) async {
    final Map<String, dynamic> params = {
      'page': page,
      'page_size': pageSize,
    };

    if (category != null && category.isNotEmpty && category != 'all') {
      params['category'] = category;
    }
    if (status != null && status.isNotEmpty) {
      params['status'] = status;
    }
    if (priority != null && priority.isNotEmpty) {
      params['priority'] = priority;
    }
    if (search != null && search.trim().isNotEmpty) {
      params['search'] = search.trim();
    }
    if (sortBy != null && sortBy.isNotEmpty) {
      params['sort_by'] = sortBy;
    }
    if (sortOrder != null && sortOrder.isNotEmpty) {
      params['sort_order'] = sortOrder;
    }

    final response = await _client.get('/opportunities', queryParams: params);
    if (response is Map<String, dynamic>) {
      return PaginatedOpportunities.fromJson(response);
    }
    throw ParseException('Invalid format for opportunities list');
  }

  Future<Opportunity> getOpportunityDetail(int id) async {
    final response = await _client.get('/opportunities/$id');
    if (response is Map<String, dynamic>) {
      return Opportunity.fromJson(response);
    }
    throw ParseException('Invalid format for opportunity details');
  }
}
