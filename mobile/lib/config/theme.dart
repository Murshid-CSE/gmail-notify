import 'package:flutter/material.dart';

/// CareerMail AI — Material 3 Theme & Semantic Design Tokens.
class AppTheme {
  // Brand colors
  static const Color primaryColor = Color(0xFF4F46E5); // Indigo 600
  static const Color secondaryColor = Color(0xFF6366F1); // Indigo 500

  // Category Semantic Colors
  static const Color hackathonColor = Color(0xFF7C3AED); // Violet
  static const Color internshipColor = Color(0xFF059669); // Emerald
  static const Color placementColor = Color(0xFF2563EB); // Royal Blue
  static const Color collegeColor = Color(0xFFD97706); // Amber
  static const Color generalColor = Color(0xFF64748B); // Slate

  // Urgency & Status Colors
  static const Color overdueColor = Color(0xFFDC2626); // Red 600
  static const Color urgentColor = Color(0xFFEA580C); // Orange 600
  static const Color todayColor = Color(0xFFD97706); // Amber 600
  static const Color tomorrowColor = Color(0xFF2563EB); // Blue 600
  static const Color upcomingColor = Color(0xFF059669); // Green 600

  // Category helpers
  static Color getCategoryColor(String? category) {
    switch (category?.toLowerCase()) {
      case 'hackathon':
        return hackathonColor;
      case 'internship':
        return internshipColor;
      case 'placement':
        return placementColor;
      case 'college':
        return collegeColor;
      default:
        return generalColor;
    }
  }

  static IconData getCategoryIcon(String? category) {
    switch (category?.toLowerCase()) {
      case 'hackathon':
        return Icons.emoji_events_outlined;
      case 'internship':
        return Icons.work_outline;
      case 'placement':
        return Icons.business_center_outlined;
      case 'college':
        return Icons.school_outlined;
      default:
        return Icons.bookmark_border;
    }
  }

  static Color getPriorityColor(String? priority) {
    switch (priority?.toLowerCase()) {
      case 'critical':
        return const Color(0xFFDC2626);
      case 'high':
        return const Color(0xFFEA580C);
      case 'medium':
        return const Color(0xFF2563EB);
      case 'low':
      default:
        return const Color(0xFF64748B);
    }
  }

  static Color getStatusColor(String? status) {
    switch (status?.toLowerCase()) {
      case 'shortlisted':
      case 'next_round':
      case 'selected':
        return const Color(0xFF059669); // Green
      case 'assessment':
      case 'interview':
        return const Color(0xFF2563EB); // Blue
      case 'registered':
        return const Color(0xFF7C3AED); // Purple
      case 'rejected':
        return const Color(0xFFDC2626); // Red
      case 'completed':
        return const Color(0xFF64748B); // Slate
      case 'opportunity':
      default:
        return const Color(0xFF0284C7); // Sky blue
    }
  }

  // Light Theme
  static ThemeData get lightTheme {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: primaryColor,
      brightness: Brightness.light,
      primary: primaryColor,
      surface: const Color(0xFFF8FAFC),
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: const Color(0xFFF8FAFC),
      appBarTheme: const AppBarTheme(
        centerTitle: false,
        elevation: 0,
        backgroundColor: Colors.white,
        foregroundColor: Color(0xFF0F172A),
        surfaceTintColor: Colors.transparent,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: Colors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: Color(0xFFE2E8F0), width: 1),
        ),
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      ),
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        elevation: 2,
        backgroundColor: Colors.white,
        indicatorColor: primaryColor.withValues(alpha: 0.15),
      ),
    );
  }

  // Dark Theme
  static ThemeData get darkTheme {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: primaryColor,
      brightness: Brightness.dark,
      primary: secondaryColor,
      surface: const Color(0xFF0F172A),
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: const Color(0xFF020617),
      appBarTheme: const AppBarTheme(
        centerTitle: false,
        elevation: 0,
        backgroundColor: Color(0xFF0F172A),
        foregroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: const Color(0xFF0F172A),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: Color(0xFF1E293B), width: 1),
        ),
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      ),
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        elevation: 2,
        backgroundColor: const Color(0xFF0F172A),
        indicatorColor: secondaryColor.withValues(alpha: 0.25),
      ),
    );
  }
}
