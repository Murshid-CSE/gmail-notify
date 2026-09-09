import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../config/theme.dart';
import '../providers/accounts_provider.dart';
import '../providers/deadlines_provider.dart';
import '../providers/digest_provider.dart';
import '../providers/onboarding_provider.dart';
import '../providers/opportunities_provider.dart';
import 'main_navigation_screen.dart';

/// CareerMail AI — Interactive 4-Step Onboarding & Automated Initial Sync Wizard.
class OnboardingScreen extends StatelessWidget {
  const OnboardingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Consumer<OnboardingProvider>(
          builder: (context, provider, child) {
            return AnimatedSwitcher(
              duration: const Duration(milliseconds: 350),
              transitionBuilder: (child, animation) {
                return FadeTransition(
                  opacity: animation,
                  child: SlideTransition(
                    position: Tween<Offset>(
                      begin: const Offset(0.05, 0),
                      end: Offset.zero,
                    ).animate(animation),
                    child: child,
                  ),
                );
              },
              child: _buildStepContent(context, provider),
            );
          },
        ),
      ),
    );
  }

  Widget _buildStepContent(BuildContext context, OnboardingProvider provider) {
    switch (provider.currentStep) {
      case OnboardingStep.welcome:
        return const _WelcomeStepView(key: ValueKey('welcome'));
      case OnboardingStep.selectAccountCount:
        return const _AccountCountStepView(key: ValueKey('accountCount'));
      case OnboardingStep.connectAccounts:
        return const _ConnectAccountsStepView(key: ValueKey('connectAccounts'));
      case OnboardingStep.syncProgress:
        return const _SyncProgressStepView(key: ValueKey('syncProgress'));
      case OnboardingStep.completed:
        return const SizedBox.shrink(key: ValueKey('completed'));
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// STEP 1: WELCOME SCREEN
// ─────────────────────────────────────────────────────────────────────────────

class _WelcomeStepView extends StatelessWidget {
  const _WelcomeStepView({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 8),
          // Glowing CareerMail Brand Icon
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  AppTheme.primaryColor,
                  AppTheme.primaryColor.withValues(alpha: 0.75),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.primaryColor.withValues(alpha: 0.35),
                  blurRadius: 18,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: const Icon(
              Icons.mark_email_read_rounded,
              size: 40,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 28),

          Text(
            'CareerMail AI',
            style: theme.textTheme.headlineMedium?.copyWith(
              fontWeight: FontWeight.w800,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'Your career inbox,\norganized automatically.',
            style: theme.textTheme.titleLarge?.copyWith(
              color: isDark ? Colors.grey.shade300 : Colors.grey.shade800,
              height: 1.3,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 14),
          Text(
            'Connect your Gmail accounts to instantly discover career opportunities, track round deadlines, and extract actionable next steps.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 28),

          // Feature Highlights Cards
          _buildFeatureRow(
            Icons.military_tech_rounded,
            AppTheme.hackathonColor,
            'Hackathons & Competitions',
            'Find registrations, submission links & prize tracks',
          ),
          const SizedBox(height: 14),
          _buildFeatureRow(
            Icons.work_outline_rounded,
            AppTheme.internshipColor,
            'Internships & Jobs',
            'Track shortlist emails, tests, and offer letters',
          ),
          const SizedBox(height: 14),
          _buildFeatureRow(
            Icons.alarm_rounded,
            AppTheme.urgentColor,
            'Deadline Radar',
            'Prioritized notifications before applications close',
          ),

          const SizedBox(height: 32),

          // Get Started CTA
          SizedBox(
            width: double.infinity,
            height: 54,
            child: FilledButton(
              key: const Key('getStartedButton'),
              onPressed: () {
                context.read<OnboardingProvider>().goToAccountSelection();
              },
              style: FilledButton.styleFrom(
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    'Get Started',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  SizedBox(width: 8),
                  Icon(Icons.arrow_forward_rounded, size: 20),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
        ],
      ),
    );
  }

  Widget _buildFeatureRow(IconData icon, Color color, String title, String subtitle) {
    return Row(
      children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(icon, color: color, size: 22),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
              ),
              Text(
                subtitle,
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// STEP 2: ACCOUNT COUNT SELECTION
// ─────────────────────────────────────────────────────────────────────────────

class _AccountCountStepView extends StatelessWidget {
  const _AccountCountStepView({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final provider = context.watch<OnboardingProvider>();
    final selectedCount = provider.targetAccountCount;

    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          IconButton(
            onPressed: () => provider.setStep(OnboardingStep.welcome),
            icon: const Icon(Icons.arrow_back_rounded),
            padding: EdgeInsets.zero,
            alignment: Alignment.centerLeft,
          ),
          const SizedBox(height: 16),

          Text(
            'Connect your Gmail',
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'How many Gmail accounts do you want CareerMail AI to monitor for opportunities?',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: Colors.grey.shade600,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 28),

          // Option 1: 1 Account
          _buildSelectionCard(
            context,
            key: const Key('accountOption1'),
            count: 1,
            title: '1 Gmail Account',
            subtitle: 'Recommended for single primary career or personal inboxes.',
            icon: Icons.person_outline_rounded,
            isSelected: selectedCount == 1,
            onTap: () => provider.setTargetAccountCount(1),
          ),
          const SizedBox(height: 16),

          // Option 2: 2 Accounts
          _buildSelectionCard(
            context,
            key: const Key('accountOption2'),
            count: 2,
            title: '2 Gmail Accounts',
            subtitle: 'Monitor two inboxes (e.g. your College email + Personal email).',
            icon: Icons.people_outline_rounded,
            isSelected: selectedCount == 2,
            onTap: () => provider.setTargetAccountCount(2),
          ),

          const SizedBox(height: 32),

          Center(
            child: Text(
              'You can always add or remove accounts later in Settings.',
              style: TextStyle(fontSize: 12, color: Colors.grey.shade500),
            ),
          ),
          const SizedBox(height: 16),

          SizedBox(
            width: double.infinity,
            height: 54,
            child: FilledButton(
              key: const Key('confirmCountButton'),
              onPressed: () => provider.confirmAccountSelection(),
              style: FilledButton.styleFrom(
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              child: const Text(
                'Continue',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
            ),
          ),
          const SizedBox(height: 12),
        ],
      ),
    );
  }

  Widget _buildSelectionCard(
    BuildContext context, {
    required Key key,
    required int count,
    required String title,
    required String subtitle,
    required IconData icon,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    final theme = Theme.of(context);
    final borderColor = isSelected ? AppTheme.primaryColor : Colors.grey.shade300;
    final bgColor = isSelected ? AppTheme.primaryColor.withValues(alpha: 0.06) : Colors.transparent;

    return InkWell(
      key: key,
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: borderColor, width: isSelected ? 2 : 1),
        ),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: isSelected
                    ? AppTheme.primaryColor.withValues(alpha: 0.15)
                    : Colors.grey.shade100,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(
                icon,
                color: isSelected ? AppTheme.primaryColor : Colors.grey.shade700,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: isSelected ? AppTheme.primaryColor : null,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey.shade600,
                      height: 1.3,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Icon(
              isSelected ? Icons.check_circle_rounded : Icons.radio_button_unchecked,
              color: isSelected ? AppTheme.primaryColor : Colors.grey.shade400,
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// STEP 3: CONNECT ACCOUNTS
// ─────────────────────────────────────────────────────────────────────────────

class _ConnectAccountsStepView extends StatelessWidget {
  const _ConnectAccountsStepView({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final provider = context.watch<OnboardingProvider>();
    final targetCount = provider.targetAccountCount;
    final connectedAccounts = provider.connectedAccounts;

    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          IconButton(
            onPressed: () => provider.setStep(OnboardingStep.selectAccountCount),
            icon: const Icon(Icons.arrow_back_rounded),
            padding: EdgeInsets.zero,
            alignment: Alignment.centerLeft,
          ),
          const SizedBox(height: 16),

          Text(
            targetCount == 1 ? 'Connect your Gmail' : 'Connect your Gmail accounts',
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            targetCount == 1
                ? 'Authorize CareerMail AI with your primary Gmail account.'
                : 'Connect your 2 Gmail accounts. CareerMail AI securely stores encrypted tokens.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: Colors.grey.shade600,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 24),

          // Slot 1
          _buildAccountSlotCard(
            context,
            slotNumber: 1,
            account: connectedAccounts.isNotEmpty ? connectedAccounts[0] : null,
            isConnecting: provider.isConnecting && connectedAccounts.isEmpty,
            onConnect: () => provider.startOAuthConnection(),
          ),
          const SizedBox(height: 14),

          // Slot 2 (if 2 accounts requested)
          if (targetCount == 2) ...[
            _buildAccountSlotCard(
              context,
              slotNumber: 2,
              account: connectedAccounts.length > 1 ? connectedAccounts[1] : null,
              isConnecting: provider.isConnecting && connectedAccounts.length == 1,
              isEnabled: connectedAccounts.isNotEmpty, // Only after slot 1 is connected
              onConnect: () => provider.startOAuthConnection(),
            ),
            const SizedBox(height: 14),
          ],

          if (provider.errorMessage != null) ...[
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppTheme.overdueColor.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_outline, color: AppTheme.overdueColor, size: 18),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      provider.errorMessage!,
                      style: const TextStyle(color: AppTheme.overdueColor, fontSize: 12),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
          ],

          // Helper info about browser flow
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.blue.withValues(alpha: 0.06),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.blue.withValues(alpha: 0.2)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.security_rounded, color: Colors.blue, size: 20),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Google OAuth runs in your browser. Tokens are encrypted using Fernet keys at rest. CareerMail AI never accesses your password.',
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade700, height: 1.4),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 28),

          // If required accounts are satisfied, allow manual advance (although auto-advance also triggers)
          if (provider.hasRequiredAccounts)
            SizedBox(
              width: double.infinity,
              height: 54,
              child: FilledButton(
                key: const Key('startSyncButton'),
                onPressed: () => provider.startInitialSyncPipeline(),
                style: FilledButton.styleFrom(
                  backgroundColor: AppTheme.internshipColor,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
                child: const Text(
                  'Start Setup & Sync',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
              ),
            )
          else if (provider.isPolling)
            Center(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    'Waiting for Google authorization in browser...',
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 12),
        ],
      ),
    );
  }

  Widget _buildAccountSlotCard(
    BuildContext context, {
    required int slotNumber,
    required dynamic account,
    required bool isConnecting,
    bool isEnabled = true,
    required VoidCallback onConnect,
  }) {
    final isConnected = account != null;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isConnected
            ? AppTheme.internshipColor.withValues(alpha: 0.06)
            : Colors.grey.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: isConnected ? AppTheme.internshipColor : Colors.grey.shade300,
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: isConnected
                  ? AppTheme.internshipColor.withValues(alpha: 0.15)
                  : Colors.grey.shade200,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              isConnected ? Icons.check_circle_rounded : Icons.mail_outline_rounded,
              color: isConnected ? AppTheme.internshipColor : Colors.grey.shade600,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Gmail Account $slotNumber',
                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                ),
                const SizedBox(height: 2),
                Text(
                  isConnected ? account.emailAddress : (isEnabled ? 'Ready to connect' : 'Connect Account 1 first'),
                  style: TextStyle(
                    fontSize: 12,
                    color: isConnected ? AppTheme.internshipColor : Colors.grey.shade600,
                    fontWeight: isConnected ? FontWeight.w600 : FontWeight.normal,
                  ),
                ),
              ],
            ),
          ),
          if (!isConnected)
            FilledButton.tonal(
              key: Key('connectSlotButton$slotNumber'),
              onPressed: isEnabled && !isConnecting ? onConnect : null,
              style: FilledButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              child: isConnecting
                  ? const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Connect', style: TextStyle(fontSize: 13)),
            ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// STEP 4: SETUP & SYNC PROGRESS CHECKLIST
// ─────────────────────────────────────────────────────────────────────────────

class _SyncProgressStepView extends StatelessWidget {
  const _SyncProgressStepView({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final provider = context.watch<OnboardingProvider>();
    final isReady = provider.syncStage == SyncProgressStage.dashboardReady;
    final isFailed = provider.syncStage == SyncProgressStage.failed;

    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 16),
          Text(
            isReady ? 'Setup Complete!' : 'Setting up CareerMail AI',
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            isReady
                ? 'Your career opportunities and deadlines are ready.'
                : 'Processing your emails silently in the background.',
            style: TextStyle(fontSize: 14, color: Colors.grey.shade600),
          ),
          const SizedBox(height: 24),

          // Linear Progress Bar
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: LinearProgressIndicator(
              value: provider.progressPercentage,
              minHeight: 8,
              backgroundColor: Colors.grey.shade200,
              valueColor: AlwaysStoppedAnimation<Color>(
                isReady ? AppTheme.internshipColor : AppTheme.primaryColor,
              ),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            provider.statusMessage,
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 24),

          // Live Checklist of Stages
          _buildChecklistItem(
            title: 'Gmail Account Connected',
            isComplete: provider.syncStage.index >= SyncProgressStage.gmailConnected.index,
            isActive: provider.syncStage == SyncProgressStage.gmailConnected,
          ),
          _buildChecklistItem(
            title: 'Encryption Established',
            isComplete: provider.syncStage.index >= SyncProgressStage.accountSecured.index,
            isActive: provider.syncStage == SyncProgressStage.accountSecured,
          ),
          _buildChecklistItem(
            title: 'Reading & Ingesting Emails',
            subtitle: provider.totalEmailsIngested > 0 ? '${provider.totalEmailsIngested} emails loaded' : null,
            isComplete: provider.syncStage.index > SyncProgressStage.readingEmails.index,
            isActive: provider.syncStage == SyncProgressStage.readingEmails,
          ),
          _buildChecklistItem(
            title: 'Analyzing Opportunities with Gemini',
            isComplete: provider.syncStage.index > SyncProgressStage.findingOpportunities.index,
            isActive: provider.syncStage == SyncProgressStage.findingOpportunities,
          ),
          _buildChecklistItem(
            title: 'Detecting Deadlines & Action Items',
            isComplete: provider.syncStage.index >= SyncProgressStage.dashboardReady.index,
            isActive: provider.syncStage == SyncProgressStage.detectingDeadlines,
          ),

          const SizedBox(height: 24),

          // Ready Summary Card
          if (isReady) ...[
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: AppTheme.internshipColor.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.internshipColor.withValues(alpha: 0.3)),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _buildMetricPill(provider.opportunitiesFound.toString(), 'Opportunities', AppTheme.primaryColor),
                  _buildMetricPill(provider.deadlinesFound.toString(), 'Deadlines', AppTheme.urgentColor),
                  _buildMetricPill(provider.urgentActionsFound.toString(), 'Actions', AppTheme.hackathonColor),
                ],
              ),
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              height: 54,
              child: FilledButton(
                key: const Key('openDashboardButton'),
                onPressed: () {
                  // Refresh global feeds
                  context.read<AccountsProvider>().fetchAccounts();
                  context.read<DigestProvider>().refresh();
                  context.read<OpportunitiesProvider>().fetchOpportunities(refresh: true);
                  context.read<DeadlinesProvider>().refresh();

                  // Transition to Dashboard
                  provider.completeOnboarding();
                  Navigator.of(context).pushReplacement(
                    MaterialPageRoute(builder: (_) => const MainNavigationScreen()),
                  );
                },
                style: FilledButton.styleFrom(
                  backgroundColor: AppTheme.primaryColor,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      'Open Career Dashboard',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                    SizedBox(width: 8),
                    Icon(Icons.arrow_forward_rounded, size: 20),
                  ],
                ),
              ),
            ),
          ] else if (isFailed) ...[
            Center(
              child: Column(
                children: [
                  Text(
                    provider.errorMessage ?? 'Setup interrupted.',
                    style: const TextStyle(color: AppTheme.overdueColor, fontSize: 13),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 12),
                  FilledButton.tonal(
                    key: const Key('retrySyncButton'),
                    onPressed: () => provider.retrySync(),
                    child: const Text('Retry Setup'),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 12),
        ],
      ),
    );
  }

  Widget _buildChecklistItem({
    required String title,
    String? subtitle,
    required bool isComplete,
    required bool isActive,
  }) {
    Widget iconWidget;

    if (isComplete) {
      iconWidget = const Icon(Icons.check_circle_rounded, color: AppTheme.internshipColor, size: 22);
    } else if (isActive) {
      iconWidget = const SizedBox(
        width: 18,
        height: 18,
        child: CircularProgressIndicator(strokeWidth: 2.2),
      );
    } else {
      iconWidget = Icon(Icons.radio_button_unchecked, color: Colors.grey.shade400, size: 20);
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          SizedBox(width: 26, height: 26, child: Center(child: iconWidget)),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: isComplete || isActive ? FontWeight.w600 : FontWeight.normal,
                    color: isComplete || isActive ? null : Colors.grey.shade600,
                  ),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: 2),
                  Text(subtitle, style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMetricPill(String value, String label, Color color) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: color),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: Colors.black54),
        ),
      ],
    );
  }
}
