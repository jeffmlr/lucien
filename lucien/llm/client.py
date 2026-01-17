"""
LLM client for LM Studio integration.

Uses OpenAI-compatible API to communicate with local LM Studio instance.
"""

import json
from typing import Optional

from openai import OpenAI
from pydantic import ValidationError

from ..config import LucienSettings
from .models import LabelOutput, LabelingContext
from .prompts import get_labeling_prompt, get_prompt_version


class LLMClient:
    """Client for LM Studio LLM interactions."""

    def __init__(self, config: LucienSettings):
        """Initialize LLM client with configuration."""
        self.config = config
        self.client = OpenAI(
            base_url=config.llm.base_url,
            api_key="not-needed",  # LM Studio doesn't require API key
        )

    def should_escalate(self, context: LabelingContext, initial_result: Optional[LabelOutput] = None) -> bool:
        """
        Determine if request should be escalated to larger model.

        Args:
            context: Labeling context
            initial_result: Result from initial model (if available)

        Returns:
            True if should use escalation model
        """
        # Always escalate for sensitive doc types
        if initial_result and initial_result.doc_type in self.config.llm.escalation_doc_types:
            return True

        # Escalate if confidence is low
        if initial_result and initial_result.confidence < self.config.llm.escalation_threshold:
            return True

        # Escalate if critical fields missing
        if initial_result and (not initial_result.date or not initial_result.issuer):
            # Only escalate for doc types where these fields are expected
            if initial_result.doc_type in ["financial", "tax", "medical", "insurance", "legal"]:
                return True

        return False

    def label_document(
        self,
        context: LabelingContext,
        use_escalation: bool = False,
    ) -> LabelOutput:
        """
        Label a document using LLM.

        Args:
            context: Document context for labeling
            use_escalation: If True, use escalation model

        Returns:
            LabelOutput with classification metadata

        Raises:
            Exception: If LLM call fails or response is invalid
        """
        # Select model
        model = self.config.llm.escalation_model if use_escalation else self.config.llm.default_model

        # Generate prompts
        system_prompt, user_prompt = get_labeling_prompt(context)

        # Call LLM with retries
        max_retries = self.config.llm.max_retries
        last_error = None

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.1,  # Low temperature for consistency
                    max_tokens=1000,
                    timeout=self.config.llm.timeout,
                )

                # Extract JSON response
                content = response.choices[0].message.content.strip()

                # Try to parse JSON (handle potential markdown wrapping)
                if content.startswith("```"):
                    # Remove markdown code block
                    content = content.strip("`").strip()
                    if content.startswith("json"):
                        content = content[4:].strip()

                # Parse and validate with Pydantic
                label_data = json.loads(content)
                label = LabelOutput(**label_data)

                # Validate doc_type is from allowed vocabulary
                if label.doc_type not in context.available_doc_types:
                    # Try to find a close match or fall back to "other"
                    original_type = label.doc_type
                    label.doc_type = "other"
                    label.why = f"[Auto-corrected from '{original_type}'] {label.why}"

                return label

            except (json.JSONDecodeError, ValidationError) as e:
                last_error = f"Invalid JSON response: {e}"
                # Retry on JSON/validation errors
                continue

            except Exception as e:
                last_error = f"LLM call failed: {e}"
                # Retry on other errors
                continue

        # All retries exhausted
        raise Exception(f"Failed to label document after {max_retries} attempts. Last error: {last_error}")

    def label_with_escalation(self, context: LabelingContext) -> tuple[LabelOutput, bool]:
        """
        Label document with automatic escalation logic.

        First tries default model. If escalation criteria are met,
        retries with larger model.

        Args:
            context: Document context for labeling

        Returns:
            Tuple of (LabelOutput, escalated: bool)
        """
        # Try default model first
        initial_result = self.label_document(context, use_escalation=False)

        # Check if escalation is needed
        if self.should_escalate(context, initial_result):
            # Retry with escalation model
            escalated_result = self.label_document(context, use_escalation=True)
            return escalated_result, True

        return initial_result, False

    def get_prompt_version(self) -> str:
        """Get current prompt version hash for tracking."""
        return get_prompt_version()


# TODO: Implement in Milestone 3 (v0.3)
# - Error handling improvements
# - Retry with exponential backoff
# - Rate limiting
# - Batch processing
# - Embedding support for similarity clustering
