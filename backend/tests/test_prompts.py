"""
CareerMail AI — Prompt Formatting Tests.

Tests extraction prompt construction and system prompt integrity.
"""

from app.services.extraction.prompts import SYSTEM_PROMPT, build_extraction_prompt


class TestExtractionPromptBuilder:
    def test_build_prompt_includes_all_fields(self):
        prompt = build_extraction_prompt(
            sender="hackathon@example.com",
            subject="Hackathon Round 2 Invitation",
            received_at="2026-09-08T10:00:00Z",
            body_text="Congratulations! You have advanced to Round 2.",
        )

        assert "From: hackathon@example.com" in prompt
        assert "Subject: Hackathon Round 2 Invitation" in prompt
        assert "Date: 2026-09-08T10:00:00Z" in prompt
        assert "Congratulations! You have advanced to Round 2." in prompt
        assert "--- EMAIL BODY ---" in prompt

    def test_build_prompt_handles_empty_body(self):
        prompt = build_extraction_prompt(
            sender="test@test.com",
            subject="No Body Email",
            received_at="2026-09-08T10:00:00Z",
            body_text="",
        )
        assert "(empty body)" in prompt

    def test_build_prompt_truncates_long_body(self):
        long_body = "x" * 10000
        prompt = build_extraction_prompt(
            sender="test@test.com",
            subject="Very Long Email",
            received_at="2026-09-08T10:00:00Z",
            body_text=long_body,
        )
        # Should truncate to 4000 characters for body
        assert "x" * 4000 in prompt
        assert "x" * 4001 not in prompt


class TestSystemPromptIntegrity:
    def test_system_prompt_rules_present(self):
        assert "EXTRACT ONLY facts" in SYSTEM_PROMPT
        assert "NEVER invent or guess" in SYSTEM_PROMPT
        assert "shortlisted" in SYSTEM_PROMPT
        assert "next_round" in SYSTEM_PROMPT
        assert "action_required" in SYSTEM_PROMPT
        assert "valid JSON" in SYSTEM_PROMPT

    def test_system_prompt_categories_present(self):
        for cat in ["hackathon", "internship", "placement", "college", "scholarship"]:
            assert cat in SYSTEM_PROMPT
