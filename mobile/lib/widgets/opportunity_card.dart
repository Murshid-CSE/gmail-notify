import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../config/theme.dart';
import '../models/opportunity.dart';
import '../screens/opportunity_detail_screen.dart';
import 'priority_badge.dart';
import 'status_badge.dart';

/// CareerMail AI — Opportunity Card.
class OpportunityCard extends StatelessWidget {
  final Opportunity opportunity;

  const OpportunityCard({super.key, required this.opportunity});

  String _formatDeadline() {
    if (opportunity.isOverdue) return 'Overdue';
    if (opportunity.isDueToday) return 'Due today';
    if (opportunity.isDueTomorrow) return 'Due tomorrow';
    if (opportunity.daysRemaining != null) {
      return 'Due in ${opportunity.daysRemaining} days';
    }
    if (opportunity.deadline != null) {
      return DateFormat('MMM d').format(opportunity.deadline!);
    }
    return '';
  }

  @override
  Widget build(BuildContext context) {
    final catColor = AppTheme.getCategoryColor(opportunity.category);
    final catIcon = AppTheme.getCategoryIcon(opportunity.category);
    final deadlineText = _formatDeadline();

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => OpportunityDetailScreen(opportunityId: opportunity.id),
            ),
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Top Row: Category icon, Organization & Priority
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: catColor.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Icon(catIcon, size: 16, color: catColor),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      opportunity.organization ?? opportunity.category.toUpperCase(),
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: Colors.grey.shade600,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  PriorityBadge(priority: opportunity.priority),
                ],
              ),
              const SizedBox(height: 8),

              // Title
              Text(
                opportunity.title,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  height: 1.25,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 10),

              // Status and Deadline Badges Row
              Row(
                children: [
                  StatusBadge(
                    status: opportunity.status,
                    roundName: opportunity.roundName,
                  ),
                  const Spacer(),
                  if (deadlineText.isNotEmpty) ...[
                    Icon(
                      Icons.schedule,
                      size: 14,
                      color: opportunity.isOverdue
                          ? AppTheme.overdueColor
                          : opportunity.isDueToday
                              ? AppTheme.todayColor
                              : Colors.grey.shade600,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      deadlineText,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: opportunity.isOverdue
                            ? AppTheme.overdueColor
                            : opportunity.isDueToday
                                ? AppTheme.todayColor
                                : Colors.grey.shade700,
                      ),
                    ),
                  ],
                ],
              ),

              // Action required highlighted banner if present
              if (opportunity.actionRequired && opportunity.action != null) ...[
                const SizedBox(height: 10),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFEF3C7),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: const Color(0xFFFDE68A)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.bolt, size: 16, color: Color(0xFFB45309)),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          opportunity.action!,
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF92400E),
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
