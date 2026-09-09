"""
CareerMail AI — Opportunity Deduplication & Matching.

Resolves incoming email analyses to existing opportunities across connected accounts.
Implements layered matching:
  • Layer 1 (Deterministic): Normalized category + organization + title match.
  • Layer 2 (Conservative Fuzzy): High-threshold similarity check with strict
    year, track, and organization guardrails to prevent false merges.
"""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models.opportunity import Opportunity
from app.utils.logging import get_logger

logger = get_logger("deduplication.matcher")

# Common corporate / legal / entity suffixes to strip for normalization
ORG_NOISE_SUFFIXES = [
    r"\bpvt\.?\s*ltd\.?\b",
    r"\bprivate\s+limited\b",
    r"\bltd\.?\b",
    r"\blimited\b",
    r"\binc\.?\b",
    r"\bincorporated\b",
    r"\bcorp\.?\b",
    r"\bcorporation\b",
    r"\bllc\.?\b",
    r"\bgmbh\.?\b",
    r"\btechnologies\b",
    r"\btechnology\b",
    r"\bsolutions\b",
    r"\bservices\b",
    r"\blabs?\b",
    r"\bco\.?\b",
    r"\bcompany\b",
    r"\bfoundation\b",
    r"\bclub\b",
    r"\bsociety\b",
    r"\buniversity\b",
    r"\bcollege\b",
    r"\binstitute(?:\s+of\s+technology)?\b",
    r"\b(?:dept\.?|department)(?:\s+of)?\b",
]

# Stage / status / notification noise words in titles to strip for root title matching
TITLE_STAGE_NOISE = [
    r"\binvitation(?:\s+to)?\b",
    r"\bregistration(?:\s+confirmed|\s+open|\s+successful|\s+received)?\b",
    r"\bshortlist(?:ed)?(?:\s+for|\s+candidates?)?\b",
    r"\bnext\s+round\b",
    r"\b(?:for\s+)?round\s+[0-9ivx]+\b",
    r"\b(?:for\s+)?phase\s+[0-9ivx]+\b",
    r"\bfinal(?:ist)?(?:\s+round)?\b",
    r"\bselection(?:\s+process|\s+update|\s+list)?\b",
    r"\bapplication(?:\s+update|\s+status|\s+received|\s+confirmed)?\b",
    r"\bonline\s+assessment\b",
    r"\binterview(?:\s+schedule|\s+slot|\s+call)?\b",
    r"\bcampus\s+(?:recruitment|hiring|placement)(?:\s+drive)?\b",
    r"\b(?:recruitment|hiring|placement)\s+drive\b",
    r"\boffer\s+letter\b",
    r"\bupdate\b",
    r"\bnotice\b",
    r"\bannouncement\b",
    r"\bcongratulations(?:\s+on)?\b",
]

# Common specialization / track keywords that distinguish roles
ROLE_TRACK_KEYWORDS = [
    "python",
    "java",
    "c++",
    "golang",
    "rust",
    "javascript",
    "typescript",
    "react",
    "node",
    "android",
    "ios",
    "flutter",
    "data science",
    "machine learning",
    "artificial intelligence",
    "ai",
    "ml",
    "frontend",
    "backend",
    "fullstack",
    "full stack",
    "devops",
    "cloud",
    "cybersecurity",
    "security",
    "qa",
    "testing",
    "analyst",
    "research",
]


