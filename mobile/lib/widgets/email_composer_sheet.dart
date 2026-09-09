import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config/theme.dart';
import '../models/email_draft.dart';
import '../providers/accounts_provider.dart';
import '../services/account_service.dart';
import '../services/api_client.dart';
import '../services/email_composer_service.dart';

/// CareerMail AI — Interactive Email Composer Bottom Sheet.
///
/// Features:
///   • Sender Account dropdown selector (multi-account support)
///   • Natural language instruction field with quick suggestion chips
///   • Generate draft with loading progress indication
///   • Editable To, Cc, Bcc, Subject, and Body fields
///   • Save Draft to connected Gmail account
///   • Explicit Confirmation Modal before sending
///   • Re-authorization handling for accounts needing compose/send scope
class EmailComposerSheet extends StatefulWidget {
  final int opportunityId;
  final String opportunityTitle;
  final String? organization;
  final String? initialInstruction;
  final VoidCallback? onEmailSent;
  final EmailComposerService? composerService;
  final AccountService? accountService;

  const EmailComposerSheet({
    super.key,
    required this.opportunityId,
    required this.opportunityTitle,
    this.organization,
    this.initialInstruction,
    this.onEmailSent,
    this.composerService,
    this.accountService,
  });

  @override
  State<EmailComposerSheet> createState() => _EmailComposerSheetState();
}

class _EmailComposerSheetState extends State<EmailComposerSheet> {
  late final EmailComposerService _composerService;
  late final AccountService _accountService;

  final TextEditingController _instructionController = TextEditingController();
  final TextEditingController _toController = TextEditingController();
  final TextEditingController _ccController = TextEditingController();
  final TextEditingController _bccController = TextEditingController();
  final TextEditingController _subjectController = TextEditingController();
  final TextEditingController _bodyController = TextEditingController();

  int? _selectedAccountId;
  String? _inReplyTo;
  String? _threadId;

  bool _isGenerating = false;
  bool _isSavingDraft = false;
  bool _isSending = false;
  bool _showCcBcc = false;
  bool _hasDraft = false;

  String? _errorMessage;
  bool _needsReauth = false;
  int? _reauthAccountId;

  static const List<String> _quickChips = [
    'Ask for extension',
    'Inquire about application status',
    'Confirm interview attendance',
    'Ask about remote / stipend',
    'Express interest',
  ];

  @override
  void initState() {
    super.initState();
    _composerService = widget.composerService ?? EmailComposerService();
    _accountService = widget.accountService ?? AccountService();

    if (widget.initialInstruction != null && widget.initialInstruction!.isNotEmpty) {
      _instructionController.text = widget.initialInstruction!;
    }
  }

  @override
  void dispose() {
    _instructionController.dispose();
    _toController.dispose();
    _ccController.dispose();
    _bccController.dispose();
    _subjectController.dispose();
    _bodyController.dispose();
    super.dispose();
  }

  void _applyChip(String chipText) {
    setState(() {
      _instructionController.text = chipText;
    });
  }

  List<String> _parseAddressList(String text) {
    if (text.trim().isEmpty) return const [];
    return text
        .split(RegExp(r'[,;]'))
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();
  }

