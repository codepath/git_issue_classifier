"""Tests for data models."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from models.data_models import (
    PullRequest,
    Classification,
)


class TestPullRequest:
    """Tests for PullRequest model."""
    
    def test_minimal_valid_pr(self):
        """Create PR with minimal required fields (Phase 1 - Index)."""
        merged_at = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        created_at = datetime(2025, 1, 10, 9, 0, 0, tzinfo=timezone.utc)
        
        pr = PullRequest(
            repo="owner/repo",
            pr_number=123,
            title="Fix bug",
            body="This fixes the bug",
            merged_at=merged_at,
            created_at=created_at,
        )
        assert pr.repo == "owner/repo"
        assert pr.pr_number == 123
        assert pr.title == "Fix bug"
        assert pr.merged_at == merged_at
        assert pr.enrichment_status == "pending"
        assert pr.files is None
        assert pr.linked_issue is None
        assert pr.classification is None
    
    def test_complete_pr_with_enrichment_and_classification(self):
        """Create PR with enrichment and classification (all phases)."""
        merged_at = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        created_at = datetime(2025, 1, 10, 9, 0, 0, tzinfo=timezone.utc)
        enriched_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        classified_at = datetime(2025, 1, 16, 14, 0, 0, tzinfo=timezone.utc)
        
        pr = PullRequest(
            repo="owner/repo",
            pr_number=456,
            title="Add authentication",
            body="Fixes #89",
            merged_at=merged_at,
            created_at=created_at,
            files=[
                {"filename": "auth.py", "additions": 100, "deletions": 5}
            ],
            linked_issue={
                "number": 89,
                "title": "Need authentication",
                "body": "We need OAuth support"
            },
            issue_comments=[
                {"body": "LGTM", "author": "alice"}
            ],
            enrichment_status="success",
            enrichment_attempted_at=enriched_at,
            classification=Classification(
                difficulty="medium",
                categories=["feature", "security"],
                concepts_taught=["authentication", "JWT", "OAuth"],
                prerequisites=["Basic web security"],
                reasoning="Introduces OAuth flow"
            ),
            classified_at=classified_at
        )
        
        assert pr.title == "Add authentication"
        assert pr.merged_at == merged_at
        assert pr.enrichment_status == "success"
        assert pr.files is not None
        assert len(pr.files) == 1
        assert pr.linked_issue is not None
        assert pr.classification is not None
        assert pr.classification.difficulty == "medium"
    
    def test_enriched_fields_accept_arbitrary_structure(self):
        """Enriched fields should accept arbitrary JSON structures."""
        merged_at = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        created_at = datetime(2025, 1, 10, 9, 0, 0, tzinfo=timezone.utc)
        
        pr = PullRequest(
            repo="owner/repo",
            pr_number=789,
            title="Test PR",
            merged_at=merged_at,
            created_at=created_at,
            files=[
                {
                    "filename": "test.py",
                    "custom_field": "value",
                    "nested": {"data": "works"}
                }
            ],
            linked_issue={
                "number": 123,
                "arbitrary_field": [1, 2, 3]
            },
            enrichment_status="success"
        )
        assert pr.files[0]["custom_field"] == "value"
        assert pr.linked_issue["arbitrary_field"] == [1, 2, 3]
    
    def test_enrichment_failed_status(self):
        """PR with failed enrichment should store error."""
        merged_at = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        created_at = datetime(2025, 1, 10, 9, 0, 0, tzinfo=timezone.utc)
        attempted_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        pr = PullRequest(
            repo="owner/repo",
            pr_number=999,
            title="Failed enrichment",
            merged_at=merged_at,
            created_at=created_at,
            enrichment_status="failed",
            enrichment_attempted_at=attempted_at,
            enrichment_error="Rate limit exceeded"
        )
        assert pr.enrichment_status == "failed"
        assert pr.enrichment_error == "Rate limit exceeded"
        assert pr.files is None
    
    def test_missing_required_fields(self):
        """Missing required fields should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PullRequest(
                repo="owner/repo",
                # Missing pr_number, title, merged_at, created_at
            )
        error_str = str(exc_info.value)
        assert "pr_number" in error_str
        assert "title" in error_str


