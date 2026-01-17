"""
Pydantic models for LLM input/output.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class LabelOutput(BaseModel):
    """LLM output schema for document labeling."""

    doc_type: str = Field(
        ...,
        description="Document type from controlled vocabulary"
    )
    title: str = Field(
        ...,
        description="Human-readable title for the document"
    )
    canonical_filename: str = Field(
        ...,
        description="Suggested canonical filename (without extension)"
    )
    suggested_tags: List[str] = Field(
        default_factory=list,
        description="List of relevant tags"
    )
    target_group_path: str = Field(
        ...,
        description="Target taxonomy path (e.g., '03 Financial/Bank Statements')"
    )
    date: Optional[str] = Field(
        None,
        description="Document date in ISO format (YYYY-MM-DD)"
    )
    issuer: Optional[str] = Field(
        None,
        description="Issuer or source of the document"
    )
    source: Optional[str] = Field(
        None,
        description="Additional source information"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0 to 1.0)"
    )
    why: str = Field(
        ...,
        description="Brief explanation of labeling decision (1-2 sentences)"
    )


class LabelingContext(BaseModel):
    """Context provided to LLM for labeling."""

    filename: str
    parent_folders: List[str]
    extracted_text: Optional[str] = None
    file_size: int
    mime_type: Optional[str] = None
    mtime: int
    available_doc_types: List[str]
    available_tags: List[str]
    taxonomy: List[str]
    family_members: List[str] = []
