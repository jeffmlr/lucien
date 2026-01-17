"""
Prompt templates for LLM labeling.
"""

import hashlib
import json
from typing import List

from .models import LabelingContext


SYSTEM_PROMPT = """You are a document classification assistant helping to organize a personal document library.

Your task is to analyze documents and provide structured metadata. Follow these rules precisely:

DOCUMENT TYPE:
- You MUST use ONLY a doc_type from the provided list - never invent new types
- ALWAYS prefer the MOST SPECIFIC type that fits:
  * Utility bills (electric, gas, water) → "utility" (NOT "financial")
  * Bank statements → "bank_statement" (NOT "financial")
  * Tax forms → specific type like "w2", "1099", "1040" (NOT "tax")
  * Medical bills/EOBs → "insurance_eob" or "medical" as appropriate
- Use generic types ("financial", "medical", "other") ONLY when no specific type applies
- If nothing fits well, use "other" or "uncategorized"

TITLE:
- Create a clear, human-readable title describing the document's content
- Include key identifiers (date range, account type, etc.)
- Include family member's first name if document is specific to one person (use names from FAMILY MEMBERS list only)

CANONICAL FILENAME FORMAT:
- Format: YYYY-MM-DD-Category-Issuer-Description
- Use HYPHENS (-) to separate the four main fields
- Use UNDERSCORES (_) within multi-word values
- Each field:
  * Date: YYYY-MM-DD (from document date)
  * Category: Top-level category (Financial, Medical, Insurance, Home, etc.)
  * Issuer: Organization name with underscores (Chase_Bank, Unum, Centerpoint_Energy)
  * Description: Brief document type, 1-3 words (Statement, LTC_Claim, Utility_Bill)
- Family member names: Include ONLY if document is specific to one person and the family has multiple members
  * Use first name only from the FAMILY MEMBERS list provided
  * Add as suffix: Description_Name (e.g., LTC_Claim_Nancy, W2_Jeff)
  * Do NOT include names for shared household documents (utility bills, mortgage, etc.)
- NEVER include:
  * Full names or names not in the family members list
  * Month/year in Description when already in Date prefix
  * File extension
  * Spaces
- Examples:
  * 2024-03-15-Financial-Chase_Bank-Statement
  * 2023-05-17-Insurance-Unum-LTC_Claim_Nancy
  * 2023-07-06-Home-Centerpoint_Energy-Utility_Bill
  * 2024-01-15-Medical-Memorial_Hermann-Lab_Results_Jeff
  * 2024-04-15-Taxes-IRS-W2_Jamie

DATE:
- Use the document's issue/creation date, NOT the period it covers
- For a 2022 tax form received in April 2023, use 2023-04-XX (when received/created)
- For statements, use the statement date shown on the document
- If no date is discernible, use null

ISSUER:
- The organization or person who CREATED/ISSUED the document
- For receipts: the merchant/store (Target, Amazon), NOT the payment method
- For statements: the bank/company issuing the statement
- For medical: the healthcare provider, NOT the insurance company

TAGS - Use from these categories:
- Domain: finances, healthcare, taxes, utilities, dental, investment, insurance, legal
- Document type: receipt, invoice, payment, bills, form:1099, form:w2, statement
- Provider: use the issuer name as a tag when it's a recurring provider (e.g., capital_one, WCID17)
- Status: archived (historical/inactive), action_required (needs response), recurring (regular document)
- Year: add the tax/fiscal year when relevant (e.g., 2024, 2025)
- Apply 1-4 relevant tags, focusing on what helps with search and filtering

CONFIDENCE SCORING:
- 0.95-1.0: Clear, unambiguous document with all fields extractable
- 0.85-0.94: Confident but minor uncertainty (e.g., exact date unclear)
- 0.70-0.84: Moderate confidence, some guessing involved
- Below 0.70: Significant uncertainty, may need human review

Always respond with valid JSON only, no additional text."""


def get_labeling_prompt(context: LabelingContext) -> tuple[str, str]:
    """
    Generate labeling prompt from context.

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    # Truncate text if too long
    # LM Studio default context is often 4K-8K tokens
    # Use 8000 chars (~2000 tokens) + prompt overhead to stay safe
    text_excerpt = context.extracted_text or ""
    max_chars = 8000  # ~2000 tokens, safe for most LM Studio configs

    if len(text_excerpt) > max_chars:
        # Take 70% from beginning, 30% from end to capture headers and signatures
        head_chars = int(max_chars * 0.7)
        tail_chars = max_chars - head_chars
        text_excerpt = (
            text_excerpt[:head_chars] +
            "\n\n[... middle section omitted ...]\n\n" +
            text_excerpt[-tail_chars:]
        )

    user_prompt = f"""Analyze this document and provide classification metadata.

DOCUMENT INFORMATION:
- Filename: {context.filename}
- Parent folders: {' > '.join(context.parent_folders)}
- File size: {context.file_size} bytes
- MIME type: {context.mime_type or 'unknown'}

EXTRACTED TEXT:
{text_excerpt or '[No text extracted]'}

AVAILABLE DOCUMENT TYPES:
{', '.join(context.available_doc_types)}

AVAILABLE TAXONOMY:
{chr(10).join(f'  - {t}' for t in context.taxonomy)}

FAMILY MEMBERS:
{', '.join(context.family_members) if context.family_members else 'None configured'}

SUGGESTED TAGS:
{', '.join(context.available_tags)}

OUTPUT FORMAT:
Respond with ONLY a JSON object matching this schema:
{{
  "doc_type": "<type from available list>",
  "title": "<descriptive title>",
  "canonical_filename": "<YYYY-MM-DD-Category-Issuer-Title, no redundant month/year in title>",
  "suggested_tags": ["<tag1>", "<tag2>"],
  "target_group_path": "<taxonomy path, e.g., '03 Financial/Bank Statements'>",
  "date": "<YYYY-MM-DD or null>",
  "issuer": "<issuer/source name or null>",
  "source": "<additional source info or null>",
  "confidence": <0.0 to 1.0>,
  "why": "<1-2 sentence explanation>"
}}

Respond with ONLY the JSON, no markdown formatting, no additional text."""

    return SYSTEM_PROMPT, user_prompt


def compute_prompt_hash(system_prompt: str, user_prompt_template: str) -> str:
    """
    Compute hash of prompt template for versioning.

    Args:
        system_prompt: System prompt text
        user_prompt_template: User prompt template (without dynamic content)

    Returns:
        SHA256 hash of prompts
    """
    combined = f"{system_prompt}\n\n{user_prompt_template}"
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def get_prompt_version() -> str:
    """Get current prompt version hash."""
    # Use static template parts for versioning
    template = get_labeling_prompt(
        LabelingContext(
            filename="example.pdf",
            parent_folders=["folder"],
            file_size=1000,
            mtime=0,
            available_doc_types=["type"],
            available_tags=["tag"],
            taxonomy=["01 Category"],
            family_members=["Member"],
        )
    )
    return compute_prompt_hash(template[0], template[1])
