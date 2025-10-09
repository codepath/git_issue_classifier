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
        # Mock the main query for PRs
        mock_pr_query = MagicMock()
        mock_pr_result = Mock()
        mock_pr_result.data = [
            {
                "id": 1,
                "repo": "facebook/react",
                "pr_number": 123,
                "title": "Test PR 1",
                "enrichment_status": "success"
            },
            {
                "id": 2,
                "repo": "facebook/react",
                "pr_number": 124,
                "title": "Test PR 2",
                "enrichment_status": "success"
            }
        ]
        
        # Mock the classification check queries (no classifications exist)
        mock_classification_result = Mock()
        mock_classification_result.data = []
        
        # Set up mock to return different things based on table name
        def table_side_effect(table_name):
            if table_name == "pull_requests":
                mock_chain = MagicMock()
                mock_chain.select.return_value = mock_chain
                mock_chain.eq.return_value = mock_chain
                mock_chain.order.return_value = mock_chain
                mock_chain.limit.return_value = mock_chain
                mock_chain.execute.return_value = mock_pr_result
                return mock_chain
            elif table_name == "classifications":
                mock_chain = MagicMock()
                mock_chain.select.return_value = mock_chain
                mock_chain.eq.return_value = mock_chain
                mock_chain.execute.return_value = mock_classification_result
                return mock_chain
        
        self.mock_supabase.table.side_effect = table_side_effect
        
        # Call method
        result = self.client.get_unclassified_prs(limit=100, repo="facebook/react")
        
        # Verify it queried correctly
        self.mock_supabase.table.assert_called()
        assert len(result) == 2
        assert result[0]["pr_number"] == 123
    
    def test_save_classification(self):
        """Test saving classification to database."""
        # Mock the upsert chain
        mock_query = MagicMock()
        mock_result = Mock()
        mock_result.data = [{
            "id": 1,
            "pr_id": 123,
            "difficulty": "medium",
            "categories": ["feature", "api"],
        }]
        
        self.mock_supabase.table.return_value = mock_query
        mock_query.upsert.return_value = mock_query
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
        
        # Verify it called upsert
        self.mock_supabase.table.assert_called_with("classifications")
        mock_query.upsert.assert_called_once()
        
        # Verify the record structure
        call_args = mock_query.upsert.call_args[0][0]
        assert call_args["pr_id"] == 123
        assert call_args["difficulty"] == "medium"
        assert call_args["categories"] == ["feature", "api"]
        assert "github_url" in call_args
        assert "facebook/react" in call_args["github_url"]
    
    def test_get_classification_stats(self):
        """Test getting classification statistics."""
        # Mock count queries
        mock_query = MagicMock()
        
        # Mock total count
        total_result = Mock()
        total_result.count = 100
        
        # Mock difficulty counts
        trivial_result = Mock()
        trivial_result.count = 10
        easy_result = Mock()
        easy_result.count = 30
        medium_result = Mock()
        medium_result.count = 40
        hard_result = Mock()
        hard_result.count = 20
        
        # Set up query chain
        self.mock_supabase.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute.side_effect = [
            total_result,
            trivial_result,
            easy_result,
            medium_result,
            hard_result
        ]
        
        # Call method
        stats = self.client.get_classification_stats(repo="facebook/react")
        
        # Verify
        assert stats["total_classified"] == 100
        assert stats["trivial"] == 10
        assert stats["easy"] == 30
        assert stats["medium"] == 40
        assert stats["hard"] == 20

