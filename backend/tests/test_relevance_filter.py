"""
CareerMail AI — Relevance Filter Tests.

Tests the keyword-based pre-filter for career/college emails:
  • Hackathon detection (Devpost, MLH, shortlisted, next round)
  • Internship detection (SWE, OA, stipend)
  • Placement / campus drive detection (CDC, TPO, interview)
  • College notices (exams, results, workshops)
  • Scholarship emails
  • Noise / spam rejection (promotional, newsletter, order confirmation)
  • Edge cases (empty inputs, subject weighting, thresholds)
"""

from app.services.extraction.filter import check_relevance, FilterResult


class TestHackathonDetection:
    def test_hackathon_in_subject(self):
        result = check_relevance(
            subject="Invitation to HackNITR 5.0 - National Hackathon",
            sender="team@hacknitr.com",
            body_text="Register now for 36 hours of hacking and building projects.",
        )
        assert result.is_relevant is True
        assert result.primary_category == "hackathon"
        assert "hackathon" in result.matched_keywords
        assert result.score > 0.1

    def test_hackathon_shortlist_notification(self):
        result = check_relevance(
            subject="Congratulations! You have been shortlisted for Round 2",
            sender="hackathon@devpost.com",
            body_text="Your submission was selected for the next round. Submit prototype by Friday.",
        )
        assert result.is_relevant is True
        assert result.primary_category == "hackathon"
        assert any(k in result.matched_keywords for k in ["shortlisted", "next round", "devpost"])

    def test_devpost_submission_confirmation(self):
        result = check_relevance(
            subject="Project Submission Confirmed on Devpost",
            sender="notifications@devpost.com",
            body_text="Your project has been entered into the Smart India Hackathon.",
        )
        assert result.is_relevant is True
        assert result.primary_category == "hackathon"


class TestInternshipDetection:
    def test_software_engineer_internship(self):
        result = check_relevance(
            subject="Application Update: Software Engineer Intern at Stripe",
            sender="recruiting@stripe.com",
            body_text="We have received your application for the summer intern role.",
        )
        assert result.is_relevant is True
        assert result.primary_category == "internship"
        assert "internship" in result.matched_keywords or "software engineer" in result.matched_keywords

    def test_online_assessment_invitation(self):
        result = check_relevance(
            subject="Google Online Assessment (OA) Invitation",
            sender="no-reply@hackerearth.com",
            body_text="Please complete your online assessment within 48 hours for the SDE internship.",
        )
        assert result.is_relevant is True
        assert result.primary_category in ("internship", "hackathon")
        assert result.score >= 0.2


class TestPlacementDetection:
    def test_campus_placement_drive(self):
        result = check_relevance(
            subject="CDC Notice: Microsoft Campus Recruitment Drive 2026",
            sender="cdc@college.edu",
            body_text="Placement drive scheduled for final year students. Pre-placement talk at 10 AM.",
        )
        assert result.is_relevant is True
        assert result.primary_category == "placement"

    def test_tpo_interview_schedule(self):
        result = check_relevance(
            subject="TPO Alert: Shortlisted for Interview - Amazon",
            sender="tpo@university.ac.in",
            body_text="Interview slot confirmed. Please bring resume and college ID.",
        )
        assert result.is_relevant is True
        assert result.primary_category == "placement"


class TestCollegeNotices:
    def test_midterm_exam_schedule(self):
        result = check_relevance(
            subject="Notice: Midterm Examination Schedule Autumn 2026",
            sender="dean_academics@college.edu",
            body_text="The midterm exam for 6th semester will commence next week.",
        )
        assert result.is_relevant is True
        assert result.primary_category == "college"

    def test_workshop_registration(self):
        result = check_relevance(
            subject="Department Workshop on Machine Learning - Registration Open",
            sender="cse_dept@college.edu",
            body_text="Registration deadline is March 15th. Limited seats available.",
        )
        assert result.is_relevant is True
        assert result.primary_category == "college"


class TestScholarshipDetection:
    def test_merit_scholarship(self):
        result = check_relevance(
            subject="Merit-Based Scholarship Application 2026",
            sender="scholarships@foundation.org",
            body_text="Apply for financial aid and scholarship for engineering students.",
        )
        assert result.is_relevant is True
        assert result.primary_category == "scholarship"


class TestNoiseRejection:
    def test_promotional_sale_rejected(self):
        result = check_relevance(
            subject="Flash Sale! 50% off on all shoes",
            sender="marketing@store.com",
            body_text="Unsubscribe from this list. Limited time offer on shoes.",
        )
        assert result.is_relevant is False
        assert result.score == 0.0

    def test_shipping_update_rejected(self):
        result = check_relevance(
            subject="Your package has shipped!",
            sender="shipping@amazon.com",
            body_text="Order confirmation #12345. You are receiving this because you ordered.",
        )
        assert result.is_relevant is False
        assert result.score == 0.0

    def test_social_media_rejected(self):
        result = check_relevance(
            subject="You have 5 new notifications on LinkedIn",
            sender="notifications@linkedin.com",
            body_text="Social media notification. Unsubscribe from this list.",
        )
        assert result.is_relevant is False


class TestEdgeCases:
    def test_empty_inputs(self):
        result = check_relevance(subject="", sender="", body_text="")
        assert result.is_relevant is False
        assert result.score == 0.0
        assert result.matched_keywords == []

    def test_subject_weighted_higher_than_body(self):
        subject_match = check_relevance(
            subject="Hackathon Announcement",
            sender="info@test.com",
            body_text="General greetings.",
        )
        body_match = check_relevance(
            subject="Greetings",
            sender="info@test.com",
            body_text="Hackathon mentioned deep in the body.",
        )
        assert subject_match.score > body_match.score

    def test_custom_threshold(self):
        result_strict = check_relevance(
            subject="Some general event",
            sender="user@test.com",
            body_text="A small hackathon keyword mention",
            threshold=0.9,
        )
        assert result_strict.is_relevant is False
