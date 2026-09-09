import 'package:flutter/foundation.dart';
import '../config/constants.dart';
import '../models/deadline.dart';
import '../services/deadline_service.dart';

/// CareerMail AI — Deadlines Provider.
class DeadlinesProvider with ChangeNotifier {
  final DeadlineService _service;

  DeadlinesProvider({DeadlineService? service})
      : _service = service ?? DeadlineService();

  DeadlinesGrouped? _deadlines;
  bool _isLoading = false;
  String? _errorMessage;
  String _selectedCategory = AppConstants.categoryAll;

  DeadlinesGrouped? get deadlines => _deadlines;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  String get selectedCategory => _selectedCategory;

  void setCategory(String category) {
    if (_selectedCategory != category) {
      _selectedCategory = category;
      fetchDeadlines(force: true);
    }
  }

  Future<void> fetchDeadlines({bool force = false}) async {
    if (_deadlines != null && !force) return;

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      _deadlines = await _service.getDeadlines(category: _selectedCategory);
    } catch (e) {
      _errorMessage = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> refresh() => fetchDeadlines(force: true);
}
