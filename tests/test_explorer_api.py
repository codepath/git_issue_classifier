"""
Tests for the PR Explorer API endpoints.

These tests use FastAPI's TestClient to test the API without
requiring a running server or real Supabase connection.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture
def mock_supabase():
    """Mock SupabaseClient for testing."""
    mock = Mock()
    mock.client = Mock()
    return mock


@pytest.fixture
def client(mock_supabase):
    """Create FastAPI test client with mocked Supabase."""
    # Patch the supabase client in the routes module
    with patch('explorer.routes.supabase', mock_supabase):
        from explorer.app import app
        with TestClient(app) as test_client:
            yield test_client


def setup_pr_query_mocks(mock_result_data, total_count, with_classifications=True):
    """Helper to set up PR query mocks with optional classification data."""
    mock_result = Mock()
    mock_result.data = mock_result_data
    
    # Create mock with count attribute set to actual integer
    mock_count_result = Mock()
    mock_count_result.count = total_count  # This is an integer, not a mock
    
    # Mock classifications for returned PRs (empty by default)
    mock_classifications_result = Mock()
    mock_classifications_result.data = []
    
    mock_classifications_query = Mock()
    mock_classifications_query.in_.return_value = mock_classifications_query
    mock_classifications_query.execute.return_value = mock_classifications_result
    
    # Set up mock chain for PRs
    mock_query = Mock()
    mock_query.in_.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.gte.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.range.return_value = mock_query
    mock_query.execute.return_value = mock_result
    
    # Set up count query - all chained methods return self, execute returns count_result
    mock_count_query = Mock()
    mock_count_query.in_.return_value = mock_count_query
    mock_count_query.eq.return_value = mock_count_query
    mock_count_query.gte.return_value = mock_count_query
    mock_count_query.execute.return_value = mock_count_result  # This should work now
    
    return mock_query, mock_count_query, mock_classifications_query


class TestListPRs:
    """Tests for GET /api/prs endpoint."""

    def test_list_prs_basic(self, client, mock_supabase):
        """Test basic PR list without filters."""
        pr_data = [
            {
                "id": 1,
                "repo": "facebook/react",
                "pr_number": 12345,
                "title": "Fix bug",
                "merged_at": "2024-01-01T00:00:00Z"
            }
        ]
        
        mock_query, mock_count_query, mock_classifications_query = setup_pr_query_mocks(pr_data, 100)

        # Create persistent table mocks (not recreated each time)
        pr_table_mock = Mock()
        pr_table_mock.select.side_effect = [mock_query, mock_count_query]
        
        classifications_table_mock = Mock()
        classifications_table_mock.select.return_value = mock_classifications_query
        
        # Set up table mock to return the same mock instances
        def table_side_effect(table_name):
            if table_name == "classifications":
                return classifications_table_mock
            else:  # pull_requests
                return pr_table_mock
        
        mock_supabase.client.table.side_effect = table_side_effect

        # Make request
        response = client.get("/api/prs")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "prs" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert data["page"] == 1
        assert data["per_page"] == 50
        assert data["total"] == 100
        assert len(data["prs"]) == 1

    def test_list_prs_with_pagination(self, client, mock_supabase):
        """Test PR list with pagination parameters."""
        # Mock Supabase responses
        mock_result = Mock()
        mock_result.data = []

        mock_count_result = Mock()
        mock_count_result.count = 150

        # Set up mock chain
        mock_query = Mock()
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.range.return_value = mock_query
        mock_query.execute.return_value = mock_result

        mock_count_query = Mock()
        mock_count_query.eq.return_value = mock_count_query
        mock_count_query.execute.return_value = mock_count_result

        mock_table = Mock()
        mock_table.select.side_effect = [mock_query, mock_count_query]

        mock_supabase.client.table.return_value = mock_table

        # Make request with pagination
        response = client.get("/api/prs?page=2&per_page=25")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["per_page"] == 25
        assert data["total"] == 150

        # Verify range was called with correct offset
        # Page 2, per_page 25 => offset 25, end 49
        mock_query.range.assert_called_once_with(25, 49)

    def test_list_prs_filtered_by_repo(self, client, mock_supabase):
        """Test PR list filtered by repository."""
        pr_data = [
            {
                "id": 1,
                "repo": "facebook/react",
                "pr_number": 12345,
                "title": "Fix bug",
                "merged_at": "2024-01-01T00:00:00Z"
            }
        ]
        
        mock_query, mock_count_query, mock_classifications_query = setup_pr_query_mocks(pr_data, 50)

        # Create persistent table mocks
        pr_table_mock = Mock()
        pr_table_mock.select.side_effect = [mock_query, mock_count_query]
        
        classifications_table_mock = Mock()
        classifications_table_mock.select.return_value = mock_classifications_query
        
        def table_side_effect(table_name):
            return classifications_table_mock if table_name == "classifications" else pr_table_mock
        
        mock_supabase.client.table.side_effect = table_side_effect

        # Make request with repo filter
        response = client.get("/api/prs?repo=facebook/react")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 50
        assert all(pr["repo"] == "facebook/react" for pr in data["prs"])

        # Verify eq was called with repo filter
        assert mock_query.eq.call_count >= 1

    def test_list_prs_with_cutoff_date(self, client, mock_supabase):
        """Test PR list with cutoff date filter (includes 2-day buffer)."""
        pr_data = [
            {
                "id": 1,
                "repo": "facebook/react",
                "pr_number": 12345,
                "title": "Fix bug",
                "merged_at": "2024-06-17T00:00:00Z"
            }
        ]
        
        mock_query, mock_count_query, mock_classifications_query = setup_pr_query_mocks(pr_data, 25)

        # Create persistent table mocks
        pr_table_mock = Mock()
        pr_table_mock.select.side_effect = [mock_query, mock_count_query]
        
        classifications_table_mock = Mock()
        classifications_table_mock.select.return_value = mock_classifications_query
        
        def table_side_effect(table_name):
            return classifications_table_mock if table_name == "classifications" else pr_table_mock
        
        mock_supabase.client.table.side_effect = table_side_effect

        # Make request with cutoff date (2024-06-15)
        # Backend should add 2 days, filtering by merged_at >= 2024-06-17
        response = client.get("/api/prs?cutoff_date=2024-06-15")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 25

        # Verify gte was called with adjusted date (2024-06-17)
        mock_query.gte.assert_called_once_with("merged_at", "2024-06-17")
        mock_count_query.gte.assert_called_once_with("merged_at", "2024-06-17")

    def test_list_prs_with_invalid_cutoff_date(self, client, mock_supabase):
        """Test that invalid date format returns 400 error."""
        # Make request with invalid date
        response = client.get("/api/prs?cutoff_date=invalid-date")

        # Assertions
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Invalid date format" in data["detail"]

    def test_list_prs_with_sort_order_asc(self, client, mock_supabase):
        """Test PR list sorted in ascending order (oldest first)."""
        pr_data = [
            {
                "id": 1,
                "repo": "facebook/react",
                "pr_number": 100,
                "title": "Old PR",
                "merged_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": 2,
                "repo": "facebook/react",
                "pr_number": 200,
                "title": "Newer PR",
                "merged_at": "2024-06-01T00:00:00Z"
            }
        ]
        
        mock_query, mock_count_query, mock_classifications_query = setup_pr_query_mocks(pr_data, 2)

        # Create persistent table mocks
        pr_table_mock = Mock()
        pr_table_mock.select.side_effect = [mock_query, mock_count_query]
        
        classifications_table_mock = Mock()
        classifications_table_mock.select.return_value = mock_classifications_query
        
        def table_side_effect(table_name):
            return classifications_table_mock if table_name == "classifications" else pr_table_mock
        
        mock_supabase.client.table.side_effect = table_side_effect

        # Make request with ascending sort order
        response = client.get("/api/prs?sort_order=asc")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["prs"]) == 2

        # Verify order was called with desc=False (ascending)
        mock_query.order.assert_called_once_with("merged_at", desc=False)

    def test_list_prs_with_sort_order_desc(self, client, mock_supabase):
        """Test PR list sorted in descending order (newest first)."""
        # Mock Supabase responses
        mock_result = Mock()
        mock_result.data = []

        mock_count_result = Mock()
        mock_count_result.count = 0

        # Set up mock chain
        mock_query = Mock()
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.range.return_value = mock_query
        mock_query.execute.return_value = mock_result

        mock_count_query = Mock()
        mock_count_query.eq.return_value = mock_count_query
        mock_count_query.execute.return_value = mock_count_result

        mock_table = Mock()
        mock_table.select.side_effect = [mock_query, mock_count_query]

        mock_supabase.client.table.return_value = mock_table

        # Make request with explicit descending sort order
        response = client.get("/api/prs?sort_order=desc")

        # Assertions
        assert response.status_code == 200

        # Verify order was called with desc=True (descending)
        mock_query.order.assert_called_once_with("merged_at", desc=True)

    def test_list_prs_default_sort_order(self, client, mock_supabase):
        """Test PR list without sort_order defaults to ascending (oldest first, chronological)."""
        # Mock Supabase responses
        mock_result = Mock()
        mock_result.data = []

        mock_count_result = Mock()
        mock_count_result.count = 0

        # Set up mock chain
        mock_query = Mock()
        mock_query.order.return_value = mock_query
        mock_query.range.return_value = mock_query
        mock_query.execute.return_value = mock_result

        mock_count_query = Mock()
        mock_count_query.execute.return_value = mock_count_result

        mock_table = Mock()
        mock_table.select.side_effect = [mock_query, mock_count_query]

        mock_supabase.client.table.return_value = mock_table

        # Make request WITHOUT sort_order parameter (should default to asc)
        response = client.get("/api/prs")

        # Assertions
        assert response.status_code == 200

        # Verify order was called with desc=False (ascending is default)
        mock_query.order.assert_called_once_with("merged_at", desc=False)

    def test_list_prs_with_invalid_sort_order(self, client, mock_supabase):
        """Test that invalid sort order returns 422 validation error."""
        # Make request with invalid sort order
        response = client.get("/api/prs?sort_order=invalid")

        # Assertions
        # FastAPI returns 422 for validation errors
        assert response.status_code == 422

    def test_list_prs_combined_filters(self, client, mock_supabase):
        """Test PR list with multiple filters combined."""
        # Mock Supabase responses
        mock_result = Mock()
        mock_result.data = []

        mock_count_result = Mock()
        mock_count_result.count = 10

        # Set up mock chain
        mock_query = Mock()
        mock_query.eq.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.range.return_value = mock_query
        mock_query.execute.return_value = mock_result

        mock_count_query = Mock()
        mock_count_query.eq.return_value = mock_count_query
        mock_count_query.gte.return_value = mock_count_query
        mock_count_query.execute.return_value = mock_count_result

        mock_table = Mock()
        mock_table.select.side_effect = [mock_query, mock_count_query]

        mock_supabase.client.table.return_value = mock_table

        # Make request with repo, cutoff date, and sort order
        response = client.get("/api/prs?repo=facebook/react&cutoff_date=2024-01-01&sort_order=asc")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 10

        # Verify all filters were applied
        mock_query.eq.assert_called_with("repo", "facebook/react")
        mock_query.gte.assert_called_with("merged_at", "2024-01-03")  # 2024-01-01 + 2 days
        mock_query.order.assert_called_with("merged_at", desc=False)

    def test_list_prs_with_onboarding_suitability_filter(self, client, mock_supabase):
        """Test PR list filtered by onboarding_suitability."""
        # Mock classifications query for filtering
        mock_classifications_result = Mock()
        mock_classifications_result.data = [
            {"pr_id": 1},
            {"pr_id": 2}
        ]
        
        mock_classifications_filter_query = Mock()
        mock_classifications_filter_query.eq.return_value = mock_classifications_filter_query
        mock_classifications_filter_query.execute.return_value = mock_classifications_result
        
        # Mock classifications for returned PRs (enrichment)
        mock_classifications_for_prs = Mock()
        mock_classifications_for_prs.data = [
            {"pr_id": 1, "onboarding_suitability": "excellent", "difficulty": "easy"},
            {"pr_id": 2, "onboarding_suitability": "excellent", "difficulty": "easy"}
        ]
        
        mock_classifications_enrich_query = Mock()
        mock_classifications_enrich_query.in_.return_value = mock_classifications_enrich_query
        mock_classifications_enrich_query.execute.return_value = mock_classifications_for_prs
        
        # Mock PRs query
        pr_data = [
            {
                "id": 1,
                "repo": "apache/superset",
                "pr_number": 100,
                "title": "Easy PR",
                "merged_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": 2,
                "repo": "apache/superset",
                "pr_number": 200,
                "title": "Another easy PR",
                "merged_at": "2024-01-02T00:00:00Z"
            }
        ]
        
        mock_query, mock_count_query, _ = setup_pr_query_mocks(pr_data, 2)
        
        # Create persistent table mocks
        pr_table_mock = Mock()
        pr_table_mock.select.side_effect = [mock_query, mock_count_query]
        
        classifications_table_mock = Mock()
        classifications_table_mock.select.side_effect = [mock_classifications_filter_query, mock_classifications_enrich_query]
        
        def table_side_effect(table_name):
            return classifications_table_mock if table_name == "classifications" else pr_table_mock
        
        mock_supabase.client.table.side_effect = table_side_effect
        
        # Make request
        response = client.get("/api/prs?onboarding_suitability=excellent&per_page=10")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["prs"]) == 2
        
        # Verify classification data is included
        assert data["prs"][0]["classification"] is not None
        assert data["prs"][0]["classification"]["onboarding_suitability"] == "excellent"

    def test_list_prs_with_difficulty_filter(self, client, mock_supabase):
        """Test PR list filtered by difficulty."""
        # Mock classifications query - no results
        mock_classifications_result = Mock()
        mock_classifications_result.data = []
        
        mock_classifications_query = Mock()
        mock_classifications_query.eq.return_value = mock_classifications_query
        mock_classifications_query.execute.return_value = mock_classifications_result
        
        mock_table = Mock()
        mock_table.select.return_value = mock_classifications_query
        mock_supabase.client.table.return_value = mock_table
        
        # Make request with difficulty filter
        response = client.get("/api/prs?difficulty=trivial")
        
        # Assertions - should return empty result
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["prs"]) == 0

    def test_list_prs_with_multiple_classification_filters(self, client, mock_supabase):
        """Test PR list with multiple classification filters combined."""
        # Mock classifications query for filtering
        mock_classifications_result = Mock()
        mock_classifications_result.data = [{"pr_id": 5}]
        
        mock_classifications_filter_query = Mock()
        mock_classifications_filter_query.eq.return_value = mock_classifications_filter_query
        mock_classifications_filter_query.execute.return_value = mock_classifications_result
        
        # Mock classifications for returned PRs (enrichment)
        mock_classifications_for_prs = Mock()
        mock_classifications_for_prs.data = [
            {
                "pr_id": 5,
                "onboarding_suitability": "excellent",
                "difficulty": "easy",
                "task_clarity": "clear",
                "is_reproducible": "highly likely"
            }
        ]
        
        mock_classifications_enrich_query = Mock()
        mock_classifications_enrich_query.in_.return_value = mock_classifications_enrich_query
        mock_classifications_enrich_query.execute.return_value = mock_classifications_for_prs
        
        # Mock PRs query
        pr_data = [
            {
                "id": 5,
                "repo": "apache/superset",
                "pr_number": 500,
                "title": "Perfect PR",
                "merged_at": "2024-01-01T00:00:00Z"
            }
        ]
        
        mock_query, mock_count_query, _ = setup_pr_query_mocks(pr_data, 1)
        
        # Create persistent table mocks
        pr_table_mock = Mock()
        pr_table_mock.select.side_effect = [mock_query, mock_count_query]
        
        classifications_table_mock = Mock()
        classifications_table_mock.select.side_effect = [mock_classifications_filter_query, mock_classifications_enrich_query]
        
        def table_side_effect(table_name):
            return classifications_table_mock if table_name == "classifications" else pr_table_mock
        
        mock_supabase.client.table.side_effect = table_side_effect
        
        # Make request with all classification filters
        response = client.get(
            "/api/prs?onboarding_suitability=excellent&difficulty=easy"
            "&task_clarity=clear&is_reproducible=highly likely"
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        
        # Verify all classification fields match
        classification = data["prs"][0]["classification"]
        assert classification["onboarding_suitability"] == "excellent"
        assert classification["difficulty"] == "easy"
        assert classification["task_clarity"] == "clear"
        assert classification["is_reproducible"] == "highly likely"

    def test_list_prs_classification_filters_with_other_filters(self, client, mock_supabase):
        """Test combining classification filters with repo/date filters."""
        # Mock classifications query for filtering
        mock_classifications_result = Mock()
        mock_classifications_result.data = [{"pr_id": 10}]
        
        mock_classifications_filter_query = Mock()
        mock_classifications_filter_query.eq.return_value = mock_classifications_filter_query
        mock_classifications_filter_query.execute.return_value = mock_classifications_result
        
        # Mock classifications for returned PRs (empty in this case - no PRs matched other filters)
        mock_classifications_enrich_query = Mock()
        mock_classifications_enrich_query.in_.return_value = mock_classifications_enrich_query
        mock_classifications_enrich_query.execute.return_value = Mock(data=[])
        
        # Mock PRs query (empty result - filtered out by repo/date)
        pr_data = []
        mock_query, mock_count_query, _ = setup_pr_query_mocks(pr_data, 0)
        
        # Create persistent table mocks
        pr_table_mock = Mock()
        pr_table_mock.select.side_effect = [mock_query, mock_count_query]
        
        classifications_table_mock = Mock()
        classifications_table_mock.select.side_effect = [mock_classifications_filter_query, mock_classifications_enrich_query]
        
        def table_side_effect(table_name):
            return classifications_table_mock if table_name == "classifications" else pr_table_mock
        
        mock_supabase.client.table.side_effect = table_side_effect
        
        # Make request with classification + repo + date filters
        response = client.get(
            "/api/prs?onboarding_suitability=excellent&repo=apache/superset"
            "&cutoff_date=2024-01-01&sort_order=asc"
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        # Verify all filters were applied to the query
        mock_query.in_.assert_called()  # PR IDs from classification filter
        mock_query.eq.assert_called_with("repo", "apache/superset")
        mock_query.gte.assert_called_with("merged_at", "2024-01-03")


    def test_list_prs_with_favorite_filter_true(self, client, mock_supabase):
        """Test PR list filtered by is_favorite=true."""
        pr_data = [
            {
                "id": 1,
                "repo": "apache/superset",
                "pr_number": 100,
                "title": "Favorite PR",
                "merged_at": "2024-01-01T00:00:00Z",
                "is_favorite": True
            }
        ]
        
        mock_query, mock_count_query, mock_classifications_query = setup_pr_query_mocks(pr_data, 5)

        # Create persistent table mocks
        pr_table_mock = Mock()
        pr_table_mock.select.side_effect = [mock_query, mock_count_query]
        
        classifications_table_mock = Mock()
        classifications_table_mock.select.return_value = mock_classifications_query
        
        def table_side_effect(table_name):
            return classifications_table_mock if table_name == "classifications" else pr_table_mock
        
        mock_supabase.client.table.side_effect = table_side_effect

        # Make request for favorites only
        response = client.get("/api/prs?is_favorite=true")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        
        # Verify eq was called with is_favorite=True
        mock_query.eq.assert_called_with("is_favorite", True)


class TestFavoriteToggle:
    """Tests for POST /api/prs/{repo}/{pr_number}/favorite endpoint."""

    def test_toggle_favorite_from_false_to_true(self, client, mock_supabase):
        """Test toggling a PR from not favorite to favorite."""
        # Mock get_pr_by_number to return a PR
        mock_pr = {
            "id": 123,
            "repo": "apache/superset",
            "pr_number": 100,
            "title": "Test PR",
            "is_favorite": False
        }
        mock_supabase.get_pr_by_number.return_value = mock_pr

        # Mock update result
        mock_update_result = Mock()
        mock_update_result.data = [{
            **mock_pr,
            "is_favorite": True
        }]

        mock_update_query = Mock()
        mock_update_query.eq.return_value = mock_update_query
        mock_update_query.execute.return_value = mock_update_result

        mock_table = Mock()
        mock_table.update.return_value = mock_update_query

        mock_supabase.client.table.return_value = mock_table

        # Make request
        response = client.post("/api/prs/apache/superset/100/favorite")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["is_favorite"] is True

        # Verify get_pr_by_number was called
        mock_supabase.get_pr_by_number.assert_called_once_with("apache/superset", 100)

        # Verify update was called with new value
        mock_table.update.assert_called_once_with({"is_favorite": True})

    def test_toggle_favorite_from_true_to_false(self, client, mock_supabase):
        """Test toggling a PR from favorite to not favorite."""
        # Mock get_pr_by_number to return a favorited PR
        mock_pr = {
            "id": 123,
            "repo": "apache/superset",
            "pr_number": 100,
            "title": "Test PR",
            "is_favorite": True
        }
        mock_supabase.get_pr_by_number.return_value = mock_pr

        # Mock update result
        mock_update_result = Mock()
        mock_update_result.data = [{
            **mock_pr,
            "is_favorite": False
        }]

        mock_update_query = Mock()
        mock_update_query.eq.return_value = mock_update_query
        mock_update_query.execute.return_value = mock_update_result

        mock_table = Mock()
        mock_table.update.return_value = mock_update_query

        mock_supabase.client.table.return_value = mock_table

        # Make request
        response = client.post("/api/prs/apache/superset/100/favorite")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["is_favorite"] is False

        # Verify update was called with new value (toggled to False)
        mock_table.update.assert_called_once_with({"is_favorite": False})

    def test_toggle_favorite_pr_not_found(self, client, mock_supabase):
        """Test 404 error when PR doesn't exist."""
        # Mock get_pr_by_number to return None
        mock_supabase.get_pr_by_number.return_value = None

        # Make request
        response = client.post("/api/prs/fake/repo/99999/favorite")

        # Assertions
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


