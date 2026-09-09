import 'package:flutter/material.dart';
import '../config/theme.dart';

/// CareerMail AI — Status Badge Widget.
class StatusBadge extends StatelessWidget {
  final String status;
  final String? roundName;

  const StatusBadge({
    super.key,
    required this.status,
    this.roundName,
  });

  String _formatStatus(String s) {
    if (s.isEmpty) return 'Opportunity';
    return s
        .split('_')
        .map((w) => w.isNotEmpty ? '${w[0].toUpperCase()}${w.substring(1)}' : '')
        .join(' ');
  }

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.getStatusColor(status);
    final text = roundName != null && roundName!.isNotEmpty
        ? '${_formatStatus(status)} ($roundName)'
        : _formatStatus(status);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.35), width: 0.8),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
