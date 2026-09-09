import 'package:flutter/material.dart';
import '../config/theme.dart';
import '../models/digest.dart';
import '../screens/opportunity_detail_screen.dart';
import 'priority_badge.dart';

/// CareerMail AI — Urgent Action Card.
class UrgentActionCard extends StatelessWidget {
  final DigestActionItem item;

  const UrgentActionCard({super.key, required this.item});

  String _formatDeadline() {
    if (item.isOverdue) return 'Overdue';
    if (item.daysRemaining == null) return '';
    if (item.daysRemaining == 0) return 'Due today';
    if (item.daysRemaining == 1) return 'Due tomorrow';
    return 'Due in ${item.daysRemaining} days';
  }

  @override
  Widget build(BuildContext context) {
    final deadlineText = _formatDeadline();
    final bool isCritical = item.isOverdue || item.priority == 'critical';
    final accentColor = isCritical ? AppTheme.overdueColor : AppTheme.urgentColor;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => OpportunityDetailScreen(opportunityId: item.opportunityId),
            ),
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.assignment_late_outlined, size: 18, color: accentColor),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      item.title,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: 8),
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
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: accentColor.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: accentColor.withValues(alpha: 0.25)),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        item.action,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: isCritical ? AppTheme.overdueColor : const Color(0xFFC2410C),
                        ),
                      ),
                    ),
                    if (deadlineText.isNotEmpty) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: accentColor,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          deadlineText,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
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
