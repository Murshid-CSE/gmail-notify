"""
CareerMail AI — Relevance Filter.

Cheap keyword-based pre-filter that determines whether an email
is potentially career/college relevant BEFORE sending to Gemini AI.

This is NOT the final classification — it only reduces unnecessary
AI API calls by filtering out obvious noise (newsletters, promotions, spam).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger("extraction.filter")

# ── Keyword sets by category ──────────────────────────────

HACKATHON_KEYWORDS: set[str] = {
    "hackathon", "hack-a-thon", "hack a thon",
    "competition", "coding challenge", "code jam", "codejam",
    "shortlisted", "shortlist", "finalist", "finalists",
    "qualified", "advanced", "progressed", "moved forward",
    "selected for the next", "next round", "round 2", "round 3",
    "submission", "prototype", "demo day", "pitch",
    "devpost", "hackerearth", "hackathon.com",
    "mlh ", "major league hacking",
}

INTERNSHIP_KEYWORDS: set[str] = {
    "internship", "intern ", "interns ", "internships",
    "software engineer", "developer", "sde", "swe",
    "application received", "application status",
    "assessment", "online assessment", "oa ",
    "offer letter", "joining date",
    "stipend", "compensation",
    "summer intern", "winter intern",
    "full-time", "full time",
}

PLACEMENT_KEYWORDS: set[str] = {
    "placement", "placements", "campus recruitment",
    "campus drive", "recruitment drive",
    "cdc ", "career development", "training and placement",
    "tpo ", "placement cell", "placement officer",
    "hiring", "eligibility criteria",
    "interview schedule", "interview slot",
    "pre-placement", "ppo ", "pre placement offer",
    "shortlisted for interview",
    "aptitude test", "group discussion",
}

COLLEGE_KEYWORDS: set[str] = {
    "college", "university", "department",
    "notice", "circular", "notification",
    "exam", "examination", "midterm", "endsem", "end-sem",
    "workshop", "seminar", "webinar", "guest lecture",
    "registration", "registration deadline",
    "deadline", "last date",
    "fee", "fees", "scholarship",
    "result", "grade", "cgpa", "sgpa",
    "attendance", "assignment", "project submission",
}

SCHOLARSHIP_KEYWORDS: set[str] = {
    "scholarship", "fellowships", "fellowship",
    "financial aid", "bursary",
    "merit-based", "need-based",
    "award", "grant",
}

# Combined set for quick "is this relevant at all?" check.
ALL_CAREER_KEYWORDS: set[str] = (
    HACKATHON_KEYWORDS
    | INTERNSHIP_KEYWORDS
    | PLACEMENT_KEYWORDS
    | COLLEGE_KEYWORDS
    | SCHOLARSHIP_KEYWORDS
)

# ── Noise indicators (likely irrelevant) ──────────────────

NOISE_INDICATORS: set[str] = {
    "unsubscribe from this list",
    "you are receiving this because",
    "marketing email",
    "promotional offer",
    "flash sale", "limited time offer",
    "order confirmation", "shipping update",
    "password reset", "verify your email",
    "social media notification",
}


@dataclass
class FilterResult:
    """Result of relevance filtering."""
    is_relevant: bool
    matched_keywords: list[str] = field(default_factory=list)
    primary_category: Optional[str] = None
    score: float = 0.0


def check_relevance(
    subject: str,
    sender: str,
    body_text: Optional[str] = None,
    *,
    threshold: float = 0.1,
) -> FilterResult:
    """Determine if an email is potentially career/college relevant.

    Args:
        subject: Email subject line.
        sender: Email sender address.
        body_text: Cleaned plain-text body (optional, used for deeper check).
        threshold: Minimum score to consider relevant (0.0 to 1.0).

    Returns:
        FilterResult with relevance decision and matched keywords.
    """
    # Normalize all text for matching.
    subject_lower = (subject or "").lower()
    sender_lower = (sender or "").lower()

    # Use first ~2000 chars of body for speed.
    body_lower = ""
    if body_text:
        body_lower = body_text[:2000].lower()

    # Combined searchable text.
    combined = f"{subject_lower} {sender_lower} {body_lower}"

    # ── Check for noise first ─────────────────────────────
    noise_count = sum(1 for kw in NOISE_INDICATORS if kw in combined)
    if noise_count >= 2:
        return FilterResult(is_relevant=False, score=0.0)

    # ── Score by category ─────────────────────────────────
    scores: dict[str, float] = {}
    all_matched: list[str] = []

    for category, keywords in [
        ("hackathon", HACKATHON_KEYWORDS),
        ("internship", INTERNSHIP_KEYWORDS),
        ("placement", PLACEMENT_KEYWORDS),
        ("college", COLLEGE_KEYWORDS),
        ("scholarship", SCHOLARSHIP_KEYWORDS),
    ]:
        matched = _match_keywords(combined, keywords, subject_lower)
        if matched:
            # Subject matches count 3x, body matches count 1x.
            subject_matches = [kw for kw in matched if kw in subject_lower]
            body_only_matches = [kw for kw in matched if kw not in subject_lower]

            score = (len(subject_matches) * 3.0 + len(body_only_matches) * 1.0) / 10.0
            score = min(score, 1.0)
            scores[category] = score
            all_matched.extend(matched)

    if not scores:
        return FilterResult(is_relevant=False, score=0.0)

    # Pick the highest-scoring category.
    best_category = max(scores, key=scores.get)
    best_score = scores[best_category]

    is_relevant = best_score >= threshold

    return FilterResult(
        is_relevant=is_relevant,
        matched_keywords=list(set(all_matched)),
        primary_category=best_category if is_relevant else None,
        score=best_score,
    )


def _match_keywords(
    text: str,
    keywords: set[str],
    subject_text: str = "",
) -> list[str]:
    """Find which keywords appear in the text.

    Uses simple substring matching — fast and sufficient for pre-filtering.
    """
    matched = []
    for kw in keywords:
        if kw in text:
            matched.append(kw)
    return matched
