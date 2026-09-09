import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:careermail/models/deadline.dart';
import 'package:careermail/models/opportunity.dart';
import 'package:careermail/widgets/deadline_card.dart';
import 'package:careermail/widgets/empty_state.dart';
import 'package:careermail/widgets/error_state.dart';
import 'package:careermail/widgets/opportunity_card.dart';
import 'package:careermail/widgets/priority_badge.dart';
import 'package:careermail/widgets/status_badge.dart';

void main() {
  group('UI Widget Tests', () {
    testWidgets('EmptyState renders title and message', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: EmptyState(
              title: "You're all caught up!",
              message: 'No opportunities found.',
            ),
          ),
        ),
      );

      expect(find.text("You're all caught up!"), findsOneWidget);
      expect(find.text('No opportunities found.'), findsOneWidget);
    });

    testWidgets('ErrorState renders error message and retry button', (WidgetTester tester) async {
      bool retried = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ErrorState(
              message: 'Failed to connect to server',
              onRetry: () {
                retried = true;
              },
            ),
          ),
        ),
      );

      expect(find.text('Unable to Load Data'), findsOneWidget);
      expect(find.text('Failed to connect to server'), findsOneWidget);

      await tester.tap(find.text('Try Again'));
      expect(retried, isTrue);
    });

    testWidgets('StatusBadge renders formatted status and round', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: StatusBadge(
              status: 'next_round',
              roundName: 'Round 2',
            ),
          ),
        ),
      );

      expect(find.text('Next Round (Round 2)'), findsOneWidget);
    });

    testWidgets('PriorityBadge renders capitalized priority', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: PriorityBadge(priority: 'critical'),
          ),
        ),
      );

      expect(find.text('CRITICAL'), findsOneWidget);
    });

    testWidgets('OpportunityCard renders title, organization, and action banner', (WidgetTester tester) async {
      final opp = Opportunity(
        id: 1,
        category: 'hackathon',
        title: 'Smart India Hackathon',
        organization: 'Ministry of Education',
        status: 'shortlisted',
        actionRequired: true,
        action: 'Submit architecture diagram',
        priority: 'high',
        confidence: 0.95,
        firstSeenAt: DateTime.now(),
        lastUpdatedAt: DateTime.now(),
        daysRemaining: 2,
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: OpportunityCard(opportunity: opp),
          ),
        ),
      );

      expect(find.text('Smart India Hackathon'), findsOneWidget);
      expect(find.text('Ministry of Education'), findsOneWidget);
      expect(find.text('Submit architecture diagram'), findsOneWidget);
      expect(find.text('Due in 2 days'), findsOneWidget);
    });

    testWidgets('DeadlineCard renders title and deadline countdown', (WidgetTester tester) async {
      final card = DeadlineCardItem(
        id: 1,
        title: 'Google SDE Intern',
        organization: 'Google',
        category: 'internship',
        status: 'interview',
        priority: 'critical',
        actionRequired: false,
        daysRemaining: 1,
        isDueTomorrow: true,
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: DeadlineCard(item: card),
          ),
        ),
      );

      expect(find.text('Google SDE Intern'), findsOneWidget);
      expect(find.text('Google'), findsOneWidget);
      expect(find.text('Tomorrow'), findsOneWidget);
    });
  });
}
