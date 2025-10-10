"""Tests for GitHub fetcher (Milestone 4 - Phase 1 Index)."""

from unittest.mock import Mock, patch
import pytest
import requests

from fetchers.github import GitHubFetcher


class TestGitHubFetcherInit:
    """Tests for GitHubFetcher initialization."""
    
    def test_init_sets_headers_correctly(self):
        """Verify headers are set correctly with token."""
        token = "ghp_test_token_123"
        fetcher = GitHubFetcher(token=token)
        
        assert fetcher.token == token
        assert fetcher.base_url == "https://api.github.com"
        assert fetcher.headers["Accept"] == "application/vnd.github+json"
        assert fetcher.headers["Authorization"] == f"Bearer {token}"
        assert fetcher.headers["X-GitHub-Api-Version"] == "2022-11-28"


class TestFetchPRList:
    """Tests for fetch_pr_list method."""
    
    def test_fetch_pr_list_filters_merged(self):
        """Verify only merged PRs are returned (no issue filtering in fetcher)."""
        fetcher = GitHubFetcher(token="test_token")
        
        # Mock response with mixed PRs:
        # - Merged PRs (keep all)
        # - Not merged (filter out)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "4999", "X-RateLimit-Limit": "5000"}
        mock_response.json.return_value = [
            {"number": 1, "title": "Good PR", "merged_at": "2025-01-15T10:30:00Z", "body": "Fixes #123"},
            {"number": 2, "title": "No issue", "merged_at": "2025-01-15T10:30:00Z", "body": "No issue ref"},
            {"number": 3, "title": "Multiple issues", "merged_at": "2025-01-16T12:00:00Z", "body": "Fixes #456 and closes #789"},
            {"number": 4, "title": "Not merged", "merged_at": None, "body": "Fixes #999"},
            {"number": 5, "title": "Another good", "merged_at": "2025-01-16T12:00:00Z", "body": "Closes #200"},
        ]
        
        with patch("requests.get", return_value=mock_response) as mock_get:
            result = fetcher.fetch_pr_list("owner", "repo", max_pages=1)
        
        # Verify request was made with correct params
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://api.github.com/repos/owner/repo/pulls"
        assert call_args[1]["params"]["state"] == "closed"
        assert call_args[1]["params"]["per_page"] == 100
        
        # Verify all merged PRs returned (4 merged, 1 not merged)
        assert len(result) == 4
        assert result[0]["number"] == 1
        assert result[1]["number"] == 2
        assert result[2]["number"] == 3
        assert result[3]["number"] == 5
        assert all(pr["merged_at"] is not None for pr in result)
    
    def test_fetch_pr_list_pagination_stops_at_max_pages(self):
        """Verify pagination respects max_pages limit."""
        fetcher = GitHubFetcher(token="test_token")
        
        # Mock response that always returns PRs with single issue
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "4999", "X-RateLimit-Limit": "5000"}
        mock_response.json.return_value = [
            {"number": 1, "title": "PR", "merged_at": "2025-01-15T10:30:00Z", "body": "Fixes #123"}
        ]
        
        with patch("requests.get", return_value=mock_response) as mock_get:
            result = fetcher.fetch_pr_list("owner", "repo", max_pages=3)
        
        # Should make exactly 3 requests (max_pages)
        assert mock_get.call_count == 3
        
        # Verify page numbers increment
        call_params = [call[1]["params"]["page"] for call in mock_get.call_args_list]
        assert call_params == [1, 2, 3]
        
        # Verify result has PRs from all 3 pages
        assert len(result) == 3
    
    def test_fetch_pr_list_pagination_stops_on_empty_response(self):
        """Verify pagination stops when API returns empty list."""
        fetcher = GitHubFetcher(token="test_token")
        
        def mock_get_side_effect(*args, **kwargs):
            """Return PRs on first page, empty on second."""
            page = kwargs["params"]["page"]
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"X-RateLimit-Remaining": "4999", "X-RateLimit-Limit": "5000"}
            
            if page == 1:
                mock_response.json.return_value = [
                    {"number": 1, "title": "PR", "merged_at": "2025-01-15T10:30:00Z", "body": "Fixes #123"}
                ]
            else:
                mock_response.json.return_value = []  # No more PRs
            
            return mock_response
        
        with patch("requests.get", side_effect=mock_get_side_effect) as mock_get:
            result = fetcher.fetch_pr_list("owner", "repo", max_pages=5)
        
        # Should make only 2 requests (stops on empty)
        assert mock_get.call_count == 2
        
        # Should have 1 PR from first page
        assert len(result) == 1
        assert result[0]["number"] == 1
    
    def test_auth_error_raises_exception(self):
        """Verify 401/403 auth errors raise exceptions."""
        fetcher = GitHubFetcher(token="invalid_token")
        
        # Mock 401 Unauthorized response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Limit": "5000"}
        mock_response.text = "Bad credentials"
        mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
        
        with patch("requests.get", return_value=mock_response):
            with pytest.raises(requests.HTTPError):
                fetcher.fetch_pr_list("owner", "repo", max_pages=1)
        
        # Test 403 Forbidden
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        
        with patch("requests.get", return_value=mock_response):
            with pytest.raises(requests.HTTPError):
                fetcher.fetch_pr_list("owner", "repo", max_pages=1)
    
    def test_returns_raw_dicts_not_models(self):
        """Verify method returns raw dicts (not Pydantic models)."""
        fetcher = GitHubFetcher(token="test_token")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "4999", "X-RateLimit-Limit": "5000"}
        mock_response.json.return_value = [
            {
                "number": 123,
                "title": "Test PR",
                "merged_at": "2025-01-15T10:30:00Z",
                "body": "PR description. Fixes #456",
                "user": {"login": "testuser"},
                "labels": [{"name": "bug"}]
            }
        ]
        
        with patch("requests.get", return_value=mock_response):
            result = fetcher.fetch_pr_list("owner", "repo", max_pages=1)
        
        # Should return raw dict, not Pydantic model
        assert isinstance(result, list)
        assert isinstance(result[0], dict)
        assert result[0]["number"] == 123
        assert result[0]["title"] == "Test PR"
        # Verify all fields from API are preserved
        assert "user" in result[0]
        assert "labels" in result[0]


