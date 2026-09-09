import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../config/theme.dart';
import '../models/digest.dart';
import '../providers/digest_provider.dart';
import '../widgets/empty_state.dart';
import '../widgets/error_state.dart';
import '../widgets/urgent_action_card.dart';
import 'opportunity_detail_screen.dart';

/// CareerMail AI — Dashboard / Home Screen ("What matters today?").
class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DigestProvider>().fetchDigest();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'CareerMail AI',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            Text(
              DateFormat('EEEE, MMM d').format(DateTime.now()),
              style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
            ),
          ],
        ),
      ),
      body: Consumer<DigestProvider>(
        builder: (context, provider, child) {
          if (provider.isLoading && provider.digest == null) {
            return const Center(child: CircularProgressIndicator());
          }

          if (provider.errorMessage != null && provider.digest == null) {
            return ErrorState(
              message: provider.errorMessage!,
              onRetry: () => provider.refresh(),
            );
          }

          final digest = provider.digest ?? DailyDigest.empty();

          return RefreshIndicator(
            onRefresh: () => provider.refresh(),
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.only(bottom: 32),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 1. Today's Brief Card
                  _buildBriefCard(digest),

                  // 2. 4 Metric Counters Grid
                  _buildMetricsGrid(digest.counts),

                  // 3. Urgent Actions Section
                  if (digest.urgentActions.isNotEmpty) ...[
                    _buildSectionHeader(
                      'URGENT ACTIONS',
                      Icons.warning_amber_rounded,
                      AppTheme.overdueColor,
                      digest.urgentActions.length,
                    ),
                    ...digest.urgentActions.map((action) => UrgentActionCard(item: action)),
                    const SizedBox(height: 12),
                  ],

                  // 4. Upcoming Deadlines Section
                  if (digest.upcomingDeadlines.isNotEmpty) ...[
                    _buildSectionHeader(
                      'APPROACHING DEADLINES',
                      Icons.timer_outlined,
                      AppTheme.todayColor,
                      digest.upcomingDeadlines.length,
                    ),
                    ...digest.upcomingDeadlines.map((dl) => _buildDeadlineTile(dl)),
                    const SizedBox(height: 12),
                  ],

                  // 5. Recent Status Changes Section
                  if (digest.recentStatusChanges.isNotEmpty) ...[
                    _buildSectionHeader(
                      'RECENT UPDATES',
                      Icons.trending_up,
                      AppTheme.primaryColor,
                      digest.recentStatusChanges.length,
                    ),
                    ...digest.recentStatusChanges.map((sc) => _buildStatusChangeTile(sc)),
                    const SizedBox(height: 12),
                  ],

                  // Empty State if no actions or deadlines
                  if (digest.urgentActions.isEmpty &&
                      digest.upcomingDeadlines.isEmpty &&
                      digest.recentStatusChanges.isEmpty) ...[
                    const EmptyState(
                      icon: Icons.check_circle_outline,
                      title: 'All Caught Up For Today',
                      message: 'No pending urgent actions or critical deadlines due today.',
                    ),
                  ],
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildBriefCard(DailyDigest digest) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.primaryColor,
            AppTheme.primaryColor.withValues(alpha: 0.82),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primaryColor.withValues(alpha: 0.25),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.auto_awesome, color: Colors.amberAccent, size: 18),
              SizedBox(width: 8),
              Text(
                "TODAY'S CAREER BRIEF",
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                  letterSpacing: 0.8,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            digest.summary,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 14,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMetricsGrid(DigestCounts counts) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: GridView.count(
        crossAxisCount: 2,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        mainAxisSpacing: 10,
        crossAxisSpacing: 10,
        childAspectRatio: 2.2,
        children: [
          _buildMetricTile(
            'Urgent Actions',
            counts.urgentActions.toString(),
            Icons.notification_important_outlined,
            counts.urgentActions > 0 ? AppTheme.overdueColor : Colors.grey,
          ),
          _buildMetricTile(
            "Today's Deadlines",
            counts.deadlinesToday.toString(),
            Icons.today_outlined,
            counts.deadlinesToday > 0 ? AppTheme.todayColor : Colors.grey,
          ),
          _buildMetricTile(
            'New Today',
            counts.newOpportunities.toString(),
            Icons.fiber_new_outlined,
            counts.newOpportunities > 0 ? AppTheme.internshipColor : Colors.grey,
          ),
          _buildMetricTile(
            'Status Updates',
            counts.statusChanges.toString(),
            Icons.trending_up,
            counts.statusChanges > 0 ? AppTheme.primaryColor : Colors.grey,
          ),
        ],
      ),
    );
  }

  Widget _buildMetricTile(String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, size: 20, color: color),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  value,
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: color,
                  ),
                ),
                Text(
                  label,
                  style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title, IconData icon, Color color, int count) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
      child: Row(
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 6),
          Text(
            title,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.bold,
              letterSpacing: 0.5,
              color: Colors.grey.shade800,
            ),
          ),
          const SizedBox(width: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              count.toString(),
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDeadlineTile(DigestDeadlineItem item) {
    final catColor = AppTheme.getCategoryColor(item.category);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: catColor.withValues(alpha: 0.12),
          child: Icon(AppTheme.getCategoryIcon(item.category), color: catColor, size: 18),
        ),
        title: Text(
          item.title,
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          item.organization ?? item.category.toUpperCase(),
          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
        ),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: AppTheme.todayColor.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(
            item.urgencyLabel,
            style: const TextStyle(
              color: AppTheme.todayColor,
              fontWeight: FontWeight.bold,
              fontSize: 11,
            ),
          ),
        ),
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => OpportunityDetailScreen(opportunityId: item.opportunityId),
            ),
          );
        },
      ),
    );
  }

  Widget _buildStatusChangeTile(DigestStatusChangeItem item) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: AppTheme.primaryColor.withValues(alpha: 0.12),
          child: const Icon(Icons.check, color: AppTheme.primaryColor, size: 18),
        ),
        title: Text(
          item.title,
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          'Moved to ${item.newStatus.toUpperCase()}${item.roundName != null ? " (${item.roundName})" : ""}',
          style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
        ),
        trailing: const Icon(Icons.chevron_right, size: 18),
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => OpportunityDetailScreen(opportunityId: item.opportunityId),
            ),
          );
        },
      ),
    );
  }
}