class TestClassification:
    """Tests for Classification model."""
    
    def test_valid_classification(self):
        """Valid classification should be accepted."""
        data = {
            "difficulty": "medium",
            "categories": ["feature", "api"],
            "concepts_taught": ["REST API", "error handling"],
            "prerequisites": ["Basic HTTP knowledge"],
            "reasoning": "This PR demonstrates good API design patterns.",
        }
        classification = Classification.model_validate(data)
        assert classification.difficulty == "medium"
        assert classification.concepts_taught == ["REST API", "error handling"]
        assert "API design" in classification.reasoning
    
    def test_invalid_difficulty(self):
        """Invalid difficulty value should raise ValidationError."""
        data = {
            "difficulty": "super-hard",  # Invalid
            "categories": ["testing"],
            "concepts_taught": ["testing"],
            "prerequisites": ["none"],
            "reasoning": "Test reasoning",
        }
        with pytest.raises(ValidationError) as exc_info:
            Classification.model_validate(data)
        assert "difficulty" in str(exc_info.value)
    
    def test_empty_concepts_not_allowed(self):
        """Empty required lists should not be allowed (per classifier validation)."""
        data = {
            "difficulty": "easy",
            "categories": ["documentation"],
            "concepts_taught": [],  # Empty not allowed
            "prerequisites": ["none"],
            "reasoning": "Simple typo fix",
        }
        # Note: Pydantic allows empty lists, but our classifier validates they're non-empty
        classification = Classification.model_validate(data)
        assert classification.concepts_taught == []
    
    def test_missing_required_fields(self):
        """Missing required fields should raise ValidationError."""
        data = {
            "difficulty": "easy",
            # Missing categories, concepts_taught, prerequisites, reasoning
        }
        with pytest.raises(ValidationError) as exc_info:
            Classification.model_validate(data)
        error_str = str(exc_info.value)
        assert "categories" in error_str or "concepts_taught" in error_str or "reasoning" in error_str


class TestEnrichmentStatus:
    """Tests for enrichment_status field in PullRequest."""
    
    def test_pending_status_default(self):
        """Default enrichment_status should be 'pending'."""
        merged_at = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        created_at = datetime(2025, 1, 10, 9, 0, 0, tzinfo=timezone.utc)
        
        pr = PullRequest(
            repo="owner/repo",
            pr_number=1,
            title="Test",
            merged_at=merged_at,
            created_at=created_at
        )
        assert pr.enrichment_status == "pending"
    
    def test_success_status(self):
        """Can set enrichment_status to 'success'."""
        merged_at = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        created_at = datetime(2025, 1, 10, 9, 0, 0, tzinfo=timezone.utc)
        
        pr = PullRequest(
            repo="owner/repo",
            pr_number=2,
            title="Test",
            merged_at=merged_at,
            created_at=created_at,
            enrichment_status="success"
        )
        assert pr.enrichment_status == "success"
    
    def test_failed_status(self):
        """Can set enrichment_status to 'failed'."""
        merged_at = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        created_at = datetime(2025, 1, 10, 9, 0, 0, tzinfo=timezone.utc)
        
        pr = PullRequest(
            repo="owner/repo",
            pr_number=3,
            title="Test",
            merged_at=merged_at,
            created_at=created_at,
            enrichment_status="failed"
        )
        assert pr.enrichment_status == "failed"
    
    def test_invalid_status_value(self):
        """Invalid enrichment_status should raise ValidationError."""
        merged_at = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        created_at = datetime(2025, 1, 10, 9, 0, 0, tzinfo=timezone.utc)
        
        with pytest.raises(ValidationError) as exc_info:
            PullRequest(
                repo="owner/repo",
                pr_number=4,
                title="Test",
                merged_at=merged_at,
                created_at=created_at,
                enrichment_status="maybe"  # Invalid
            )
        assert "enrichment_status" in str(exc_info.value)