class TestExtractIssueNumbers:
    """Tests for _extract_issue_numbers method."""
    
    def test_extract_single_issue(self):
        """Test extracting a single issue reference."""
        fetcher = GitHubFetcher(token="test_token")
        
        result = fetcher.extract_issue_numbers("Fixes #123")
        assert result == [123]
    
    def test_extract_multiple_issues(self):
        """Test extracting multiple issue references."""
        fetcher = GitHubFetcher(token="test_token")
        
        result = fetcher.extract_issue_numbers("Fixes #123 and closes #456")
        assert result == [123, 456]
    
    def test_extract_no_issues(self):
        """Test with no issue references."""
        fetcher = GitHubFetcher(token="test_token")
        
        result = fetcher.extract_issue_numbers("This is a PR without issue refs")
        assert result == []
    
    def test_extract_with_none_body(self):
        """Test with None as PR body."""
        fetcher = GitHubFetcher(token="test_token")
        
        result = fetcher.extract_issue_numbers(None)
        assert result == []
    
    def test_extract_case_insensitive(self):
        """Test that extraction is case insensitive."""
        fetcher = GitHubFetcher(token="test_token")
        
        result = fetcher.extract_issue_numbers("FIXES #123, Closes #456, resolves #789")
        assert result == [123, 456, 789]
    
    def test_extract_removes_duplicates(self):
        """Test that duplicate issue numbers are removed."""
        fetcher = GitHubFetcher(token="test_token")
        
        result = fetcher.extract_issue_numbers("Fixes #123, closes #123, fixes #456")
        assert result == [123, 456]


