"""
Prompt templates for LLM labeling.
"""

import hashlib
import json
from typing import List

from .models import LabelingContext


SYSTEM_PROMPT = """You are a document classification assistant helping to organize a personal document library.

Your task is to analyze documents and provide structured metadata including:
- Document type (from a controlled vocabulary)
- A clear, descriptive title
- Suggested canonical filename
- Relevant tags
- Target taxonomy folder path
- Date (if discernible)
- Issuer/source (if applicable)
- Confidence score
- Brief explanation of your reasoning

Be precise and consistent. When uncertain, express lower confidence rather than guessing.
Always respond with valid JSON only, no additional text."""


def get_labeling_prompt(context: LabelingContext) -> tuple[str, str]:
    """
    Generate labeling prompt from context.

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    # Truncate text if too long
    text_excerpt = context.extracted_text or ""
    max_chars = 8000
    if len(text_excerpt) > max_chars:
        text_excerpt = text_excerpt[:max_chars] + "\n\n[... truncated ...]"

    user_prompt = f"""Analyze this document and provide classification metadata.

DOCUMENT INFORMATION:
- Filename: {context.filename}
- Parent folders: {' > '.join(context.parent_folders)}
- File size: {context.file_size} bytes
- MIME type: {context.mime_type or 'unknown'}

EXTRACTED TEXT (first {max_chars} chars):
{text_excerpt or '[No text extracted]'}

AVAILABLE DOCUMENT TYPES:
{', '.join(context.available_doc_types)}

AVAILABLE TAXONOMY:
{chr(10).join(f'  - {t}' for t in context.taxonomy)}

SUGGESTED TAGS:
{', '.join(context.available_tags)}

OUTPUT FORMAT:
Respond with ONLY a JSON object matching this schema:
{{
  "doc_type": "<type from available list>",
  "title": "<descriptive title>",
  "canonical_filename": "<YYYY-MM-DD__Domain__Issuer__Title format without extension>",
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
            available_doc_types=["type"],
            available_tags=["tag"],
            taxonomy=["01 Category"],
        )
    )
    return compute_prompt_hash(template[0], template[1])
