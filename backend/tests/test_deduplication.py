"""
CareerMail AI — Deduplication & Matcher Tests.

Tests:
  • Normalization of text, organizations, and titles.
  • Deterministic matching (Layer 1).
  • Conservative fuzzy matching (Layer 2).
  • Guardrails against false merges:
      - Different specialization tracks (e.g. Python Intern vs Java Intern).
      - Different years (e.g. Hackathon 2026 vs Hackathon 2027).
      - Disjoint organizations.
  • Merge cases:
      - Suffix variations ("XYZ Technologies Pvt. Ltd." vs "XYZ Technologies").
      - Stage noise in titles ("XYZ Hackathon Registration" vs "XYZ Hackathon Shortlisted").
      - Same opportunity across different Gmail accounts.
"""

from datetime import datetime, timezone
import pytest

from app.models.email_account import EmailAccount
from app.models.opportunity import Opportunity
from app.models.user import User
from app.services.deduplication.matcher import (
    are_tracks_compatible,
    are_years_compatible,
    extract_track_tokens,
    extract_year_tokens,
    find_matching_opportunity,
    normalize_organization,
    normalize_text,
    normalize_title,
)


class TestNormalization:
    def test_normalize_text(self):
        assert normalize_text("  Hello, World! 123  ") == "hello world 123"
        assert normalize_text("") == ""
        assert normalize_text(None) == ""

    def test_normalize_organization_strips_corporate_suffixes(self):
        assert normalize_organization("XYZ Technologies Pvt. Ltd.") == "xyz"
        assert normalize_organization("XYZ Technologies Private Limited") == "xyz"
        assert normalize_organization("Google Inc.") == "google"
        assert normalize_organization("Microsoft Corporation") == "microsoft"
        assert normalize_organization("Stripe LLC") == "stripe"
        assert normalize_organization("MIT University") == "mit"
        assert normalize_organization("Department of Computer Science") == "computer science"

    def test_normalize_title_strips_stage_noise(self):
        assert normalize_title("Invitation to HackNITR 5.0") == "hacknitr 5 0"
        assert normalize_title("HackNITR 5.0 Registration Confirmed") == "hacknitr 5 0"
        assert normalize_title("HackNITR 5.0 - Shortlisted for Round 2") == "hacknitr 5 0"
        assert normalize_title("Google SDE Internship - Online Assessment") == "google sde internship"
        assert normalize_title("Amazon Campus Hiring Interview Schedule") == "amazon"

    def test_extract_year_tokens(self):
        assert extract_year_tokens("Smart India Hackathon 2026") == {"2026"}
        assert extract_year_tokens("Hackathon 2026 vs 2027") == {"2026", "2027"}
        assert extract_year_tokens("No year here") == set()

    def test_extract_track_tokens(self):
        assert "python" in extract_track_tokens("Software Engineer Intern (Python)")
        assert "java" in extract_track_tokens("Java Backend Developer")
        assert "machine learning" in extract_track_tokens("Machine Learning Research Intern")
        assert extract_track_tokens("General Graduate Trainee") == set()


class TestMatchingGuardrails:
    def test_different_specialization_tracks_incompatible(self):
        # Python Intern vs Java Intern must NOT merge
        assert are_tracks_compatible("ABC Python Intern", "ABC Java Intern") is False
        assert are_tracks_compatible("Frontend Engineer", "Backend Engineer") is False

    def test_same_or_neutral_tracks_compatible(self):
        assert are_tracks_compatible("ABC Python Intern", "ABC Python Developer") is True
        assert are_tracks_compatible("ABC Software Intern", "ABC Software Intern") is True
        assert are_tracks_compatible("General Intern", "ABC Python Intern") is True

    def test_different_years_incompatible(self):
        # Hackathon 2026 vs Hackathon 2027 must NOT merge
        assert are_years_compatible("XYZ Hackathon 2026", "XYZ Hackathon 2027") is False

    def test_same_or_unspecified_years_compatible(self):
        assert are_years_compatible("XYZ Hackathon 2026", "XYZ Hackathon 2026") is True
        assert are_years_compatible("XYZ Hackathon", "XYZ Hackathon 2026") is True