class TestFetchPRFiles:
    """Tests for fetch_pr_files method."""
    
    def test_fetch_files_success(self):
        """Test successfully fetching PR files."""
        fetcher = GitHubFetcher(token="test_token")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "4999"}
        mock_response.json.return_value = [
            {
                "filename": "app.py",
                "status": "modified",
                "additions": 5,
                "deletions": 2,
                "changes": 7,
                "patch": "@@ -1,3 +1,5 @@\n+import os\n def main():\n     pass"
            },
            {
                "filename": "test.py",
                "status": "added",
                "additions": 10,
                "deletions": 0,
                "changes": 10,
                "patch": "@@ -0,0 +1,10 @@\n+def test():\n+    pass"
            }
        ]
        
        with patch("requests.get", return_value=mock_response):
            result = fetcher.fetch_pr_files("owner", "repo", 123)
        
        # Check structure
        assert "summary" in result
        assert "files" in result
        
        # Check summary
        assert result["summary"]["total_files"] == 2
        assert result["summary"]["files_with_patches"] == 2
        assert result["summary"]["files_included"] == 2
        assert result["summary"]["total_additions"] == 15
        assert result["summary"]["total_deletions"] == 2
        assert result["summary"]["truncated"] == False
        
        # Check files
        assert len(result["files"]) == 2
        assert result["files"][0]["filename"] == "app.py"
        assert result["files"][0]["patch_truncated"] == False
        assert result["files"][1]["filename"] == "test.py"
        assert result["files"][1]["patch_truncated"] == False
    
    def test_fetch_files_skips_binaries(self):
        """Test that files without patches (binaries) are skipped."""
        fetcher = GitHubFetcher(token="test_token")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "4999"}
        mock_response.json.return_value = [
            {
                "filename": "app.py",
                "status": "modified",
                "additions": 5,
                "deletions": 2,
                "patch": "@@ -1,3 +1,5 @@\n+import os\n def main():\n     pass"
            },
            {
                "filename": "image.png",
                "status": "added",
                "additions": 0,
                "deletions": 0,
                # No patch field for binary
            },
            {
                "filename": "test.py",
                "status": "added",
                "additions": 10,
                "deletions": 0,
                "patch": "@@ -0,0 +1,10 @@\n+def test():\n+    pass"
            }
        ]
        
        with patch("requests.get", return_value=mock_response):
            result = fetcher.fetch_pr_files("owner", "repo", 123)
        
        # Check summary reflects all files but only non-binaries included
        assert result["summary"]["total_files"] == 3
        assert result["summary"]["files_with_patches"] == 2
        assert result["summary"]["files_included"] == 2
        
        # Should only return 2 files (skipped the binary)
        assert len(result["files"]) == 2
        assert result["files"][0]["filename"] == "app.py"
        assert result["files"][1]["filename"] == "test.py"
    
    def test_fetch_files_limits_to_10(self):
        """Test that only first 10 files with patches are returned."""
        fetcher = GitHubFetcher(token="test_token")
        
        # Create 15 files with patches
        files = []
        for i in range(15):
            files.append({
                "filename": f"file{i}.py",
                "status": "modified",
                "additions": 1,
                "deletions": 0,
                "patch": f"@@ -1,1 +1,2 @@\n+line {i}"
            })
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "4999"}
        mock_response.json.return_value = files
        
        with patch("requests.get", return_value=mock_response):
            result = fetcher.fetch_pr_files("owner", "repo", 123)
        
        # Check summary shows all 15 but only 10 included
        assert result["summary"]["total_files"] == 15
        assert result["summary"]["files_with_patches"] == 15
        assert result["summary"]["files_included"] == 10
        assert result["summary"]["total_additions"] == 15
        assert result["summary"]["total_deletions"] == 0
        assert result["summary"]["truncated"] == True  # File list is truncated
        
        # Should only return first 10
        assert len(result["files"]) == 10
        assert result["files"][0]["filename"] == "file0.py"
        assert result["files"][9]["filename"] == "file9.py"
    
    def test_fetch_files_truncates_patches(self):
        """Test that patches are truncated to 100 lines."""
        fetcher = GitHubFetcher(token="test_token")
        
        # Create a patch with 150 lines
        patch_lines = [f"line {i}" for i in range(150)]
        long_patch = '\n'.join(patch_lines)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "4999"}
        mock_response.json.return_value = [
            {
                "filename": "large_file.py",
                "status": "modified",
                "additions": 150,
                "deletions": 0,
                "patch": long_patch
            }
        ]
        
        with patch("requests.get", return_value=mock_response):
            result = fetcher.fetch_pr_files("owner", "repo", 123)
        
        # File list is NOT truncated (only 1 file, all shown)
        assert result["summary"]["truncated"] == False
        
        # But the individual patch was truncated
        file = result["files"][0]
        assert file["patch_truncated"] == True
        assert "... [TRUNCATED: 50 more lines]" in file["patch"]
        lines = file["patch"].split('\n')
        # Should have 100 lines + 1 truncation marker line
        assert len(lines) == 101


