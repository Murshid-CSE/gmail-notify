import 'dart:async';
import 'package:flutter/foundation.dart';
import '../config/constants.dart';
import '../models/opportunity.dart';
import '../services/opportunity_service.dart';

/// CareerMail AI — Opportunities Provider.
class OpportunitiesProvider with ChangeNotifier {
  final OpportunityService _service;

  OpportunitiesProvider({OpportunityService? service})
      : _service = service ?? OpportunityService();

  List<Opportunity> _items = [];
  PaginationMeta? _pagination;
  bool _isLoading = false;
  bool _isLoadingMore = false;
  String? _errorMessage;

  // Filters & Sorting state
  String _category = AppConstants.categoryAll;
  String? _status;
  String? _priority;
  String _searchQuery = '';
  String _sortBy = AppConstants.sortUpdatedAt;
  String _sortOrder = 'desc';

  Timer? _debounceTimer;

  List<Opportunity> get items => _items;
  PaginationMeta? get pagination => _pagination;
  bool get isLoading => _isLoading;
  bool get isLoadingMore => _isLoadingMore;
  String? get errorMessage => _errorMessage;

  String get category => _category;
  String? get status => _status;
  String? get priority => _priority;
  String get searchQuery => _searchQuery;
  String get sortBy => _sortBy;
  String get sortOrder => _sortOrder;

  void setCategory(String newCategory) {
    if (_category != newCategory) {
      _category = newCategory;
      fetchOpportunities(refresh: true);
    }
  }

  void setStatus(String? newStatus) {
    if (_status != newStatus) {
      _status = newStatus;
      fetchOpportunities(refresh: true);
    }
  }

  void setPriority(String? newPriority) {
    if (_priority != newPriority) {
      _priority = newPriority;
      fetchOpportunities(refresh: true);
    }
  }

  void setSorting(String newSortBy, String newSortOrder) {
    if (_sortBy != newSortBy || _sortOrder != newSortOrder) {
      _sortBy = newSortBy;
      _sortOrder = newSortOrder;
      fetchOpportunities(refresh: true);
    }
  }

  void onSearchChanged(String query) {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 350), () {
      if (_searchQuery != query) {
        _searchQuery = query;
        fetchOpportunities(refresh: true);
      }
    });
  }

  void clearFilters() {
    _category = AppConstants.categoryAll;
    _status = null;
    _priority = null;
    _searchQuery = '';
    _sortBy = AppConstants.sortUpdatedAt;
    _sortOrder = 'desc';
    fetchOpportunities(refresh: true);
  }

  Future<void> fetchOpportunities({bool refresh = false}) async {
    if (_isLoading) return;

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final result = await _service.getOpportunities(
        category: _category,
        status: _status,
        priority: _priority,
        search: _searchQuery,
        sortBy: _sortBy,
        sortOrder: _sortOrder,
        page: 1,
        pageSize: 20,
      );
      _items = result.items;
      _pagination = result.pagination;
    } catch (e) {
      _errorMessage = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> loadNextPage() async {
    if (_isLoading || _isLoadingMore || _pagination == null || !_pagination!.hasNext) {
      return;
    }

    _isLoadingMore = true;
    notifyListeners();

    try {
      final nextPage = _pagination!.page + 1;
      final result = await _service.getOpportunities(
        category: _category,
        status: _status,
        priority: _priority,
        search: _searchQuery,
        sortBy: _sortBy,
        sortOrder: _sortOrder,
        page: nextPage,
        pageSize: 20,
      );
      _items.addAll(result.items);
      _pagination = result.pagination;
    } catch (e) {
      _errorMessage = e.toString();
    } finally {
      _isLoadingMore = false;
      notifyListeners();
    }
  }

  Future<Opportunity> getOpportunityDetail(int id) async {
    return await _service.getOpportunityDetail(id);
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    super.dispose();
  }
}