  Future<void> _generateDraft() async {
    final instruction = _instructionController.text.trim();
    if (instruction.isEmpty) {
      setState(() {
        _errorMessage = 'Please describe what you want the email to say.';
      });
      return;
    }

    setState(() {
      _isGenerating = true;
      _errorMessage = null;
      _needsReauth = false;
    });

    try {
      final draft = await _composerService.generateDraft(
        opportunityId: widget.opportunityId,
        instruction: instruction,
        accountId: _selectedAccountId,
      );

      setState(() {
        _toController.text = draft.to.join(', ');
        _ccController.text = draft.cc.join(', ');
        _bccController.text = draft.bcc.join(', ');
        _subjectController.text = draft.subject;
        _bodyController.text = draft.bodyText;
        _inReplyTo = draft.inReplyTo;
        _threadId = draft.threadId;

        if (draft.suggestedAccountId != null && _selectedAccountId == null) {
          _selectedAccountId = draft.suggestedAccountId;
        }

        _hasDraft = true;
      });
    } on ReauthRequiredException catch (e) {
      setState(() {
        _needsReauth = true;
        _reauthAccountId = e.accountId ?? _selectedAccountId;
        _errorMessage = 'Your Gmail permissions need to be refreshed for drafting and sending.';
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      setState(() {
        _isGenerating = false;
      });
    }
  }

  Future<void> _saveDraft() async {
    final toList = _parseAddressList(_toController.text);
    final subject = _subjectController.text.trim();
    final body = _bodyController.text.trim();

    if (subject.isEmpty) {
      setState(() => _errorMessage = 'Please enter a subject.');
      return;
    }

    final accountId = _selectedAccountId ?? _getDefaultAccountId();
    if (accountId == null) {
      setState(() => _errorMessage = 'Please connect or select a Gmail account.');
      return;
    }

    setState(() {
      _isSavingDraft = true;
      _errorMessage = null;
      _needsReauth = false;
    });

    try {
      final draft = EmailDraft(
        to: toList,
        cc: _parseAddressList(_ccController.text),
        bcc: _parseAddressList(_bccController.text),
        subject: subject,
        bodyText: body,
        inReplyTo: _inReplyTo,
        threadId: _threadId,
      );

      final res = await _composerService.createGmailDraft(
        accountId: accountId,
        opportunityId: widget.opportunityId,
        draft: draft,
      );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('✓ Draft saved to Gmail (${res.subject})'),
            backgroundColor: Colors.green.shade700,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } on ReauthRequiredException catch (e) {
      setState(() {
        _needsReauth = true;
        _reauthAccountId = e.accountId ?? accountId;
        _errorMessage = 'Permission refresh required to create drafts in Gmail.';
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() => _isSavingDraft = false);
      }
    }
  }

  Future<void> _confirmAndSend() async {
    final toList = _parseAddressList(_toController.text);
    final subject = _subjectController.text.trim();
    final body = _bodyController.text.trim();

    if (toList.isEmpty) {
      setState(() => _errorMessage = 'Please provide at least one recipient email address.');
      return;
    }
    if (subject.isEmpty) {
      setState(() => _errorMessage = 'Please enter an email subject.');
      return;
    }
    if (body.isEmpty) {
      setState(() => _errorMessage = 'Email body cannot be empty.');
      return;
    }

    final accountId = _selectedAccountId ?? _getDefaultAccountId();
    if (accountId == null) {
      setState(() => _errorMessage = 'Please select an account to send from.');
      return;
    }

    final accounts = Provider.of<AccountsProvider>(context, listen: false).accounts;
    final senderEmail = accounts.any((a) => a.id == accountId)
        ? accounts.firstWhere((a) => a.id == accountId).emailAddress
        : (accounts.isNotEmpty ? accounts.first.emailAddress : 'Connected Gmail Account');

    // Explicit user confirmation modal before sending
    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialogCtx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.warning_amber_rounded, color: Colors.orange),
            SizedBox(width: 8),
            Text('Confirm Email Send'),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Are you sure you want to send this email now? This will deliver the message immediately via your Gmail account.',
              style: TextStyle(fontSize: 14),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.grey.shade100,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('From: $senderEmail', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                  Text('To: ${toList.join(", ")}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                  Text('Subject: $subject', style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
                ],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogCtx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryColor),
            onPressed: () => Navigator.pop(dialogCtx, true),
            child: const Text('Send Now'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    setState(() {
      _isSending = true;
      _errorMessage = null;
      _needsReauth = false;
    });

    try {
      await _composerService.sendEmail(
        accountId: accountId,
        opportunityId: widget.opportunityId,
        to: toList,
        cc: _parseAddressList(_ccController.text),
        bcc: _parseAddressList(_bccController.text),
        subject: subject,
        bodyText: body,
        inReplyTo: _inReplyTo,
        threadId: _threadId,
        confirmed: true,
      );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('✓ Email sent to ${toList.first}!'),
            backgroundColor: Colors.green.shade700,
            behavior: SnackBarBehavior.floating,
          ),
        );
        widget.onEmailSent?.call();
        Navigator.pop(context);
      }
    } on ReauthRequiredException catch (e) {
      setState(() {
        _needsReauth = true;
        _reauthAccountId = e.accountId ?? accountId;
        _errorMessage = 'Permission refresh required to send emails via Gmail.';
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() => _isSending = false);
      }
    }
  }

  int? _getDefaultAccountId() {
    final accounts = Provider.of<AccountsProvider>(context, listen: false).accounts;
    if (accounts.isNotEmpty) return accounts.first.id;
    return null;
  }

  Future<void> _startReauth() async {
    try {
      final authUrl = await _accountService.getOAuthStartUrl();
      final uri = Uri.parse(authUrl);
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Please grant permissions in browser, then return to CareerMail AI.'),
            ),
          );
        }
      }
    } catch (e) {
      setState(() => _errorMessage = 'Could not launch Google authorization: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final accounts = Provider.of<AccountsProvider>(context).accounts;
    if (_selectedAccountId == null && accounts.isNotEmpty) {
      _selectedAccountId = accounts.first.id;
    }

    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
        top: 16,
        left: 16,
        right: 16,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.auto_awesome, color: AppTheme.primaryColor, size: 20),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'AI Email Copilot',
                        style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
                      ),
                      Text(
                        widget.opportunityTitle,
                        style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
            const Divider(height: 24),

            // Account selection dropdown (Multi-account support)
            if (accounts.isNotEmpty) ...[
              Row(
                children: [
                  const Text('Send from: ', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10),
                      decoration: BoxDecoration(
                        border: Border.all(color: Colors.grey.shade300),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: DropdownButtonHideUnderline(
                        child: DropdownButton<int>(
                          value: _selectedAccountId,
                          isExpanded: true,
                          items: accounts.map((acc) {
                            return DropdownMenuItem<int>(
                              value: acc.id,
                              child: Text(
                                acc.emailAddress,
                                style: const TextStyle(fontSize: 13),
                                overflow: TextOverflow.ellipsis,
                              ),
                            );
                          }).toList(),
                          onChanged: (val) => setState(() => _selectedAccountId = val),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
            ],

            // Re-authorization Card
            if (_needsReauth) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                margin: const EdgeInsets.only(bottom: 12),
                decoration: BoxDecoration(
                  color: Colors.amber.shade50,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: Colors.amber.shade300),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.lock_reset, color: Colors.brown, size: 18),
                        SizedBox(width: 8),
                        Text(
                          'Gmail Permission Refresh Required',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.brown),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Your Gmail permissions need to be refreshed to create drafts and send messages.',
                      style: TextStyle(fontSize: 12, color: Colors.black87),
                    ),
                    if (_reauthAccountId != null) ...[
                      const SizedBox(height: 6),
                      Text(
                        'Account requiring re-authorization: ${accounts.where((a) => a.id == _reauthAccountId).map((a) => a.emailAddress).firstOrNull ?? "Selected account"}',
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.brown),
                      ),
                    ],
                    const SizedBox(height: 8),
                    FilledButton.icon(
                      style: FilledButton.styleFrom(backgroundColor: Colors.brown),
                      onPressed: _startReauth,
                      icon: const Icon(Icons.open_in_browser, size: 16),
                      label: const Text('Re-authorize with Google', style: TextStyle(fontSize: 12)),
                    ),
                  ],
                ),
              ),
            ],

            // Error Banner
            if (_errorMessage != null && !_needsReauth) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                margin: const EdgeInsets.only(bottom: 12),
                decoration: BoxDecoration(
                  color: Colors.red.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.red.shade200),
                ),
                child: Text(
                  _errorMessage!,
                  style: TextStyle(color: Colors.red.shade900, fontSize: 13),
                ),
              ),
            ],

            // Natural Language Prompt Section
            const Text(
              'What do you want to say?',
              style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
            ),
            const SizedBox(height: 6),
            TextField(
              controller: _instructionController,
              decoration: InputDecoration(
                hintText: 'e.g. Ask them if I can submit after the deadline...',
                hintStyle: TextStyle(fontSize: 13, color: Colors.grey.shade400),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                contentPadding: const EdgeInsets.all(12),
              ),
              maxLines: 2,
            ),
            const SizedBox(height: 8),

            // Suggestion Chips
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: _quickChips.map((chip) {
                return ActionChip(
                  label: Text(chip, style: const TextStyle(fontSize: 11)),
                  backgroundColor: Colors.grey.shade100,
                  onPressed: () => _applyChip(chip),
                );
              }).toList(),
            ),
            const SizedBox(height: 12),

            // Generate Button
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _isGenerating ? null : _generateDraft,
                icon: _isGenerating
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.auto_awesome, size: 16),
                label: Text(_isGenerating ? 'Drafting your email...' : (_hasDraft ? 'Regenerate Draft' : 'Generate Draft with AI')),
              ),
            ),

            // Draft Editor Section
            if (_hasDraft) ...[
              const Divider(height: 28),
              Row(
                children: [
                  const Text(
                    'REVIEW & EDIT DRAFT',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: Colors.grey),
                  ),
                  const Spacer(),
                  TextButton(
                    onPressed: () => setState(() => _showCcBcc = !_showCcBcc),
                    child: Text(_showCcBcc ? 'Hide Cc/Bcc' : 'Show Cc/Bcc', style: const TextStyle(fontSize: 11)),
                  ),
                ],
              ),
              const SizedBox(height: 6),

              // To field
              TextField(
                controller: _toController,
                decoration: InputDecoration(
                  labelText: 'To',
                  hintText: 'recruiter@company.com',
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                ),
              ),
              const SizedBox(height: 8),

              // Optional Cc / Bcc fields
              if (_showCcBcc) ...[
                TextField(
                  controller: _ccController,
                  decoration: InputDecoration(
                    labelText: 'Cc',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _bccController,
                  decoration: InputDecoration(
                    labelText: 'Bcc',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  ),
                ),
                const SizedBox(height: 8),
              ],

              // Subject field
              TextField(
                controller: _subjectController,
                decoration: InputDecoration(
                  labelText: 'Subject',
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                ),
              ),
              const SizedBox(height: 8),

              // Body field
              TextField(
                controller: _bodyController,
                decoration: InputDecoration(
                  labelText: 'Body',
                  alignLabelWithHint: true,
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                  contentPadding: const EdgeInsets.all(12),
                ),
                minLines: 6,
                maxLines: 12,
              ),
              const SizedBox(height: 16),

              // Bottom Action Buttons
              Row(
                children: [
                  // Save as Draft
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: (_isSavingDraft || _isSending) ? null : _saveDraft,
                      icon: _isSavingDraft
                          ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.save_outlined, size: 16),
                      label: Text(_isSavingDraft ? 'Saving...' : 'Save Draft'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  // Send Email
                  Expanded(
                    child: FilledButton.icon(
                      style: FilledButton.styleFrom(backgroundColor: AppTheme.primaryColor),
                      onPressed: (_isSavingDraft || _isSending) ? null : _confirmAndSend,
                      icon: _isSending
                          ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Icon(Icons.send_rounded, size: 16),
                      label: Text(_isSending ? 'Sending...' : 'Send Email'),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
