import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../config/constants.dart';
import '../config/theme.dart';
import '../models/deadline.dart';
import '../providers/deadlines_provider.dart';
import '../widgets/deadline_card.dart';
import '../widgets/empty_state.dart';
import '../widgets/error_state.dart';

/// CareerMail AI — Grouped Deadlines Screen.
class DeadlinesScreen extends StatefulWidget {
  const DeadlinesScreen({super.key});

  @override
  State<DeadlinesScreen> createState() => _DeadlinesScreenState();
}

class _DeadlinesScreenState extends State<DeadlinesScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DeadlinesProvider>().fetchDeadlines();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Deadlines'),
      ),
      body: Consumer<DeadlinesProvider>(
        builder: (context, provider, child) {
          return Column(
            children: [
              // Category Filter Bar
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
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

              // Content Area
              Expanded(
                child: _buildBody(provider),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildCategoryChip(DeadlinesProvider provider, String categoryKey, String label) {
    final isSelected = provider.selectedCategory == categoryKey;
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

  Widget _buildBody(DeadlinesProvider provider) {
    if (provider.isLoading && provider.deadlines == null) {
      return const Center(child: CircularProgressIndicator());
    }

    if (provider.errorMessage != null && provider.deadlines == null) {
      return ErrorState(
        message: provider.errorMessage!,
        onRetry: () => provider.refresh(),
      );
    }

    final deadlines = provider.deadlines ?? DeadlinesGrouped.empty();

    if (deadlines.totalActive == 0 && deadlines.noDeadline.isEmpty) {
      return EmptyState(
        icon: Icons.event_available_outlined,
        title: 'No Deadlines Scheduled',
        message: 'There are currently no active deadlines for this category.',
        actionLabel: 'Refresh',
        onAction: () => provider.refresh(),
      );
    }

    return RefreshIndicator(
      onRefresh: () => provider.refresh(),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.only(bottom: 32),
        children: [
          if (deadlines.overdue.isNotEmpty)
            _buildGroupSection('OVERDUE', AppTheme.overdueColor, deadlines.overdue),

          if (deadlines.today.isNotEmpty)
            _buildGroupSection('DUE TODAY', AppTheme.todayColor, deadlines.today),

          if (deadlines.tomorrow.isNotEmpty)
            _buildGroupSection('DUE TOMORROW', AppTheme.tomorrowColor, deadlines.tomorrow),

          if (deadlines.thisWeek.isNotEmpty)
            _buildGroupSection('THIS WEEK', const Color(0xFF0284C7), deadlines.thisWeek),

          if (deadlines.later.isNotEmpty)
            _buildGroupSection('LATER', Colors.grey.shade700, deadlines.later),

          if (deadlines.noDeadline.isNotEmpty)
            _buildGroupSection('NO DEADLINE SPECIFIED', Colors.grey.shade500, deadlines.noDeadline),
        ],
      ),
    );
  }

  Widget _buildGroupSection(String title, Color color, List<DeadlineCardItem> items) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 6),
          child: Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(color: color, shape: BoxShape.circle),
              ),
              const SizedBox(width: 8),
              Text(
                title,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 0.5,
                  color: color,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '(${items.length})',
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
              ),
            ],
          ),
        ),
        ...items.map((item) => DeadlineCard(item: item)),
      ],
    );
  }
}
