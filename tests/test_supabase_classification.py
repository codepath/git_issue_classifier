"""
Tests for Supabase classification methods.

These tests use mocking to avoid requiring a real database connection.
"""

import pytest
from unittest.mock import Mock, MagicMock
from storage.supabase_client import SupabaseClient


class TestSupabaseClassificationMethods:
    """Tests for classification-related Supabase methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a mock Supabase client
        self.mock_supabase = Mock()
        self.client = SupabaseClient.__new__(SupabaseClient)
        self.client.client = self.mock_supabase
        self.client.table_name = "pull_requests"
    
    def test_get_unclassified_prs(self):
        """Test querying unclassified PRs."""
        # Mock the query chain
        mock_query = MagicMock()
        mock_result = Mock()
        mock_result.data = [
            {
                "id": 1,
                "repo": "facebook/react",
                "pr_number": 123,
                "title": "Test PR 1",
                "enrichment_status": "success",
                "classified_at": None  # Not yet classified
            },
            {
                "id": 2,
                "repo": "facebook/react",
                "pr_number": 124,
                "title": "Test PR 2",
                "enrichment_status": "success",
                "classified_at": None  # Not yet classified
            }
        ]
        
        # Set up query chain mock
        self.mock_supabase.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.is_.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.execute.return_value = mock_result
        
        # Call method
        result = self.client.get_unclassified_prs(limit=100, repo="facebook/react")
        
        # Verify it queried correctly
        self.mock_supabase.table.assert_called_with("pull_requests")
        mock_query.eq.assert_any_call("enrichment_status", "success")
        mock_query.is_.assert_called_with("classified_at", "null")
        assert len(result) == 2
        assert result[0]["pr_number"] == 123
    
    def test_save_classification(self):
        """Test saving classification to database."""
        # Mock the update chain
        mock_query = MagicMock()
        mock_result = Mock()
        mock_result.data = [{
            "id": 123,
            "difficulty": "medium",
            "task_clarity": "clear",
            "is_reproducible": "highly likely",
            "onboarding_suitability": "excellent",
            "categories": ["feature", "api"],
            "concepts_taught": ["API design"],
            "prerequisites": ["Basic React"],
            "reasoning": "This adds a new API endpoint."
        }]
        
        self.mock_supabase.table.return_value = mock_query
        mock_query.update.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value = mock_result
        
        # Test data
        pr_data = {
            "repo": "facebook/react",
            "pr_number": 456,
            "title": "Add new feature",
            "body": "Description",
            "merged_at": "2024-01-01T12:00:00Z"
        }
        
        classification = {
            "difficulty": "medium",
            "task_clarity": "clear",
            "is_reproducible": "highly likely",
            "onboarding_suitability": "excellent",
            "categories": ["feature", "api"],
            "concepts_taught": ["API design"],
            "prerequisites": ["Basic React"],
            "reasoning": "This adds a new API endpoint."
        }
        
        # Call method
        result = self.client.save_classification(
            pr_id=123,
            pr_data=pr_data,
            classification=classification
        )
        
        # Verify it called update on pull_requests table
        self.mock_supabase.table.assert_called_with("pull_requests")
        mock_query.update.assert_called_once()
        mock_query.eq.assert_called_with("id", 123)
        
        # Verify the update record structure
        call_args = mock_query.update.call_args[0][0]
        assert call_args["difficulty"] == "medium"
        assert call_args["task_clarity"] == "clear"
        assert call_args["categories"] == ["feature", "api"]
        assert "classified_at" in call_args
    
    def test_get_classification_stats(self):
        """Test getting classification statistics."""
        # Mock the query result with actual classification data
        mock_query = MagicMock()
        mock_result = Mock()
        mock_result.data = [
            {"difficulty": "trivial", "task_clarity": "clear", "is_reproducible": "highly likely", "onboarding_suitability": "excellent"},
            {"difficulty": "trivial", "task_clarity": "clear", "is_reproducible": "maybe", "onboarding_suitability": "excellent"},
            {"difficulty": "easy", "task_clarity": "partial", "is_reproducible": "highly likely", "onboarding_suitability": "excellent"},
            {"difficulty": "medium", "task_clarity": "clear", "is_reproducible": "unclear", "onboarding_suitability": "poor"},
            {"difficulty": "hard", "task_clarity": "poor", "is_reproducible": "maybe", "onboarding_suitability": "poor"},
        ]
        
        # Set up query chain
        self.mock_supabase.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.not_ = mock_query
        mock_query.is_.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value = mock_result
        
        # Call method
        stats = self.client.get_classification_stats(repo="facebook/react")
        
        # Verify it queries pull_requests with difficulty not null
        self.mock_supabase.table.assert_called_with("pull_requests")
        
        # Verify counts
        assert stats["total_classified"] == 5
        assert stats["by_difficulty"]["trivial"] == 2
        assert stats["by_difficulty"]["easy"] == 1
        assert stats["by_difficulty"]["medium"] == 1
        assert stats["by_difficulty"]["hard"] == 1
        assert stats["by_task_clarity"]["clear"] == 3
        assert stats["by_task_clarity"]["partial"] == 1
        assert stats["by_task_clarity"]["poor"] == 1
        assert stats["by_onboarding"]["excellent"] == 3
        assert stats["by_onboarding"]["poor"] == 2

