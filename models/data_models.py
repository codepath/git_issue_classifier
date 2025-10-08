"""Data models for GitHub/GitLab PR and issue data."""

from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel


class Classification(BaseModel):
    """LLM classification output structure.
    
    This is our controlled output format that the LLM will populate.
    """
    difficulty: Literal["easy", "medium", "hard"]
    concepts: list[str]
    reasoning: str


class PullRequest(BaseModel):
    """PR record matching two-phase Supabase schema.
    
    This model supports a two-phase workflow:
    - Phase 1 (Index): Basic PR metadata from list endpoint (cheap, reliable)
    - Phase 2 (Enrichment): Files, diffs, linked issues (expensive, can fail per-PR)
    
    This allows resuming enrichment on failures without re-indexing.
    """
    
    # Database ID
    id: Optional[int] = None  # BIGSERIAL in Postgres
    
    # Phase 1: Basic fields (from index - always present)
    repo: str  # e.g., "facebook/react"
    pr_number: int
    title: str
    body: Optional[str] = None  # PR description (may contain linked issue refs)
    merged_at: datetime
    created_at: datetime
    
    # Phase 2: Enriched data (nullable - fetched separately)
    files: Optional[list[dict[str, Any]]] = None  # Changed files with diffs
    linked_issue: Optional[dict[str, Any]] = None  # Issue details
    issue_comments: Optional[list[dict[str, Any]]] = None  # Issue comments
    
    # Enrichment tracking
    enrichment_status: Literal["pending", "success", "failed"] = "pending"
    enrichment_attempted_at: Optional[datetime] = None
    enrichment_error: Optional[str] = None
    
    # Classification (Phase 3)
    classification: Optional[Classification] = None
    classified_at: Optional[datetime] = None
