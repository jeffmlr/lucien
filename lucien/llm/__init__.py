"""
LLM client and prompt management (Phase 2: AI Labeling).

Provides interface to LM Studio for document labeling and categorization.
"""

from .client import LLMClient
from .models import LabelOutput
from .prompts import get_labeling_prompt

__all__ = ["LLMClient", "LabelOutput", "get_labeling_prompt"]
