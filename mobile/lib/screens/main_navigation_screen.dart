import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/notification_service.dart';
import 'dashboard_screen.dart';
import 'deadlines_screen.dart';
import 'opportunities_screen.dart';
import 'opportunity_detail_screen.dart';
import 'settings_screen.dart';

/// CareerMail AI — Main Navigation Shell.
class MainNavigationScreen extends StatefulWidget {
  const MainNavigationScreen({super.key});

  @override
  State<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends State<MainNavigationScreen> {
  int _currentIndex = 0;
  StreamSubscription<NotificationPayload>? _notificationSub;

  final List<Widget> _screens = const [
    DashboardScreen(),
    OpportunitiesScreen(),
    DeadlinesScreen(),
    SettingsScreen(),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final notifService = context.read<NotificationService>();
      notifService.initialize();
      _notificationSub = notifService.onNotificationTapped.listen(_handleNotificationTap);
    });
  }

  @override
  void dispose() {
    _notificationSub?.cancel();
    super.dispose();
  }

  void _handleNotificationTap(NotificationPayload payload) {
    if (!mounted) return;

    if (payload.isOpportunity && payload.opportunityId != null) {
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => OpportunityDetailScreen(opportunityId: payload.opportunityId!),
        ),
      );
    } else if (payload.isDigest) {
      setState(() {
        _currentIndex = 0; // Navigate to Dashboard
      });
    }
  }


  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (index) {
          setState(() {
            _currentIndex = index;
          });
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.work_outline),
            selectedIcon: Icon(Icons.work),
            label: 'Opportunities',
          ),
          NavigationDestination(
            icon: Icon(Icons.calendar_month_outlined),
            selectedIcon: Icon(Icons.calendar_month),
            label: 'Deadlines',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings),
            label: 'Settings',
          ),
        ],
      ),
    );
  }
}
