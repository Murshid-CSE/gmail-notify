import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'config/theme.dart';
import 'providers/accounts_provider.dart';
import 'providers/deadlines_provider.dart';
import 'providers/digest_provider.dart';
import 'providers/onboarding_provider.dart';
import 'providers/opportunities_provider.dart';
import 'providers/scheduler_provider.dart';
import 'services/notification_service.dart';
import 'screens/main_navigation_screen.dart';
import 'screens/onboarding_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const CareerMailApp());
}

class CareerMailApp extends StatelessWidget {
  const CareerMailApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => NotificationService()),
        ChangeNotifierProvider(create: (_) => DigestProvider()),
        ChangeNotifierProvider(create: (_) => OpportunitiesProvider()),
        ChangeNotifierProvider(create: (_) => DeadlinesProvider()),
        ChangeNotifierProvider(create: (_) => AccountsProvider()),
        ChangeNotifierProvider(create: (_) => SchedulerProvider()),
        ChangeNotifierProvider(create: (_) => OnboardingProvider()),
      ],
      child: MaterialApp(
        title: 'CareerMail AI',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: ThemeMode.system,
        home: const AppEntryScreen(),
      ),
    );
  }
}

/// App entry router: routes existing users with connected accounts directly
/// to Dashboard, and fresh installations to the Onboarding wizard.
class AppEntryScreen extends StatefulWidget {
  const AppEntryScreen({super.key});

  @override
  State<AppEntryScreen> createState() => _AppEntryScreenState();
}

class _AppEntryScreenState extends State<AppEntryScreen> {
  late Future<void> _initFuture;

  @override
  void initState() {
    super.initState();
    final provider = context.read<AccountsProvider>();
    if (provider.hasFetched) {
      _initFuture = Future.value();
    } else {
      _initFuture = provider.fetchAccounts();
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<void>(
      future: _initFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return Scaffold(
            body: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    width: 56,
                    height: 56,
                    decoration: BoxDecoration(
                      color: AppTheme.primaryColor,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: const Icon(
                      Icons.mark_email_read_rounded,
                      color: Colors.white,
                      size: 32,
                    ),
                  ),
                  const SizedBox(height: 20),
                  const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ],
              ),
            ),
          );
        }

        final accounts = context.watch<AccountsProvider>().accounts;

        if (accounts.isNotEmpty) {
          return const MainNavigationScreen();
        } else {
          return const OnboardingScreen();
        }
      },
    );
  }
}