class TestLLMPayload:
    """Tests for GET /api/prs/{repo}/{pr_number}/llm_payload endpoint."""

    def test_get_llm_payload_success(self, client, mock_supabase):
        """Test retrieving LLM payload successfully."""
        # Mock the get_pr_by_number method
        mock_pr = {
            "id": 1,
            "repo": "apache/superset",
            "pr_number": 100,
            "title": "Fix CORS bug",
            "body": "This fixes a CORS issue",
            "merged_at": "2024-01-01T00:00:00Z",
            "files": {
                "files": [{
                    "filename": "api/cors.py",
                    "status": "modified",
                    "additions": 5,
                    "deletions": 2,
                    "patch": "@@ -10,7 +10,7 @@\n-old line\n+new line"
                }]
            }
        }
        mock_supabase.get_pr_by_number.return_value = mock_pr

        # Make request
        response = client.get("/api/prs/apache/superset/100/llm_payload")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        # Check all three components are present
        assert "pr_context" in data
        assert "full_prompt" in data
        assert "prompt_template" in data
        
        # Verify pr_context contains PR information
        assert "Fix CORS bug" in data["pr_context"]
        assert "apache/superset" in data["pr_context"]
        assert "api/cors.py" in data["pr_context"]
        
        # Verify full_prompt contains both context and template
        assert "Fix CORS bug" in data["full_prompt"]
        assert "onboarding_suitability" in data["full_prompt"]  # From template
        
        # Verify prompt_template is the classification prompt
        assert "onboarding_suitability" in data["prompt_template"]
        assert "Return ONLY a valid JSON" in data["prompt_template"]

        # Verify get_pr_by_number was called
        mock_supabase.get_pr_by_number.assert_called_once_with("apache/superset", 100)

    def test_get_llm_payload_pr_not_found(self, client, mock_supabase):
        """Test 404 error when PR doesn't exist."""
        # Mock the get_pr_by_number method to return None
        mock_supabase.get_pr_by_number.return_value = None

        # Make request
        response = client.get("/api/prs/fake/repo/99999/llm_payload")

        # Assertions
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


