import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../config/constants.dart';
import '../config/theme.dart';
import '../providers/opportunities_provider.dart';
import '../widgets/empty_state.dart';
import '../widgets/error_state.dart';
import '../widgets/opportunity_card.dart';

/// CareerMail AI — Categorized & Filterable Opportunities Screen.
class OpportunitiesScreen extends StatefulWidget {
  const OpportunitiesScreen({super.key});

  @override
  State<OpportunitiesScreen> createState() => _OpportunitiesScreenState();
}

class _OpportunitiesScreenState extends State<OpportunitiesScreen> {
  final ScrollController _scrollController = ScrollController();
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<OpportunitiesProvider>().fetchOpportunities();
    });
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      context.read<OpportunitiesProvider>().loadNextPage();
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  void _showFilterBottomSheet(BuildContext context) {
    final provider = context.read<OpportunitiesProvider>();
    String? tempStatus = provider.status;
    String? tempPriority = provider.priority;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Text(
                        'Filter Opportunities',
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                      ),
                      const Spacer(),
                      TextButton(
                        onPressed: () {
                          setModalState(() {
                            tempStatus = null;
                            tempPriority = null;
                          });
                        },
                        child: const Text('Reset'),
                      ),
                    ],
                  ),
                  const Divider(),
                  const SizedBox(height: 10),

                  // Status filter
                  const Text('STATUS', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: Colors.grey)),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    children: AppConstants.allStatuses.map((s) {
                      final isSelected = tempStatus == s;
                      return ChoiceChip(
                        label: Text(s.replaceAll('_', ' ')),
                        selected: isSelected,
                        onSelected: (selected) {
                          setModalState(() {
                            tempStatus = selected ? s : null;
                          });
                        },
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 16),

                  // Priority filter
                  const Text('PRIORITY', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: Colors.grey)),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    children: AppConstants.allPriorities.map((p) {
                      final isSelected = tempPriority == p;
                      return ChoiceChip(
                        label: Text(p.toUpperCase()),
                        selected: isSelected,
                        onSelected: (selected) {
                          setModalState(() {
                            tempPriority = selected ? p : null;
                          });
                        },
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 24),

                  // Apply button
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: () {
                        provider.setStatus(tempStatus);
                        provider.setPriority(tempPriority);
                        Navigator.pop(ctx);
                      },
                      child: const Text('Apply Filters'),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Opportunities'),
        actions: [
          IconButton(
            icon: const Icon(Icons.tune),
            tooltip: 'Filter Options',
            onPressed: () => _showFilterBottomSheet(context),
          ),
          PopupMenuButton<String>(
            icon: const Icon(Icons.sort),
            tooltip: 'Sort By',
            onSelected: (value) {
              final provider = context.read<OpportunitiesProvider>();
              switch (value) {
                case 'deadline':
                  provider.setSorting(AppConstants.sortDeadline, 'asc');
                  break;
                case 'priority':
                  provider.setSorting(AppConstants.sortPriority, 'desc');
                  break;
                case 'updated':
                  provider.setSorting(AppConstants.sortUpdatedAt, 'desc');
                  break;
                case 'title':
                  provider.setSorting(AppConstants.sortTitle, 'asc');
                  break;
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(value: 'deadline', child: Text('Sort by Deadline (Soonest)')),
              const PopupMenuItem(value: 'priority', child: Text('Sort by Priority (Highest)')),
              const PopupMenuItem(value: 'updated', child: Text('Sort by Recently Updated')),
              const PopupMenuItem(value: 'title', child: Text('Sort by Title (A-Z)')),
            ],
          ),
        ],
      ),
      body: Consumer<OpportunitiesProvider>(
        builder: (context, provider, child) {
          return Column(
            children: [
              // Search Input Bar
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                child: TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: 'Search title or organization...',
                    prefixIcon: const Icon(Icons.search, size: 20),
                    suffixIcon: _searchController.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear, size: 18),
                            onPressed: () {
                              _searchController.clear();
                              provider.onSearchChanged('');
                            },
                          )
                        : null,
                    filled: true,
                    fillColor: Colors.grey.shade100,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 0),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: BorderSide.none,
                    ),
                  ),
                  onChanged: (val) {
                    setState(() {});
                    provider.onSearchChanged(val);
                  },
                ),
              ),

              // Category Filter Tabs
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: Row(
                  children: [
                    _buildCategoryChip(provider, AppConstants.categoryAll, 'All'),
                    _buildCategoryChip(provider, AppConstants.categoryHackathon, 'Hackathons'),
                    _buildCategoryChip(provider, AppConstants.categoryInternship, 'Internships'),
                    _buildCategoryChip(provider, AppConstants.categoryPlacement, 'Placements'),
                    _buildCategoryChip(provider, AppConstants.categoryCollege, 'College'),
                  ],
                ),
              ),

              // Active Filters indicator if status or priority is set
              if (provider.status != null || provider.priority != null) ...[
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                  child: Row(
                    children: [
                      const Text('Filtered by: ', style: TextStyle(fontSize: 12, color: Colors.grey)),
                      if (provider.status != null)
                        Chip(
                          label: Text('Status: ${provider.status}', style: const TextStyle(fontSize: 11)),
                          onDeleted: () => provider.setStatus(null),
                          visualDensity: VisualDensity.compact,
                        ),
                      const SizedBox(width: 4),
                      if (provider.priority != null)
                        Chip(
                          label: Text('Priority: ${provider.priority}', style: const TextStyle(fontSize: 11)),
                          onDeleted: () => provider.setPriority(null),
                          visualDensity: VisualDensity.compact,
                        ),
                    ],
                  ),
                ),
              ],

              const SizedBox(height: 4),

              // Opportunities List / States
              Expanded(
                child: _buildListContent(provider),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildCategoryChip(OpportunitiesProvider provider, String categoryKey, String label) {
    final isSelected = provider.category == categoryKey;
    final catColor = categoryKey == AppConstants.categoryAll
        ? AppTheme.primaryColor
        : AppTheme.getCategoryColor(categoryKey);

    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: FilterChip(
        label: Text(label),
        selected: isSelected,
        selectedColor: catColor.withValues(alpha: 0.18),
        labelStyle: TextStyle(
          color: isSelected ? catColor : Colors.grey.shade700,
          fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
          fontSize: 13,
        ),
        onSelected: (_) => provider.setCategory(categoryKey),
      ),
    );
  }

  Widget _buildListContent(OpportunitiesProvider provider) {
    if (provider.isLoading && provider.items.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (provider.errorMessage != null && provider.items.isEmpty) {
      return ErrorState(
        message: provider.errorMessage!,
        onRetry: () => provider.fetchOpportunities(refresh: true),
      );
    }

    if (provider.items.isEmpty) {
      return EmptyState(
        icon: Icons.search_off_outlined,
        title: 'No Opportunities Found',
        message: 'No opportunities matched your search and filter criteria.',
        actionLabel: 'Reset Filters',
        onAction: () {
          _searchController.clear();
          provider.clearFilters();
        },
      );
    }

    return RefreshIndicator(
      onRefresh: () => provider.fetchOpportunities(refresh: true),
      child: ListView.builder(
        controller: _scrollController,
        physics: const AlwaysScrollableScrollPhysics(),
        itemCount: provider.items.length + (provider.isLoadingMore ? 1 : 0),
        itemBuilder: (context, index) {
          if (index < provider.items.length) {
            return OpportunityCard(opportunity: provider.items[index]);
          }
          return const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Center(child: CircularProgressIndicator()),
          );
        },
      ),
    );
  }
}
