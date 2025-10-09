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


class TestListPRs:
    """Tests for GET /api/prs endpoint."""

    def test_list_prs_basic(self, client, mock_supabase):
        """Test basic PR list without filters."""
        # Mock Supabase responses
        mock_result = Mock()
        mock_result.data = [
            {
                "id": 1,
                "repo": "facebook/react",
                "pr_number": 12345,
                "title": "Fix bug",
                "merged_at": "2024-01-01T00:00:00Z"
            }
        ]

        mock_count_result = Mock()
        mock_count_result.count = 100

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
        # Mock Supabase responses
        mock_result = Mock()
        mock_result.data = [
            {
                "id": 1,
                "repo": "facebook/react",
                "pr_number": 12345,
                "title": "Fix bug",
                "merged_at": "2024-01-01T00:00:00Z"
            }
        ]

        mock_count_result = Mock()
        mock_count_result.count = 50

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

        # Make request with repo filter
        response = client.get("/api/prs?repo=facebook/react")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 50
        assert all(pr["repo"] == "facebook/react" for pr in data["prs"])

        # Verify eq was called with repo filter
        assert mock_query.eq.call_count >= 1


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


class TestListRepos:
    """Tests for GET /api/repos endpoint."""

    def test_list_repos(self, client, mock_supabase):
        """Test listing unique repositories."""
        # Mock Supabase response
        mock_result = Mock()
        mock_result.data = [
            {"repo": "facebook/react"},
            {"repo": "microsoft/vscode"},
            {"repo": "facebook/react"},  # Duplicate
            {"repo": "torvalds/linux"}
        ]

        mock_query = Mock()
        mock_query.execute.return_value = mock_result

        mock_table = Mock()
        mock_table.select.return_value = mock_query

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
