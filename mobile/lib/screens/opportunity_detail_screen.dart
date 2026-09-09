import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import '../config/theme.dart';
import '../models/opportunity.dart';
import '../models/email.dart';
import '../services/opportunity_service.dart';
import '../widgets/error_state.dart';
import '../widgets/priority_badge.dart';
import '../widgets/status_badge.dart';
import '../widgets/email_composer_sheet.dart';
import 'source_email_screen.dart';


/// CareerMail AI — Opportunity Detail Screen.
class OpportunityDetailScreen extends StatefulWidget {
  final int opportunityId;

  const OpportunityDetailScreen({super.key, required this.opportunityId});

  @override
  State<OpportunityDetailScreen> createState() => _OpportunityDetailScreenState();
}

class _OpportunityDetailScreenState extends State<OpportunityDetailScreen> {
  final OpportunityService _service = OpportunityService();
  late Future<Opportunity> _future;

  @override
  void initState() {
    super.initState();
    _loadDetail();
  }

  void _loadDetail() {
    _future = _service.getOpportunityDetail(widget.opportunityId);
  }

  Future<void> _openUrl(String url) async {
    final uri = Uri.tryParse(url);
    if (uri != null && await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not launch URL: $url')),
      );
    }
  }

  void _openEmailComposer(Opportunity opp) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => EmailComposerSheet(
        opportunityId: opp.id,
        opportunityTitle: opp.title,
        organization: opp.organization,
        initialInstruction: opp.action != null && opp.actionRequired
            ? 'Follow up regarding: ${opp.action}'
            : null,
        onEmailSent: () {
          setState(() {
            _loadDetail();
          });
        },
      ),
    );
  }

  @override

  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Opportunity Details'),
      ),
      body: FutureBuilder<Opportunity>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            return ErrorState(
              message: snapshot.error.toString(),
              onRetry: () => setState(() => _loadDetail()),
            );
          }

          final opp = snapshot.data!;
          final catColor = AppTheme.getCategoryColor(opp.category);
          final catIcon = AppTheme.getCategoryIcon(opp.category);

          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Category & Priority row
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: catColor.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Row(
                        children: [
                          Icon(catIcon, size: 14, color: catColor),
                          const SizedBox(width: 4),
                          Text(
                            opp.category.toUpperCase(),
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                              color: catColor,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Spacer(),
                    PriorityBadge(priority: opp.priority),
                  ],
                ),
                const SizedBox(height: 10),

                // Title
                Text(
                  opp.title,
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    height: 1.25,
                  ),
                ),
                if (opp.organization != null && opp.organization!.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    opp.organization!,
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey.shade700,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
                const SizedBox(height: 12),

                // Current Status Badge
                StatusBadge(status: opp.status, roundName: opp.roundName),
                const SizedBox(height: 16),

                // Action Required Callout Box
                if (opp.actionRequired && opp.action != null) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFFFBEB),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: const Color(0xFFFDE68A), width: 1.2),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.bolt, color: Color(0xFFB45309), size: 18),
                            SizedBox(width: 6),
                            Text(
                              'ACTION REQUIRED',
                              style: TextStyle(
                                color: Color(0xFFB45309),
                                fontWeight: FontWeight.bold,
                                fontSize: 12,
                                letterSpacing: 0.5,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text(
                          opp.action!,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF78350F),
                            height: 1.3,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                ],

                // Metadata Details Card (Deadline, Location, Eligibility, Event Date)
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade50,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.grey.shade200),
                  ),
                  child: Column(
                    children: [
                      if (opp.deadline != null) ...[
                        _buildMetaRow(
                          Icons.schedule,
                          'Deadline',
                          '${DateFormat('EEE, MMM d, yyyy • h:mm a').format(opp.deadline!)} '
                              '${opp.isOverdue ? "(Overdue)" : opp.daysRemaining != null ? "(${opp.daysRemaining}d left)" : ""}',
                          textColor: opp.isOverdue ? AppTheme.overdueColor : null,
                        ),
                      ],
                      if (opp.eventDate != null) ...[
                        const Divider(height: 16),
                        _buildMetaRow(Icons.event, 'Event Date', opp.eventDate!),
                      ],
                      if (opp.location != null) ...[
                        const Divider(height: 16),
                        _buildMetaRow(Icons.place_outlined, 'Location', opp.location!),
                      ],
                      if (opp.eligibility != null) ...[
                        const Divider(height: 16),
                        _buildMetaRow(Icons.verified_user_outlined, 'Eligibility', opp.eligibility!),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 16),

                // AI Email Copilot Card
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        AppTheme.primaryColor.withValues(alpha: 0.08),
                        AppTheme.primaryColor.withValues(alpha: 0.03),
                      ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: AppTheme.primaryColor.withValues(alpha: 0.25)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(6),
                            decoration: BoxDecoration(
                              color: AppTheme.primaryColor,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const Icon(Icons.auto_awesome, color: Colors.white, size: 16),
                          ),
                          const SizedBox(width: 8),
                          const Text(
                            'AI Email Copilot',
                            style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: AppTheme.primaryColor),
                          ),
                          const Spacer(),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: AppTheme.primaryColor.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: const Text(
                              'Draft & Send',
                              style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: AppTheme.primaryColor),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Generate a tailored email or inquiry in natural language, review the draft, and send or save directly in Gmail.',
                        style: TextStyle(fontSize: 13, color: Colors.grey.shade700, height: 1.3),
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton.icon(
                          style: FilledButton.styleFrom(
                            backgroundColor: AppTheme.primaryColor,
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                          onPressed: () => _openEmailComposer(opp),
                          icon: const Icon(Icons.edit_note_rounded, size: 18),
                          label: const Text('Draft Email with Copilot'),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),


                // External Links (Apply Now / Event URL)
                if (opp.applyUrl != null || opp.eventUrl != null) ...[
                  Row(
                    children: [
                      if (opp.applyUrl != null)
                        Expanded(
                          child: FilledButton.icon(
                            onPressed: () => _openUrl(opp.applyUrl!),
                            icon: const Icon(Icons.open_in_browser, size: 16),
                            label: const Text('Apply / Portal'),
                          ),
                        ),
                      if (opp.applyUrl != null && opp.eventUrl != null)
                        const SizedBox(width: 10),
                      if (opp.eventUrl != null)
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: () => _openUrl(opp.eventUrl!),
                            icon: const Icon(Icons.link, size: 16),
                            label: const Text('Event Info'),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 24),
                ],

                // Status History Timeline
                if (opp.statusHistory.isNotEmpty) ...[
                  const Text(
                    'STATUS PROGRESSION',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 0.5,
                      color: Colors.grey,
                    ),
                  ),
                  const SizedBox(height: 12),
                  _buildStatusTimeline(opp.statusHistory),
                  const SizedBox(height: 24),
                ],

                // Source Emails Section
                const Text(
                  'SOURCE EMAILS (Truth)',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0.5,
                    color: Colors.grey,
                  ),
                ),
                const SizedBox(height: 8),
                if (opp.sourceEmails.isEmpty)
                  const Text('No source emails linked.')
                else
                  ...opp.sourceEmails.map((email) => _buildSourceEmailTile(email)),

                const SizedBox(height: 32),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildMetaRow(IconData icon, String label, String value, {Color? textColor}) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 16, color: Colors.grey.shade600),
        const SizedBox(width: 8),
        Text(
          '$label: ',
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
        ),
        Expanded(
          child: Text(
            value,
            style: TextStyle(fontSize: 13, color: textColor ?? Colors.grey.shade800),
          ),
        ),
      ],
    );
  }

  Widget _buildStatusTimeline(List<StatusHistoryItem> history) {
    return Column(
      children: List.generate(history.length, (index) {
        final item = history[index];
        final isLast = index == history.length - 1;
        final dateStr = DateFormat('MMM d, h:mm a').format(item.changedAt);

        return IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Indicator line & dot
              Column(
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                      color: isLast ? AppTheme.primaryColor : Colors.grey.shade400,
                      shape: BoxShape.circle,
                    ),
                  ),
                  if (!isLast)
                    Expanded(
                      child: Container(
                        width: 2,
                        color: Colors.grey.shade300,
                      ),
                    ),
                ],
              ),
              const SizedBox(width: 12),
              // Content
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            item.newStatus.toUpperCase(),
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.bold,
                              color: isLast ? AppTheme.primaryColor : Colors.black87,
                            ),
                          ),
                          const Spacer(),
                          Text(
                            dateStr,
                            style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                          ),
                        ],
                      ),
                      if (item.oldStatus != null) ...[
                        const SizedBox(height: 2),
                        Text(
                          'Transitioned from ${item.oldStatus}',
                          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      }),
    );
  }

  Widget _buildSourceEmailTile(SourceEmailReference email) {
    final dateStr = DateFormat('MMM d, yyyy').format(email.receivedAt);

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      elevation: 0,
      color: Colors.grey.shade100,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: const Icon(Icons.mail_outline, size: 20),
        title: Text(
          email.subject,
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          '${email.sender} • $dateStr',
          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        trailing: const Icon(Icons.chevron_right, size: 18),
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => SourceEmailScreen(emailId: email.id),
            ),
          );
        },
      ),
    );
  }
}
