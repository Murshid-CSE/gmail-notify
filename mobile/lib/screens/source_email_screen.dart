import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/email.dart';
import '../services/email_service.dart';
import '../widgets/error_state.dart';

/// CareerMail AI — Original Source Email Viewer.
class SourceEmailScreen extends StatefulWidget {
  final int emailId;

  const SourceEmailScreen({super.key, required this.emailId});

  @override
  State<SourceEmailScreen> createState() => _SourceEmailScreenState();
}

class _SourceEmailScreenState extends State<SourceEmailScreen> {
  final EmailService _service = EmailService();
  late Future<EmailDetail> _emailFuture;

  @override
  void initState() {
    super.initState();
    _loadEmail();
  }

  void _loadEmail() {
    _emailFuture = _service.getEmailDetail(widget.emailId);
  }

  Future<void> _openInGmail(EmailDetail email) async {
    final threadOrMsgId = email.gmailThreadId.isNotEmpty
        ? email.gmailThreadId
        : email.gmailMessageId;

    // Standard web URL for Gmail message/thread
    final webUri = Uri.parse('https://mail.google.com/mail/u/0/#inbox/$threadOrMsgId');
    final genericSearchUri = Uri.parse(
      'https://mail.google.com/mail/u/0/#search/${Uri.encodeComponent(email.subject)}',
    );

    try {
      final launched = await launchUrl(webUri, mode: LaunchMode.externalApplication);
      if (!launched) {
        final searchLaunched = await launchUrl(genericSearchUri, mode: LaunchMode.externalApplication);
        if (!searchLaunched && mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Could not open Gmail app. Please check Gmail in your browser.'),
            ),
          );
        }
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Could not open Gmail link.'),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Source Email'),
      ),
      body: FutureBuilder<EmailDetail>(
        future: _emailFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            return ErrorState(
              message: snapshot.error.toString(),
              onRetry: () {
                setState(() {
                  _loadEmail();
                });
              },
            );
          }

          final email = snapshot.data!;
          final formattedDate = DateFormat('EEE, MMM d, yyyy • h:mm a').format(email.receivedAt);

          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Subject
                Text(
                  email.subject,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    height: 1.3,
                  ),
                ),
                const SizedBox(height: 12),

                // Sender, Recipients & Date Card
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade100,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'From: ',
                            style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                          ),
                          Expanded(
                            child: Text(
                              email.sender,
                              style: const TextStyle(fontSize: 13),
                            ),
                          ),
                        ],
                      ),
                      if (email.recipients.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'To: ',
                              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                            ),
                            Expanded(
                              child: Text(
                                email.recipients.join(', '),
                                style: TextStyle(fontSize: 13, color: Colors.grey.shade800),
                              ),
                            ),
                          ],
                        ),
                      ],
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Text(
                            'Date: ',
                            style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                          ),
                          Text(
                            formattedDate,
                            style: TextStyle(fontSize: 13, color: Colors.grey.shade700),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),

                // Labels
                if (email.labels.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    children: email.labels.map((label) {
                      return Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.blueGrey.shade50,
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: Colors.blueGrey.shade200, width: 0.7),
                        ),
                        child: Text(
                          label,
                          style: TextStyle(fontSize: 11, color: Colors.blueGrey.shade700),
                        ),
                      );
                    }).toList(),
                  ),
                ],

                const SizedBox(height: 16),

                // Open in Gmail Action Button
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: () => _openInGmail(email),
                    icon: const Icon(Icons.open_in_new, size: 16),
                    label: const Text('Open in Gmail'),
                    style: FilledButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                ),

                const SizedBox(height: 20),
                const Divider(),
                const SizedBox(height: 10),

                // Source of truth label
                Row(
                  children: [
                    const Icon(Icons.verified_outlined, size: 16, color: Color(0xFF059669)),
                    const SizedBox(width: 6),
                    Text(
                      'ORIGINAL EMAIL BODY (Source of Truth)',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.5,
                        color: Colors.grey.shade700,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),

                // Email Body Text
                SelectableText(
                  email.bodyText?.isNotEmpty == true
                      ? email.bodyText!
                      : '(This email did not contain extractable plain text body content.)',
                  style: const TextStyle(
                    fontSize: 14,
                    height: 1.5,
                    fontFamily: 'monospace',
                  ),
                ),
                const SizedBox(height: 32),
              ],
            ),
          );
        },
      ),
    );
  }
}
