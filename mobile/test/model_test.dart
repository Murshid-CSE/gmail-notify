import 'package:flutter_test/flutter_test.dart';
import 'package:careermail/models/opportunity.dart';
import 'package:careermail/models/deadline.dart';
import 'package:careermail/models/digest.dart';
import 'package:careermail/models/email.dart';
import 'package:careermail/models/account.dart';

void main() {
  group('Model JSON Deserialization & Null Safety Tests', () {
    test('Opportunity.fromJson parses full valid payload', () {
      final json = {
        'id': 1,
        'category': 'hackathon',
        'title': 'HackNITR 5.0',
        'organization': 'NIT Rourkela',
        'description': 'Annual hackathon',
        'status': 'shortlisted',
        'round_name': 'Round 2',
        'deadline': '2026-09-15T18:30:00Z',
        'event_date': 'Sep 20-22, 2026',
        'location': 'Online',
        'eligibility': 'Students',
        'apply_url': 'https://hacknitr.com',
        'event_url': 'https://devpost.com',
        'action_required': true,
        'action': 'Submit Round 2 PPT',
        'priority': 'critical',
        'confidence': 0.95,
        'first_seen_at': '2026-09-01T10:00:00Z',
        'last_updated_at': '2026-09-08T12:00:00Z',
        'days_remaining': 7,
        'hours_remaining': 168.0,
        'is_overdue': false,
        'is_due_today': false,
        'is_due_tomorrow': false,
        'source_emails': [
          {
            'id': 10,
            'gmail_message_id': 'msg_10',
            'subject': 'Shortlisted for HackNITR',
            'received_at': '2026-09-08T12:00:00Z',
            'sender': 'team@hacknitr.com',
          }
        ],
        'status_history': [
          {
            'id': 100,
            'old_status': 'registered',
            'new_status': 'shortlisted',
            'source_email_id': 10,
            'changed_at': '2026-09-08T12:00:00Z',
          }
        ],
      };

      final opp = Opportunity.fromJson(json);

      expect(opp.id, 1);
      expect(opp.title, 'HackNITR 5.0');
      expect(opp.category, 'hackathon');
      expect(opp.status, 'shortlisted');
      expect(opp.roundName, 'Round 2');
      expect(opp.actionRequired, isTrue);
      expect(opp.action, 'Submit Round 2 PPT');
      expect(opp.priority, 'critical');
      expect(opp.daysRemaining, 7);
      expect(opp.sourceEmails.length, 1);
      expect(opp.sourceEmails[0].gmailMessageId, 'msg_10');
      expect(opp.statusHistory.length, 1);
      expect(opp.statusHistory[0].newStatus, 'shortlisted');
    });

    test('Opportunity.fromJson handles missing optional fields safely', () {
      final minimalJson = {
        'id': 2,
        'title': 'Minimal Internship',
      };

      final opp = Opportunity.fromJson(minimalJson);

      expect(opp.id, 2);
      expect(opp.title, 'Minimal Internship');
      expect(opp.category, 'general');
      expect(opp.status, 'opportunity');
      expect(opp.organization, isNull);
      expect(opp.deadline, isNull);
      expect(opp.actionRequired, isFalse);
      expect(opp.action, isNull);
      expect(opp.applyUrl, isNull);
      expect(opp.sourceEmails, isEmpty);
      expect(opp.statusHistory, isEmpty);
    });

    test('DeadlinesGrouped.fromJson parses all groups correctly', () {
      final json = {
        'overdue': [
          {
            'id': 1,
            'title': 'Overdue Test',
            'category': 'hackathon',
            'status': 'registered',
            'priority': 'high',
            'action_required': false,
            'is_overdue': true,
          }
        ],
        'today': [],
        'tomorrow': [],
        'this_week': [],
        'later': [],
        'no_deadline': [
          {
            'id': 2,
            'title': 'No Deadline Test',
            'category': 'internship',
            'status': 'open',
            'priority': 'low',
            'action_required': false,
          }
        ],
        'total_active': 1,
      };

      final grouped = DeadlinesGrouped.fromJson(json);

      expect(grouped.overdue.length, 1);
      expect(grouped.overdue[0].title, 'Overdue Test');
      expect(grouped.overdue[0].isOverdue, isTrue);
      expect(grouped.noDeadline.length, 1);
      expect(grouped.totalActive, 1);
    });

    test('DailyDigest.fromJson parses counts, actions, and brief summary', () {
      final json = {
        'generated_at': '2026-09-08T12:00:00Z',
        'target_date': '2026-09-08',
        'timezone': 'Asia/Kolkata',
        'summary': 'YOUR DAILY CAREER BRIEF\n2 urgent actions',
        'counts': {
          'new_opportunities': 1,
          'status_changes': 2,
          'urgent_actions': 2,
          'deadlines_today': 1,
          'deadlines_tomorrow': 1,
          'deadlines_this_week': 3,
          'hackathon_updates': 1,
          'internship_updates': 1,
          'placement_updates': 0,
          'college_updates': 0,
        },
        'urgent_actions': [
          {
            'opportunity_id': 1,
            'title': 'Urgent Opp',
            'category': 'hackathon',
            'action': 'Submit code',
            'priority': 'critical',
            'is_overdue': false,
          }
        ],
        'recent_status_changes': [],
        'new_opportunities': [],
        'upcoming_deadlines': [],
      };

      final digest = DailyDigest.fromJson(json);

      expect(digest.summary, contains('YOUR DAILY CAREER BRIEF'));
      expect(digest.counts.newOpportunities, 1);
      expect(digest.counts.statusChanges, 2);
      expect(digest.urgentActions.length, 1);
      expect(digest.urgentActions[0].action, 'Submit code');
    });

    test('EmailDetail.fromJson parses recipients and labels safely', () {
      final json = {
        'id': 50,
        'gmail_message_id': 'g_msg_50',
        'gmail_thread_id': 'g_th_50',
        'account_id': 1,
        'sender': 'recruiter@company.com',
        'recipients': ['student@college.edu', 'careers@college.edu'],
        'subject': 'Interview Scheduled',
        'received_at': '2026-09-08T10:00:00Z',
        'body_text': 'Dear Candidate, your interview is set for Friday.',
        'labels': ['INBOX', 'IMPORTANT'],
        'processing_status': 'extracted',
        'created_at': '2026-09-08T10:05:00Z',
      };

      final email = EmailDetail.fromJson(json);

      expect(email.id, 50);
      expect(email.sender, 'recruiter@company.com');
      expect(email.recipients, contains('student@college.edu'));
      expect(email.labels, contains('IMPORTANT'));
      expect(email.bodyText, contains('interview is set'));
    });

    test('EmailAccount.fromJson parses account status and timestamps', () {
      final json = {
        'id': 1,
        'email_address': 'student@gmail.com',
        'provider': 'gmail',
        'is_active': true,
        'last_sync_at': '2026-09-08T11:30:00Z',
        'created_at': '2026-09-01T08:00:00Z',
      };

      final acc = EmailAccount.fromJson(json);

      expect(acc.id, 1);
      expect(acc.emailAddress, 'student@gmail.com');
      expect(acc.isActive, isTrue);
      expect(acc.lastSyncAt, isNotNull);
    });
  });
}