def normalize_text(text: Optional[str]) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    if not text:
        return ""
    lowered = text.lower()
    cleaned = re.sub(r"[^\w\s]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_organization(org: Optional[str]) -> str:
    """Normalize organization name by stripping common corporate/legal suffixes."""
    norm = normalize_text(org)
    if not norm:
        return ""

    for suffix_pattern in ORG_NOISE_SUFFIXES:
        norm = re.sub(suffix_pattern, "", norm).strip()

    return re.sub(r"\s+", " ", norm).strip()


def normalize_title(title: Optional[str]) -> str:
    """Normalize opportunity title by stripping common stage/notification noise."""
    norm = normalize_text(title)
    if not norm:
        return ""

    for stage_pattern in TITLE_STAGE_NOISE:
        norm = re.sub(stage_pattern, "", norm).strip()

    return re.sub(r"\s+", " ", norm).strip()


def extract_year_tokens(text: str) -> set[str]:
    """Find 4-digit years (e.g. 2024, 2025, 2026, 2027) in text."""
    if not text:
        return set()
    return set(re.findall(r"\b(202[0-9]|203[0-9])\b", text))


def extract_track_tokens(text: str) -> set[str]:
    """Find role track keywords present in text."""
    norm = normalize_text(text)
    tracks = set()
    for kw in ROLE_TRACK_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", norm):
            tracks.add(kw)
    return tracks


def are_tracks_compatible(text1: str, text2: str) -> bool:
    """Check if two texts have conflicting specialization tracks.

    If both texts explicitly specify tracks and their tracks are completely disjoint
    (e.g., "Python Intern" vs "Java Intern"), they are incompatible.
    """
    t1 = extract_track_tokens(text1)
    t2 = extract_track_tokens(text2)
    if t1 and t2 and t1.isdisjoint(t2):
        return False
    return True


def are_years_compatible(text1: str, text2: str) -> bool:
    """Check if two texts have conflicting years (e.g., 2026 vs 2027)."""
    y1 = extract_year_tokens(text1)
    y2 = extract_year_tokens(text2)
    if y1 and y2 and y1 != y2:
        return False
    return True


def find_matching_opportunity(
    db: Session,
    user_id: int,
    category: str,
    title: str,
    organization: Optional[str] = None,
) -> Optional[Opportunity]:
    """Find an existing opportunity matching the incoming email analysis.

    Uses a 2-layer strategy:
      1. Deterministic match on normalized (category, org, title).
      2. Conservative fuzzy match on title/org with strict guardrails.

    Args:
        db: Active database session.
        user_id: ID of the user owning the opportunity.
        category: Opportunity category (e.g., "hackathon", "internship").
        title: Extracted title.
        organization: Extracted organization or company.

    Returns:
        The matched Opportunity, or None if no match is found.
    """
    if not title:
        return None

    # Retrieve all existing opportunities for this user in this category
    candidates = (
        db.query(Opportunity)
        .filter(
            Opportunity.user_id == user_id,
            Opportunity.category == category,
        )
        .all()
    )

    if not candidates:
        return None

    norm_incoming_title = normalize_title(title)
    norm_incoming_org = normalize_organization(organization)

    # ── Layer 1: Deterministic Match ─────────────────────────
    for opp in candidates:
        norm_opp_title = normalize_title(opp.title)
        norm_opp_org = normalize_organization(opp.organization)

        # Check year and track guardrails even in deterministic comparison
        full_incoming = f"{organization or ''} {title}"
        full_opp = f"{opp.organization or ''} {opp.title}"

        if not are_years_compatible(full_incoming, full_opp):
            continue
        if not are_tracks_compatible(full_incoming, full_opp):
            continue

        # Case 1A: Both have organizations that match
        if norm_incoming_org and norm_opp_org:
            org_matches = (
                norm_incoming_org == norm_opp_org
                or norm_incoming_org in norm_opp_org
                or norm_opp_org in norm_incoming_org
            )
            if org_matches:
                # Title matches exactly or one is contained in the other
                if (
                    norm_incoming_title == norm_opp_title
                    or (norm_incoming_title and norm_incoming_title in norm_opp_title)
                    or (norm_opp_title and norm_opp_title in norm_incoming_title)
                ):
                    logger.info(
                        "DEDUP_MATCH_DETERMINISTIC | opp_id=%d | org=%s | title=%s",
                        opp.id,
                        opp.organization,
                        opp.title,
                    )
                    return opp

        # Case 1B: No organization provided on one or both, but root title is identical
        if not norm_incoming_org or not norm_opp_org:
            if norm_incoming_title and norm_incoming_title == norm_opp_title:
                logger.info(
                    "DEDUP_MATCH_TITLE_EXACT | opp_id=%d | title=%s",
                    opp.id,
                    opp.title,
                )
                return opp

    # ── Layer 2: Conservative Fuzzy Match ────────────────────
    best_candidate: Optional[Opportunity] = None
    best_score: float = 0.0

    for opp in candidates:
        full_incoming = f"{organization or ''} {title}"
        full_opp = f"{opp.organization or ''} {opp.title}"

        # Guardrail 1: Year must be compatible
        if not are_years_compatible(full_incoming, full_opp):
            continue

        # Guardrail 2: Role track must be compatible
        if not are_tracks_compatible(full_incoming, full_opp):
            continue

        # Guardrail 3: Organization compatibility
        norm_opp_org = normalize_organization(opp.organization)
        if norm_incoming_org and norm_opp_org:
            org_ratio = SequenceMatcher(None, norm_incoming_org, norm_opp_org).ratio()
            org_compatible = (
                norm_incoming_org in norm_opp_org
                or norm_opp_org in norm_incoming_org
                or org_ratio >= 0.75
            )
            if not org_compatible:
                # Organizations clearly conflict — do not merge
                continue

        # Calculate title similarity
        norm_opp_title = normalize_title(opp.title)
        if not norm_incoming_title or not norm_opp_title:
            continue

        title_ratio = SequenceMatcher(None, norm_incoming_title, norm_opp_title).ratio()

        # Conservative threshold: must be >= 0.85
        if title_ratio >= 0.85 and title_ratio > best_score:
            best_score = title_ratio
            best_candidate = opp

    if best_candidate:
        logger.info(
            "DEDUP_MATCH_FUZZY | opp_id=%d | score=%.2f | title=%s",
            best_candidate.id,
            best_score,
            best_candidate.title,
        )
        return best_candidate

    return None
