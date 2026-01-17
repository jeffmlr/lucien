"""
LLM client and prompt management (Phase 2: AI Labeling).

Provides interface to LM Studio for document labeling and categorization.
"""

from .client import LLMClient
from .models import LabelOutput, LabelingContext
from .prompts import get_labeling_prompt, get_prompt_version
from .pipeline import LabelingPipeline

__all__ = [
    "LLMClient",
    "LabelOutput",
    "LabelingContext",
    "LabelingPipeline",
    "get_labeling_prompt",
    "get_prompt_version",
]
