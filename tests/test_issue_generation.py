"""
Tests for issue generation feature.

These tests verify:
1. Migration added required columns
2. Prompt template exists and is properly formatted
3. Issue generation endpoints work correctly
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from fastapi.testclient import TestClient
from classifier.prompt_template import ISSUE_GENERATION_PROMPT


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
    with patch('backend.routes.supabase', mock_supabase):
        from backend.app import app
        with TestClient(app) as test_client:
            yield test_client


class TestIssueGenerationPrompt:
    """Tests for issue generation prompt template."""
    
    def test_issue_generation_prompt_exists(self):
        """Verify ISSUE_GENERATION_PROMPT constant is defined."""
        assert ISSUE_GENERATION_PROMPT is not None
        assert isinstance(ISSUE_GENERATION_PROMPT, str)
        assert len(ISSUE_GENERATION_PROMPT) > 0
    
    def test_issue_generation_prompt_has_placeholders(self):
        """Verify prompt contains required placeholders."""
        assert "{pr_context}" in ISSUE_GENERATION_PROMPT
        assert "{classification_info}" in ISSUE_GENERATION_PROMPT
    
    def test_issue_generation_prompt_formats_correctly(self):
        """Test that prompt can be formatted with sample data."""
        sample_pr_context = """
        PULL REQUEST METADATA
        Repo: test/repo
        PR #123: Fix button overflow
        
        DESCRIPTION:
        Users report button text overflow in Japanese locale.
        """
        
        sample_classification = """
        Difficulty: easy
        Task Clarity: clear
        Onboarding Suitability: excellent
        Categories: bug-fix, ui/ux
        Concepts Taught: CSS layout, internationalization
        Prerequisites: Basic HTML/CSS
        Reasoning: Simple CSS fix with clear reproduction steps.
        """
        
        # Should format without errors
        result = ISSUE_GENERATION_PROMPT.format(
            pr_context=sample_pr_context,
            classification_info=sample_classification
        )
        
        assert sample_pr_context in result
        assert sample_classification in result
        assert "{pr_context}" not in result  # Should be replaced
        assert "{classification_info}" not in result  # Should be replaced
    
    def test_issue_generation_prompt_structure(self):
        """Verify prompt includes key sections and instructions."""
        # Check for key sections
        assert "Motivation" in ISSUE_GENERATION_PROMPT
        assert "Current Behavior" in ISSUE_GENERATION_PROMPT
        assert "Expected Behavior" in ISSUE_GENERATION_PROMPT
        assert "Verification" in ISSUE_GENERATION_PROMPT
        
        # Check for important guidelines
        assert "Reproduction Steps" in ISSUE_GENERATION_PROMPT
        assert "Acceptance Criteria" in ISSUE_GENERATION_PROMPT
        assert "markdown" in ISSUE_GENERATION_PROMPT.lower()
        
        # Check difficulty considerations mentioned
        assert "trivial" in ISSUE_GENERATION_PROMPT.lower()
        assert "easy" in ISSUE_GENERATION_PROMPT.lower()
        assert "medium" in ISSUE_GENERATION_PROMPT.lower()
        assert "hard" in ISSUE_GENERATION_PROMPT.lower()


class TestDatabaseMigration:
    """Tests for database schema migration (integration tests)."""
    
    def test_migration_script_exists(self):
        """Verify migration script file exists."""
        from pathlib import Path
        migration_file = Path(__file__).parent.parent / "setup" / "migrations" / "001_add_issue_generation_columns.py"
        assert migration_file.exists()
        assert migration_file.is_file()
    
    def test_migration_is_executable(self):
        """Verify migration script has execute permissions."""
        from pathlib import Path
        import os
        migration_file = Path(__file__).parent.parent / "setup" / "migrations" / "001_add_issue_generation_columns.py"
        assert os.access(migration_file, os.X_OK)


# Note: Actual database column verification would require database connection.
# These are skipped for unit tests but should be verified manually or in integration tests.


class TestIssueGenerationEndpoints:
    """Tests for issue generation API endpoints."""
    
    def test_get_pr_context_endpoint_success(self, client, mock_supabase):
        """Test GET /api/prs/{repo}/{pr_number}/context endpoint."""
        # Mock PR data with classification
        mock_pr = {
            "id": 1,
            "repo": "test/repo",
            "pr_number": 123,
            "title": "Fix button overflow",
            "body": "This fixes the button overflow issue",
            "classified_at": "2025-10-11T10:00:00Z",  # Important: marks PR as classified
            "difficulty": "easy",
            "task_clarity": "clear",
            "is_reproducible": "highly likely",
            "onboarding_suitability": "excellent",
            "categories": ["bug-fix", "ui/ux"],
            "concepts_taught": ["CSS layout"],
            "prerequisites": ["Basic HTML/CSS"],
            "reasoning": "Simple CSS fix"
        }
        mock_supabase.get_pr_by_number.return_value = mock_pr
        
        # Make request
        response = client.get("/api/prs/test/repo/123/context")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "pr_context" in data
        assert "classification_info" in data
        assert "Difficulty: easy" in data["classification_info"]
        assert "test/repo" in data["pr_context"]
    
    def test_get_pr_context_endpoint_404(self, client, mock_supabase):
        """Test GET /api/prs/{repo}/{pr_number}/context when PR not found."""
        mock_supabase.get_pr_by_number.return_value = None
        
        response = client.get("/api/prs/test/repo/999/context")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_get_pr_context_endpoint_no_classification(self, client, mock_supabase):
        """Test GET /api/prs/{repo}/{pr_number}/context with unclassified PR."""
        mock_pr = {
            "id": 1,
            "repo": "test/repo",
            "pr_number": 123,
            "title": "Fix button overflow",
            "body": "This fixes the button overflow issue"
            # No classification fields
        }
        mock_supabase.get_pr_by_number.return_value = mock_pr
        
        response = client.get("/api/prs/test/repo/123/context")
        
        assert response.status_code == 200
        data = response.json()
        assert data["classification_info"] == "No classification available"
    
    def test_get_default_issue_prompt_endpoint(self, client):
        """Test GET /api/prompts/issue-generation endpoint."""
        response = client.get("/api/prompts/issue-generation")
        
        assert response.status_code == 200
        data = response.json()
        assert "prompt_template" in data
        assert len(data["prompt_template"]) > 0
        assert "{pr_context}" in data["prompt_template"]
        assert "{classification_info}" in data["prompt_template"]
    
    @patch("backend.routes.LLMClient")
    def test_generate_issue_endpoint_success(self, mock_llm_class, client, mock_supabase):
        """Test POST /api/prs/{repo}/{pr_number}/generate-issue endpoint."""
        # Mock PR data
        mock_pr = {
            "id": 1,
            "repo": "test/repo",
            "pr_number": 123,
            "title": "Fix button overflow",
            "body": "This fixes the button overflow issue",
            "difficulty": "easy",
            "task_clarity": "clear",
            "is_reproducible": "highly likely",
            "onboarding_suitability": "excellent",
            "categories": ["bug-fix"],
            "concepts_taught": ["CSS layout"],
            "prerequisites": ["Basic HTML/CSS"],
            "reasoning": "Simple CSS fix"
        }
        mock_supabase.get_pr_by_number.return_value = mock_pr
        
        # Mock database update
        mock_update_result = MagicMock()
        mock_update_result.execute.return_value = None
        mock_supabase.client.table.return_value.update.return_value.eq.return_value = mock_update_result
        
        # Mock LLM response
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_issue.return_value = "# Fix Button Overflow\n\n## Motivation\n..."
        mock_llm_class.return_value = mock_llm_instance
        
        # Make request
        response = client.post("/api/prs/test/repo/123/generate-issue")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "issue_markdown" in data
        assert "generated_at" in data
        assert "# Fix Button Overflow" in data["issue_markdown"]
        
        # Verify LLM was called
        mock_llm_instance.generate_issue.assert_called_once()
    
    @patch("backend.routes.LLMClient")
    def test_generate_issue_endpoint_with_custom_prompt(self, mock_llm_class, client, mock_supabase):
        """Test POST /api/prs/{repo}/{pr_number}/generate-issue with custom prompt."""
        # Mock PR data
        mock_pr = {
            "id": 1,
            "repo": "test/repo",
            "pr_number": 123,
            "title": "Fix button overflow",
            "body": "This fixes the button overflow issue",
            "difficulty": "easy"
        }
        mock_supabase.get_pr_by_number.return_value = mock_pr
        
        # Mock database update
        mock_update_result = MagicMock()
        mock_update_result.execute.return_value = None
        mock_supabase.client.table.return_value.update.return_value.eq.return_value = mock_update_result
        
        # Mock LLM response
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_issue.return_value = "# Custom Issue\n..."
        mock_llm_class.return_value = mock_llm_instance
        
        # Make request with custom prompt
        custom_prompt = "Custom prompt: {pr_context}\n{classification_info}"
        response = client.post(
            "/api/prs/test/repo/123/generate-issue",
            json={"custom_prompt_template": custom_prompt}
        )
        
        # Verify response
        assert response.status_code == 200
        
        # Verify LLM was called (custom prompt should be used)
        mock_llm_instance.generate_issue.assert_called_once()
        call_args = mock_llm_instance.generate_issue.call_args[0][0]
        assert "Custom prompt:" in call_args
    
    def test_generate_issue_endpoint_404(self, client, mock_supabase):
        """Test POST /api/prs/{repo}/{pr_number}/generate-issue when PR not found."""
        mock_supabase.get_pr_by_number.return_value = None
        
        response = client.post("/api/prs/test/repo/999/generate-issue")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_get_generated_issue_endpoint_success(self, client, mock_supabase):
        """Test GET /api/prs/{repo}/{pr_number}/generated-issue endpoint."""
        # Mock PR with generated issue
        mock_pr = {
            "id": 1,
            "repo": "test/repo",
            "pr_number": 123,
            "generated_issue": "# Fix Button Overflow\n\n## Motivation\n...",
            "issue_generated_at": "2025-10-11T10:30:00Z"
        }
        mock_supabase.get_pr_by_number.return_value = mock_pr
        
        # Make request
        response = client.get("/api/prs/test/repo/123/generated-issue")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "issue_markdown" in data
        assert "generated_at" in data
        assert "# Fix Button Overflow" in data["issue_markdown"]
        assert data["generated_at"] == "2025-10-11T10:30:00Z"
    
    def test_get_generated_issue_endpoint_404_pr_not_found(self, client, mock_supabase):
        """Test GET /api/prs/{repo}/{pr_number}/generated-issue when PR not found."""
        mock_supabase.get_pr_by_number.return_value = None
        
        response = client.get("/api/prs/test/repo/999/generated-issue")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_get_generated_issue_endpoint_404_no_issue(self, client, mock_supabase):
        """Test GET /api/prs/{repo}/{pr_number}/generated-issue when no issue generated."""
        # Mock PR without generated issue
        mock_pr = {
            "id": 1,
            "repo": "test/repo",
            "pr_number": 123,
            "generated_issue": None
        }
        mock_supabase.get_pr_by_number.return_value = mock_pr
        
        response = client.get("/api/prs/test/repo/123/generated-issue")
        
        assert response.status_code == 404
        assert "no issue generated" in response.json()["detail"].lower()

