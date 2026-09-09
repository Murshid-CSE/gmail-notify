import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../config/theme.dart';
import '../models/deadline.dart';
import '../screens/opportunity_detail_screen.dart';
import 'priority_badge.dart';
import 'status_badge.dart';

/// CareerMail AI — Deadline Card Item Widget.
class DeadlineCard extends StatelessWidget {
  final DeadlineCardItem item;

  const DeadlineCard({super.key, required this.item});

  String _formatDeadline() {
    if (item.isOverdue) return 'Overdue';
    if (item.isDueToday) return 'Today';
    if (item.isDueTomorrow) return 'Tomorrow';
    if (item.daysRemaining != null) {
      return '${item.daysRemaining}d left';
    }
    if (item.deadline != null) {
      return DateFormat('MMM d').format(item.deadline!);
    }
    return 'No date';
  }

  Color _getUrgencyColor() {
    if (item.isOverdue) return AppTheme.overdueColor;
    if (item.isDueToday) return AppTheme.todayColor;
    if (item.isDueTomorrow) return AppTheme.tomorrowColor;
    return AppTheme.upcomingColor;
  }

  @override
  Widget build(BuildContext context) {
    final urgencyColor = _getUrgencyColor();
    final deadlineLabel = _formatDeadline();
    final catColor = AppTheme.getCategoryColor(item.category);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => OpportunityDetailScreen(opportunityId: item.id),
            ),
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Urgency Badge / Countdown block on the left
              Container(
                width: 60,
                padding: const EdgeInsets.symmetric(vertical: 8),
                decoration: BoxDecoration(
                  color: urgencyColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: urgencyColor.withValues(alpha: 0.3)),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.event_outlined, size: 16, color: urgencyColor),
                    const SizedBox(height: 3),
                    Text(
                      deadlineLabel,
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: urgencyColor,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),

              // Title, Organization & Status
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            item.title,
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        const SizedBox(width: 6),
                        PriorityBadge(priority: item.priority),
                      ],
                    ),
                    if (item.organization != null && item.organization!.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(
                        item.organization!,
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    ],
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        StatusBadge(status: item.status),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: catColor.withValues(alpha: 0.08),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            item.category.toUpperCase(),
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w600,
                              color: catColor,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