class TestGetSinglePR:
    """Tests for GET /api/prs/{repo}/{pr_number} endpoint."""

    def test_get_pr_success(self, client, mock_supabase):
        """Test retrieving a single PR successfully."""
        # Mock the get_pr_by_number method
        mock_pr = {
            "id": 1,
            "repo": "facebook/react",
            "pr_number": 12345,
            "title": "Fix bug",
            "body": "This fixes a bug",
            "merged_at": "2024-01-01T00:00:00Z",
            "enrichment_status": "success"
        }
        mock_supabase.get_pr_by_number.return_value = mock_pr

        # Make request
        response = client.get("/api/prs/facebook/react/12345")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["repo"] == "facebook/react"
        assert data["pr_number"] == 12345
        assert data["title"] == "Fix bug"

        # Verify method was called correctly
        mock_supabase.get_pr_by_number.assert_called_once_with("facebook/react", 12345)

    def test_get_pr_not_found(self, client, mock_supabase):
        """Test 404 when PR doesn't exist."""
        # Mock the get_pr_by_number method to return None
        mock_supabase.get_pr_by_number.return_value = None

        # Make request
        response = client.get("/api/prs/fake/repo/99999")

        # Assertions
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_get_pr_includes_llm_payload(self, client, mock_supabase):
        """Test that PR detail includes LLM payload for debugging."""
        # Mock the get_pr_by_number method
        mock_pr = {
            "id": 1,
            "repo": "facebook/react",
            "pr_number": 12345,
            "title": "Fix bug",
            "body": "This fixes a bug",
            "merged_at": "2024-01-01T00:00:00Z",
            "enrichment_status": "success",
            "files": {"files": []},
            "linked_issue": None,
            "issue_comments": []
        }
        mock_supabase.get_pr_by_number.return_value = mock_pr

        # Mock the classifications query
        mock_classification_query = Mock()
        mock_classification_result = Mock()
        mock_classification_result.data = []
        mock_classification_query.execute.return_value = mock_classification_result
        mock_classification_query.eq.return_value = mock_classification_query
        
        mock_table = Mock()
        mock_table.select.return_value = mock_classification_query
        mock_supabase.client.table.return_value = mock_table

        # Make request
        response = client.get("/api/prs/facebook/react/12345")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "llm_payload" in data
        # Payload should be a string (or None if generation failed)
        assert data["llm_payload"] is None or isinstance(data["llm_payload"], str)
        if data["llm_payload"]:
            # If payload exists, it should contain the PR title
            assert "Fix bug" in data["llm_payload"]


class TestListRepos:
    """Tests for GET /api/repos endpoint."""

    def test_list_repos(self, client, mock_supabase):
        """Test listing unique repositories."""
        # Mock Supabase response for RPC call (try first)
        mock_rpc = Mock()
        mock_rpc.execute.side_effect = Exception("RPC not available")
        
        # Mock fallback table query
        mock_result = Mock()
        mock_result.data = [
            {"repo": "facebook/react"},
            {"repo": "microsoft/vscode"},
            {"repo": "facebook/react"},  # Duplicate
            {"repo": "torvalds/linux"}
        ]

        mock_query = Mock()
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = mock_result

        mock_table = Mock()
        mock_table.select.return_value = mock_query

        mock_supabase.client.rpc.return_value = mock_rpc
        mock_supabase.client.table.return_value = mock_table

        # Make request
        response = client.get("/api/repos")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "repos" in data
        repos = data["repos"]
        assert len(repos) == 3  # Duplicates removed
        assert "facebook/react" in repos
        assert "microsoft/vscode" in repos
        assert "torvalds/linux" in repos
        # Verify alphabetical sorting
        assert repos == sorted(repos)