class TestFetchIssue:
    """Tests for fetch_issue method."""
    
    def test_fetch_issue_success(self):
        """Test successfully fetching an issue."""
        fetcher = GitHubFetcher(token="test_token")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "number": 123,
            "title": "Test Issue",
            "body": "Issue description",
            "state": "closed",
            "labels": [{"name": "bug"}],
            "created_at": "2025-01-01T00:00:00Z",
            "closed_at": "2025-01-02T00:00:00Z",
            "comments": 5
        }
        
        with patch("requests.get", return_value=mock_response):
            result = fetcher.fetch_issue("owner", "repo", 123)
        
        assert result is not None
        assert result["number"] == 123
        assert result["title"] == "Test Issue"
        assert result["state"] == "closed"
    
    def test_fetch_issue_not_found(self):
        """Test that 404 returns None (deleted/private issue)."""
        fetcher = GitHubFetcher(token="test_token")
        
        mock_response = Mock()
        mock_response.status_code = 404
        
        with patch("requests.get", return_value=mock_response):
            result = fetcher.fetch_issue("owner", "repo", 999999)
        
        assert result is None


class TestFetchIssueComments:
    """Tests for fetch_issue_comments method."""
    
    def test_fetch_comments_success(self):
        """Test successfully fetching issue comments."""
        fetcher = GitHubFetcher(token="test_token")
        
        # Mock to return comments on first page, empty on second (stops pagination)
        call_count = 0
        def mock_get_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = Mock()
            mock_response.status_code = 200
            
            if call_count == 1:
                mock_response.json.return_value = [
                    {
                        "id": 1,
                        "user": {"login": "user1"},
                        "body": "First comment",
                        "created_at": "2025-01-01T00:00:00Z"
                    },
                    {
                        "id": 2,
                        "user": {"login": "user2"},
                        "body": "Second comment",
                        "created_at": "2025-01-02T00:00:00Z"
                    }
                ]
            else:
                mock_response.json.return_value = []  # Stop pagination
            
            return mock_response
        
        with patch("requests.get", side_effect=mock_get_side_effect):
            result = fetcher.fetch_issue_comments("owner", "repo", 123)
        
        assert len(result) == 2
        assert result[0]["body"] == "First comment"
        assert result[1]["user"]["login"] == "user2"
    
    def test_fetch_comments_empty(self):
        """Test fetching comments when there are none."""
        fetcher = GitHubFetcher(token="test_token")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        
        with patch("requests.get", return_value=mock_response):
            result = fetcher.fetch_issue_comments("owner", "repo", 123)
        
        assert result == []


class TestTruncatePatch:
    """Tests for _truncate_patch helper method."""
    
    def test_truncate_patch_no_truncation_needed(self):
        """Test that short patches are not truncated."""
        fetcher = GitHubFetcher(token="test_token")
        
        patch = "line 1\nline 2\nline 3"
        result = fetcher._truncate_patch(patch, max_lines=100)
        
        assert result == patch
        assert "TRUNCATED" not in result
    
    def test_truncate_patch_truncates_long_patches(self):
        """Test that long patches are truncated correctly."""
        fetcher = GitHubFetcher(token="test_token")
        
        lines = [f"line {i}" for i in range(150)]
        patch = '\n'.join(lines)
        
        result = fetcher._truncate_patch(patch, max_lines=100)
        
        # Should have first 100 lines + truncation marker
        result_lines = result.split('\n')
        assert len(result_lines) == 101
        assert result_lines[0] == "line 0"
        assert result_lines[99] == "line 99"
        assert "... [TRUNCATED: 50 more lines]" in result_lines[100]