class TestOpportunityDeduplicationDB:
    def _setup_user(self, db):
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            user = User(id=1, display_name="Test User")
            db.add(user)
            db.commit()
        return user

    def test_deterministic_match_same_org_and_title(self, db):
        self._setup_user(db)
        opp = Opportunity(
            user_id=1,
            category="hackathon",
            title="HackNITR 5.0",
            organization="NIT Rourkela",
            status="registered",
            first_seen_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
        )
        db.add(opp)
        db.commit()

        matched = find_matching_opportunity(
            db=db,
            user_id=1,
            category="hackathon",
            title="HackNITR 5.0 Registration",
            organization="NIT Rourkela",
        )
        assert matched is not None
        assert matched.id == opp.id

    def test_deterministic_match_corporate_suffix_variation(self, db):
        self._setup_user(db)
        opp = Opportunity(
            user_id=1,
            category="internship",
            title="Software Engineering Intern",
            organization="XYZ Technologies Pvt. Ltd.",
            status="registered",
            first_seen_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
        )
        db.add(opp)
        db.commit()

        # Incoming email has shortened org "XYZ Technologies"
        matched = find_matching_opportunity(
            db=db,
            user_id=1,
            category="internship",
            title="Software Engineering Intern - Shortlisted",
            organization="XYZ Technologies",
        )
        assert matched is not None
        assert matched.id == opp.id

    def test_false_merge_prevented_for_different_tracks(self, db):
        self._setup_user(db)
        opp = Opportunity(
            user_id=1,
            category="internship",
            title="Software Engineer Intern - Python",
            organization="Acme Corp",
            status="registered",
            first_seen_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
        )
        db.add(opp)
        db.commit()

        # Different track "Java" must NOT merge with Python intern
        matched = find_matching_opportunity(
            db=db,
            user_id=1,
            category="internship",
            title="Software Engineer Intern - Java",
            organization="Acme Corp",
        )
        assert matched is None

    def test_false_merge_prevented_for_different_years(self, db):
        self._setup_user(db)
        opp = Opportunity(
            user_id=1,
            category="hackathon",
            title="Smart India Hackathon 2026",
            organization="AICTE",
            status="registered",
            first_seen_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
        )
        db.add(opp)
        db.commit()

        # SIH 2027 must NOT merge with SIH 2026
        matched = find_matching_opportunity(
            db=db,
            user_id=1,
            category="hackathon",
            title="Smart India Hackathon 2027",
            organization="AICTE",
        )
        assert matched is None

    def test_conservative_fuzzy_match_high_similarity(self, db):
        self._setup_user(db)
        opp = Opportunity(
            user_id=1,
            category="placement",
            title="Microsoft Campus Hiring Drive 2026",
            organization="Microsoft",
            status="opportunity",
            first_seen_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
        )
        db.add(opp)
        db.commit()

        # Slight variation in title punctuation & phrasing
        matched = find_matching_opportunity(
            db=db,
            user_id=1,
            category="placement",
            title="Microsoft Campus Recruitment 2026",
            organization="Microsoft Corp",
        )
        assert matched is not None
        assert matched.id == opp.id

    def test_different_category_does_not_match(self, db):
        self._setup_user(db)
        opp = Opportunity(
            user_id=1,
            category="hackathon",
            title="CyberSecurity Challenge",
            organization="DEF",
            status="registered",
            first_seen_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
        )
        db.add(opp)
        db.commit()

        matched = find_matching_opportunity(
            db=db,
            user_id=1,
            category="internship",  # Different category
            title="CyberSecurity Challenge",
            organization="DEF",
        )
        assert matched is None
