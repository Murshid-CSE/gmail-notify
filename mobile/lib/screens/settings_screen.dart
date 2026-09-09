import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../config/api_config.dart';
import '../config/theme.dart';
import '../models/account.dart';
import '../providers/accounts_provider.dart';
import '../providers/deadlines_provider.dart';
import '../providers/digest_provider.dart';
import '../providers/opportunities_provider.dart';
import '../providers/scheduler_provider.dart';
import '../services/account_service.dart';
import '../services/notification_service.dart';

/// CareerMail AI — Settings Screen.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final TextEditingController _urlController = TextEditingController();
  final ApiConfig _apiConfig = ApiConfig();
  bool _isSendingTest = false;
  bool _isRegisteringDevice = false;
  bool _isConnectingOAuth = false;
  Timer? _oauthPollTimer;

  @override
  void initState() {

    super.initState();
    _urlController.text = _apiConfig.baseUrl;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AccountsProvider>().fetchAccounts();
      context.read<SchedulerProvider>().fetchStatus();
    });
  }

  @override
  void dispose() {
    _oauthPollTimer?.cancel();
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _handleAddAccount() async {
    final initialCount = context.read<AccountsProvider>().accounts.length;
    setState(() => _isConnectingOAuth = true);
    final accountService = AccountService();
    try {
      final url = await accountService.getOAuthStartUrl();
      final launched = await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
      if (!mounted) return;
      if (!launched) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open browser for Google sign-in')),
        );
        setState(() => _isConnectingOAuth = false);
        return;
      }

      _oauthPollTimer?.cancel();
      _oauthPollTimer = Timer.periodic(const Duration(seconds: 2), (timer) async {
        try {
          final accounts = await accountService.getAccounts();
          if (accounts.length > initialCount) {
            timer.cancel();
            if (mounted) {
              setState(() => _isConnectingOAuth = false);
              context.read<AccountsProvider>().fetchAccounts();
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('New Gmail account connected successfully!')),
              );
            }
          }
        } catch (_) {}
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to start Google sign-in: $e')),
        );
        setState(() => _isConnectingOAuth = false);
      }
    }
  }

  void _saveUrl() {
    final newUrl = _urlController.text.trim();
    if (newUrl.isNotEmpty) {
      _apiConfig.setBaseUrl(newUrl);

      // Refresh all providers with new base URL
      context.read<DigestProvider>().refresh();
      context.read<OpportunitiesProvider>().fetchOpportunities(refresh: true);
      context.read<DeadlinesProvider>().refresh();
      context.read<AccountsProvider>().fetchAccounts();
      context.read<SchedulerProvider>().fetchStatus();

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('API URL updated to: ${_apiConfig.baseUrl}')),
      );
    }
  }

  void _resetUrl() {
    _apiConfig.resetToDefault();
    setState(() {
      _urlController.text = _apiConfig.baseUrl;
    });

    context.read<DigestProvider>().refresh();
    context.read<OpportunitiesProvider>().fetchOpportunities(refresh: true);
    context.read<DeadlinesProvider>().refresh();
    context.read<AccountsProvider>().fetchAccounts();
    context.read<SchedulerProvider>().fetchStatus();

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Reset to default: ${_apiConfig.baseUrl}')),
    );
  }

  Future<void> _handleSyncNow() async {
    final provider = context.read<AccountsProvider>();
    await provider.syncAll();
    if (!mounted) return;

    if (provider.errorMessage != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(provider.errorMessage!),
          backgroundColor: AppTheme.overdueColor,
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Sync completed successfully! Updating feeds...'),
          backgroundColor: AppTheme.internshipColor,
        ),
      );
      // Refresh feeds
      context.read<DigestProvider>().refresh();
      context.read<OpportunitiesProvider>().fetchOpportunities(refresh: true);
      context.read<DeadlinesProvider>().refresh();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
      ),
      body: Consumer<AccountsProvider>(
        builder: (context, provider, child) {
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // 1. Connected Accounts Section
              _buildSectionHeader('CONNECTED GMAIL ACCOUNTS'),
              const SizedBox(height: 8),

              if (provider.isLoading && provider.accounts.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 24),
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (provider.accounts.isEmpty)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.info_outline, color: Colors.grey),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                'No Gmail accounts connected yet.',
                                style: TextStyle(fontSize: 13, color: Colors.grey.shade700),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton.icon(
                            key: const Key('settingsConnectAccountButton'),
                            onPressed: _isConnectingOAuth ? null : _handleAddAccount,
                            icon: _isConnectingOAuth
                                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                                : const Icon(Icons.add, size: 16),
                            label: Text(_isConnectingOAuth ? 'Waiting for Google sign-in...' : 'Connect Gmail Account'),
                          ),
                        ),
                      ],
                    ),
                  ),
                )
              else ...[
                ...provider.accounts.map((acc) => _buildAccountCard(acc, provider)),
                if (provider.accounts.length < 2) ...[
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      key: const Key('addSecondAccountButton'),
                      onPressed: _isConnectingOAuth ? null : _handleAddAccount,
                      icon: _isConnectingOAuth
                          ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.add_rounded, size: 18),
                      label: Text(_isConnectingOAuth ? 'Waiting for Google sign-in...' : 'Add Second Gmail Account'),
                    ),
                  ),
                ],
              ],

              const SizedBox(height: 12),

              // Sync Now Button
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: provider.isSyncing ? null : _handleSyncNow,
                  icon: provider.isSyncing
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(Icons.sync, size: 18),
                  label: Text(provider.isSyncing ? 'Syncing Ingested Emails...' : 'Sync Now'),
                  style: FilledButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
              ),

              const SizedBox(height: 28),

              // 2. Automated Sync & Scheduling Section (Milestone 7)
              _buildSectionHeader('AUTOMATED SYNC & SCHEDULING'),
              const SizedBox(height: 8),
              _buildSchedulerCard(),

              const SizedBox(height: 28),

              // 3. Push Notifications Section (Milestone 6)
              _buildSectionHeader('PUSH NOTIFICATIONS'),
              const SizedBox(height: 8),
              _buildPushNotificationsCard(),

              const SizedBox(height: 28),

              // 4. API Configuration Section
              _buildSectionHeader('BACKEND API CONFIGURATION'),
              const SizedBox(height: 8),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Backend Service URL',
                        style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Emulator: http://10.0.2.2:8000 • Chrome/Desktop: http://localhost:8000',
                        style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: _urlController,
                        decoration: InputDecoration(
                          hintText: 'e.g. http://10.0.2.2:8000',
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          FilledButton(
                            onPressed: _saveUrl,
                            child: const Text('Save URL'),
                          ),
                          const SizedBox(width: 8),
                          OutlinedButton(
                            onPressed: _resetUrl,
                            child: const Text('Reset Default'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 28),

              // 4. Timezone & App Information Section
              _buildSectionHeader('PREFERENCES & ABOUT'),
              const SizedBox(height: 8),
              Card(
                child: Column(
                  children: [
                    ListTile(
                      leading: const Icon(Icons.public, size: 20),
                      title: const Text('Timezone', style: TextStyle(fontSize: 14)),
                      subtitle: Text(
                        _apiConfig.userTimezone,
                        style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                      ),
                    ),
                    const Divider(height: 1),
                    ListTile(
                      leading: const Icon(Icons.info_outline, size: 20),
                      title: const Text('CareerMail AI Version', style: TextStyle(fontSize: 14)),
                      subtitle: const Text('v1.0.0 (Milestone 6)', style: TextStyle(fontSize: 12, color: Colors.grey)),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 32),
            ],
          );
        },
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Text(
      title,
      style: const TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.bold,
        letterSpacing: 0.6,
        color: Colors.grey,
      ),
    );
  }

  Widget _buildAccountCard(EmailAccount account, AccountsProvider provider) {
    final syncStr = account.lastSyncAt != null
        ? DateFormat('MMM d, h:mm a').format(account.lastSyncAt!)
        : 'Never synced';

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: AppTheme.primaryColor.withValues(alpha: 0.12),
          child: const Icon(Icons.mail, color: AppTheme.primaryColor, size: 18),
        ),
        title: Text(
          account.emailAddress,
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
        ),
        subtitle: Text(
          'Last sync: $syncStr',
          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              icon: const Icon(Icons.lock_reset, size: 20, color: Colors.grey),
              tooltip: 'Re-authorize permissions for Copilot',
              onPressed: _handleAddAccount,
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: account.isActive
                    ? const Color(0xFF059669).withValues(alpha: 0.12)
                    : Colors.grey.shade200,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                account.isActive ? 'ACTIVE' : 'INACTIVE',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  color: account.isActive ? const Color(0xFF059669) : Colors.grey,
                ),
              ),
            ),
          ],
        ),
      ),
    );

  }

  Widget _buildPushNotificationsCard() {
    return Consumer<NotificationService>(
      builder: (context, notif, _) {
        final isRegistered = notif.status.isRegistered;
        final prefs = notif.preferences;

        return Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Status Header Row
                Row(
                  children: [
                    Icon(
                      isRegistered ? Icons.notifications_active : Icons.notifications_off_outlined,
                      color: isRegistered ? const Color(0xFF059669) : Colors.grey,
                      size: 22,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Status',
                            style: TextStyle(fontSize: 12, color: Colors.grey),
                          ),
                          Text(
                            isRegistered ? 'Registered with Backend' : 'Not Registered',
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              color: isRegistered ? const Color(0xFF059669) : Colors.grey.shade700,
                            ),
                          ),
                        ],
                      ),
                    ),
                    if (!isRegistered)
                      OutlinedButton(
                        onPressed: _isRegisteringDevice ? null : () => _handleRegisterDevice(notif),
                        child: _isRegisteringDevice
                            ? const SizedBox(
                                width: 14,
                                height: 14,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Text('Register'),
                      )
                    else
                      TextButton(
                        onPressed: () => notif.unregisterDevice(),
                        child: const Text('Deactivate', style: TextStyle(color: Colors.red, fontSize: 12)),
                      ),
                  ],
                ),

                if (!notif.status.permissionGranted) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: Colors.amber.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.amber.shade200),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.warning_amber_rounded, color: Colors.amber.shade800, size: 20),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Notifications disabled. Enable them in system settings to receive alerts.',
                            style: TextStyle(fontSize: 12, color: Colors.amber.shade900),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],

                const SizedBox(height: 14),

                // Send Test Notification Button
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: _isSendingTest ? null : () => _handleSendTestNotification(notif),
                    icon: _isSendingTest
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Icon(Icons.send_rounded, size: 16),
                    label: Text(_isSendingTest ? 'Sending Test Push...' : 'Send Test Notification'),
                    style: FilledButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
                ),

                const Divider(height: 28),

                const Text(
                  'Notification Categories',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 4),

                SwitchListTile.adaptive(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Urgent Actions', style: TextStyle(fontSize: 13)),
                  subtitle: const Text('Alerts when immediate student action is required', style: TextStyle(fontSize: 11, color: Colors.grey)),
                  value: prefs.urgentActions,
                  onChanged: (val) {
                    notif.updatePreferences(prefs.copyWith(urgentActions: val));
                  },
                ),
                SwitchListTile.adaptive(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Approaching Deadlines', style: TextStyle(fontSize: 13)),
                  subtitle: const Text('Alerts for deadlines today or tomorrow', style: TextStyle(fontSize: 11, color: Colors.grey)),
                  value: prefs.approachingDeadlines,
                  onChanged: (val) {
                    notif.updatePreferences(prefs.copyWith(approachingDeadlines: val));
                  },
                ),
                SwitchListTile.adaptive(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Status Updates', style: TextStyle(fontSize: 13)),
                  subtitle: const Text('Interview, shortlist, or selection updates', style: TextStyle(fontSize: 11, color: Colors.grey)),
                  value: prefs.statusUpdates,
                  onChanged: (val) {
                    notif.updatePreferences(prefs.copyWith(statusUpdates: val));
                  },
                ),
                SwitchListTile.adaptive(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Daily Brief', style: TextStyle(fontSize: 13)),
                  subtitle: const Text('Concise summary of your career activity', style: TextStyle(fontSize: 11, color: Colors.grey)),
                  value: prefs.dailyBrief,
                  onChanged: (val) {
                    notif.updatePreferences(prefs.copyWith(dailyBrief: val));
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _handleRegisterDevice(NotificationService notif) async {
    setState(() => _isRegisteringDevice = true);
    final mockToken = 'dev-device-${DateTime.now().millisecondsSinceEpoch}';
    final ok = await notif.registerDevice(
      fcmToken: mockToken,
      deviceName: 'Flutter Mobile Client',
      deviceType: 'android',
    );
    if (!mounted) return;
    setState(() => _isRegisteringDevice = false);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(ok ? 'Device registered successfully with CareerMail backend!' : 'Failed to register device.'),
        backgroundColor: ok ? const Color(0xFF059669) : Colors.red,
      ),
    );
  }

  Future<void> _handleSendTestNotification(NotificationService notif) async {
    setState(() => _isSendingTest = true);
    try {
      final res = await notif.sendTestNotification();
      if (!mounted) return;
      setState(() => _isSendingTest = false);

      final status = res['status'] ?? 'mock_sent';
      final detail = res['detail'] ?? 'Test notification triggered!';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('[$status] $detail'),
          backgroundColor: const Color(0xFF059669),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _isSendingTest = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to send test notification: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Widget _buildSchedulerCard() {
    return Consumer<SchedulerProvider>(
      builder: (context, scheduler, _) {
        final status = scheduler.status;
        final syncInterval = status?.syncIntervalMinutes ?? 15;
        final digestTime = status?.dailyDigestTime ?? '08:00';
        final tz = status?.timezone ?? 'Asia/Kolkata';

        String nextSyncStr = 'Every $syncInterval min';
        if (status != null && status.syncJob?.nextRunTime != null) {
          nextSyncStr = DateFormat('MMM d, h:mm a').format(status.syncJob!.nextRunTime!.toLocal());
        } else if (status?.isPaused == true) {
          nextSyncStr = 'Paused';
        }

        String nextDigestStr = '$digestTime daily';
        if (status != null && status.digestJob?.nextRunTime != null) {
          nextDigestStr = DateFormat('MMM d, h:mm a').format(status.digestJob!.nextRunTime!.toLocal());
        } else if (status?.isPaused == true) {
          nextDigestStr = 'Paused';
        }

        return Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      status?.isRunning == true ? Icons.schedule : Icons.schedule_send,
                      color: AppTheme.primaryColor,
                      size: 22,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Background Automation',
                            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                          ),
                          Text(
                            status?.isRunning == true
                                ? 'Active & monitoring in background'
                                : 'Scheduler ready (manual or background)',
                            style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.refresh, size: 18),
                      tooltip: 'Refresh Status',
                      onPressed: scheduler.isLoading ? null : () => scheduler.fetchStatus(),
                    ),
                  ],
                ),
                const Divider(height: 24),
                _buildScheduleInfoRow('Automatic Sync', 'Every $syncInterval minutes'),
                const SizedBox(height: 8),
                _buildScheduleInfoRow('Daily Career Brief', '$digestTime AM'),
                const SizedBox(height: 8),
                _buildScheduleInfoRow('Timezone', tz),
                const SizedBox(height: 8),
                _buildScheduleInfoRow('Next Sync', nextSyncStr),
                const SizedBox(height: 8),
                _buildScheduleInfoRow('Next Daily Brief', nextDigestStr),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: FilledButton.icon(
                        onPressed: scheduler.isTriggeringSync ? null : () => _handleTriggerPipeline(scheduler),
                        icon: scheduler.isTriggeringSync
                            ? const SizedBox(
                                width: 14,
                                height: 14,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                              )
                            : const Icon(Icons.play_arrow_rounded, size: 16),
                        label: Text(scheduler.isTriggeringSync ? 'Running...' : 'Run Pipeline Now'),
                        style: FilledButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 10),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: scheduler.isTriggeringDigest ? null : () => _handleTriggerDigest(scheduler),
                        icon: scheduler.isTriggeringDigest
                            ? const SizedBox(
                                width: 14,
                                height: 14,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.auto_stories_rounded, size: 16),
                        label: Text(scheduler.isTriggeringDigest ? 'Briefing...' : 'Trigger Daily Brief'),
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 10),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildScheduleInfoRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(fontSize: 12, color: Colors.grey)),
        Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
      ],
    );
  }

  Future<void> _handleTriggerPipeline(SchedulerProvider scheduler) async {
    final res = await scheduler.triggerPipelineNow();
    if (!mounted) return;

    if (res != null && res['success'] == true) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(res['message']?.toString() ?? 'Pipeline completed successfully!'),
          backgroundColor: const Color(0xFF059669),
        ),
      );
      // Refresh user-facing feeds
      context.read<DigestProvider>().refresh();
      context.read<OpportunitiesProvider>().fetchOpportunities(refresh: true);
      context.read<DeadlinesProvider>().refresh();
      context.read<AccountsProvider>().fetchAccounts();
    } else {
      final msg = res?['message']?.toString() ?? scheduler.errorMessage ?? 'Pipeline run failed';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(msg),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _handleTriggerDigest(SchedulerProvider scheduler) async {
    final res = await scheduler.triggerDailyBriefNow();
    if (!mounted) return;

    if (res != null && res['success'] == true) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(res['message']?.toString() ?? 'Daily brief generated and sent!'),
          backgroundColor: const Color(0xFF059669),
        ),
      );
      context.read<DigestProvider>().refresh();
    } else {
      final msg = res?['message']?.toString() ?? scheduler.errorMessage ?? 'Daily brief trigger failed';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(msg),
          backgroundColor: Colors.red,
        ),
      );
    }
  }
}

