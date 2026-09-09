"""
CareerMail AI — AI Email Composer Prompts.

Contains system instructions and prompt formatting for generating context-aware,
fact-faithful career email drafts.

Strict Rules Enforced:
  1. Never invent recipient email addresses. Derive solely from provided source sender or reply-to.
  2. If no valid recipient email exists in context, return an empty list: "to": [].
  3. Never fabricate facts, dates, qualifications, or commitments not provided in the context.
  4. Return valid JSON only.
"""

from __future__ import annotations

import json
from typing import Any

EMAIL_COMPOSER_SYSTEM_PROMPT = """You are CareerMail AI Email Copilot, an expert career communications assistant for college students and professionals.
Your job is to generate a professional, context-aware email draft based on a specific career opportunity and the user's natural language instruction.

## Critical Safety & Anti-Hallucination Rules:
1. RECIPIENT ADDRESS SAFETY:
   - NEVER invent, hallucinate, or assume email addresses.
   - You may ONLY use recipient addresses explicitly provided in the OPPORTUNITY CONTEXT (e.g., from 'source_sender' or 'contact_emails').
   - If no recipient email is explicitly provided in the context, set "to": []. The user will supply it manually.
2. FACTUAL FIDELITY:
   - NEVER invent deadlines, interview dates, qualifications, commitments, or facts not present in the context or instruction.
   - If personal details are needed that are not in context (e.g., phone number, portfolio link, full legal name), use bracketed placeholders like "[Your Name]", "[Your Phone Number]", "[Link to Project/Resume]".
3. PROFESSIONAL STRUCTURE & TONE:
   - Clear subject line (prefixed with 'Re: ' if replying to an existing thread).
   - Polite salutation (e.g. 'Dear [Name or Hiring Team]').
   - Concise, respectful body stating the exact purpose clearly.
   - Professional closing and sign-off.

## Output Format:
Return ONLY a valid JSON object with these exact keys (no markdown code blocks, no extraneous text):
{
  "to": ["recipient@example.com"],
  "cc": [],
  "bcc": [],
  "subject": "Concise and relevant subject line",
  "body_text": "Salutation,\n\nBody text adhering strictly to user instruction...\n\nSincerely,\n[Your Name]"
}
"""


def build_composer_prompt(
    opportunity_context: dict[str, Any],
    instruction: str,
) -> str:
    """Build the user prompt containing opportunity context and user instruction.

    Args:
        opportunity_context: Dict containing title, organization, category, status,
                             deadline, source_sender, source_subject, body_snippet.
        instruction: Natural language instruction from the user.

    Returns:
        Formatted prompt string.
    """
    title = opportunity_context.get("title", "Career Opportunity")
    org = opportunity_context.get("organization") or "Organization"
    category = opportunity_context.get("category", "general")
    status = opportunity_context.get("status", "active")
    deadline = opportunity_context.get("deadline") or "Not specified"
    source_sender = opportunity_context.get("source_sender") or ""
    source_subject = opportunity_context.get("source_subject") or ""
    body_snippet = (opportunity_context.get("source_body") or "")[:2000]

    context_summary = {
        "title": title,
        "organization": org,
        "category": category,
        "status": status,
        "deadline": str(deadline),
        "source_sender": source_sender,
        "source_subject": source_subject,
        "email_context_snippet": body_snippet,
    }

    return f"""Draft an email based on the following verified opportunity context and user instruction.

=== OPPORTUNITY CONTEXT ===
{json.dumps(context_summary, indent=2)}
=== END OPPORTUNITY CONTEXT ===

=== USER INSTRUCTION ===
{instruction.strip()}
=== END USER INSTRUCTION ===

Follow all anti-hallucination rules. If source_sender is empty, return "to": []. Return ONLY valid JSON."""
