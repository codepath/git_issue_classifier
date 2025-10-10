"""GitHub API client for fetching pull request data.

This module implements both phases of the two-phase fetch workflow:
- Phase 1 (Index): Fetch basic PR metadata from the list endpoint (cheap, reliable)
- Phase 2 (Enrichment): Fetch PR files, diffs, and linked issues (expensive, per-PR)
"""

import logging
import re
import time
from datetime import datetime
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


class GitHubFetcher:
    """Fetch pull request data from GitHub API.
    
    This is a single-class implementation without abstract base (YAGNI principle).
    When GitLab support is added (Milestone 19), we can extract a common interface.
    """
    
    def __init__(self, token: str):
        """Initialize GitHub API client.
        
        Args:
            token: GitHub personal access token for authentication
        """
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    
    def _make_github_request(self, url: str, params: Optional[dict] = None) -> requests.Response:
        """Make GitHub API request with automatic rate limit handling.
        
        If rate limited (429), waits until rate limit resets and retries.
        
        Args:
            url: GitHub API URL to request
            params: Optional query parameters
        
        Returns:
            Response object from requests
            
        Raises:
            requests.HTTPError: On non-rate-limit errors (401, 403, 404, etc.)
        """
        while True:
            response = requests.get(url, headers=self.headers, params=params)
            
            # Log rate limit info
            remaining = response.headers.get("X-RateLimit-Remaining")
            limit = response.headers.get("X-RateLimit-Limit")
            if remaining and limit:
                logger.debug(f"Rate limit: {remaining}/{limit} remaining")
            
            # Handle rate limiting (429)
            if response.status_code == 429:
                reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                current_time = int(time.time())
                wait_seconds = max(reset_time - current_time + 5, 60)  # +5 second buffer, minimum 60s
                
                reset_datetime = datetime.fromtimestamp(reset_time)
                reset_str = reset_datetime.strftime("%H:%M:%S")
                
                logger.warning(
                    f"⏳ Rate limited! Waiting until {reset_str} "
                    f"({wait_seconds/60:.1f} minutes)..."
                )
                time.sleep(wait_seconds)
                logger.info("Rate limit reset - resuming...")
                continue  # Retry the request
            
            # Return response for caller to handle other status codes
            return response
    
    def fetch_pr_list(
        self,
        owner: str,
        repo: str,
        max_pages: int = 10
    ) -> list[dict[str, Any]]:
        """Fetch list of merged pull requests (Phase 1 - Index).
        
        This method fetches basic PR metadata from GitHub's list endpoint,
        which is cheap (1 API call for 100 PRs) and rarely fails.
        
        Uses simple page-based pagination with max_pages limit. This is
        "good enough" for bulk analysis where missing a few PRs is acceptable.
        
        Args:
            owner: Repository owner (e.g., "facebook")
            repo: Repository name (e.g., "react")
            max_pages: Maximum number of pages to fetch (default: 10 = up to 1000 PRs)
        
        Returns:
            List of merged PR dictionaries (raw GitHub API response objects).
            Only includes PRs where merged_at is not None.
        
        Raises:
            requests.HTTPError: On authentication errors (401, 403) or other HTTP errors
        """
        logger.info(
            f"Fetching merged PRs from {owner}/{repo} (max {max_pages} pages)"
        )
        
        all_prs = []
        merged_count = 0
        
        for page in range(1, max_pages + 1):
            url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
            params = {
                "state": "closed",
                "sort": "created",
                "direction": "desc",
                "per_page": 100,
                "page": page
            }
            
            try:
                response = self._make_github_request(url, params=params)
                
                # Handle authentication errors immediately
                if response.status_code in (401, 403):
                    logger.error(
                        f"Authentication error: {response.status_code} - "
                        f"{response.text[:200]}"
                    )
                    response.raise_for_status()
                
                # Raise on other HTTP errors
                response.raise_for_status()
                
                prs = response.json()
                
                # Stop if no more PRs
                if not prs:
                    logger.info(f"No more PRs found at page {page}, stopping pagination")
                    break
                
                # Filter for merged PRs only
                filtered_prs = [pr for pr in prs if pr.get("merged_at") is not None]
                
                merged_count += len(filtered_prs)
                all_prs.extend(filtered_prs)
                
                logger.debug(
                    f"Page {page}: {len(prs)} closed PRs, "
                    f"{len(filtered_prs)} merged (total: {merged_count})"
                )
                
            except requests.RequestException as e:
                logger.error(f"Error fetching page {page}: {e}")
                raise
        
        logger.info(
            f"Fetched {merged_count} merged PRs from {owner}/{repo}"
        )
        
        return all_prs
    
    def fetch_pr_files(
        self,
        owner: str,
        repo: str,
        pr_number: int
    ) -> dict[str, Any]:
        """Fetch changed files with diffs for a PR (Phase 2 - Enrichment).
        
        Returns up to 10 files with patches, truncated to 100 lines each.
        Skips binary files (files without a patch field).
        
        Includes summary metadata to help LLM understand the scale and scope
        of changes, especially when data is truncated.
        
        Args:
            owner: Repository owner (e.g., "facebook")
            repo: Repository name (e.g., "react")
            pr_number: Pull request number
        
        Returns:
            Dict with structure:
            {
                "summary": {
                    "total_files": int,           // All files in the PR
                    "files_with_patches": int,    // Non-binary files with diffs
                    "files_included": int,        // Files actually returned (max 10)
                    "total_additions": int,       // Total lines added (all files)
                    "total_deletions": int,       // Total lines deleted (all files)
                    "truncated": bool             // Whether any file was truncated
                },
                "files": [
                    {
                        "filename": str,
                        "status": str,
                        "additions": int,
                        "deletions": int,
                        "changes": int,
                        "patch": str,
                        "patch_truncated": bool,  // Whether this patch was truncated
                        ... other GitHub API fields ...
                    }
                ]
            }
        
        Raises:
            requests.HTTPError: On authentication errors or other HTTP errors
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        params = {"per_page": 100, "page": 1}
        
        try:
            response = self._make_github_request(url, params=params)
            
            # Handle errors
            if response.status_code in (401, 403):
                logger.error(f"Authentication error: {response.status_code}")
                response.raise_for_status()
            
            response.raise_for_status()
            
            all_files = response.json()
            
            # Calculate aggregate statistics across ALL files
            total_additions = sum(f.get("additions", 0) for f in all_files)
            total_deletions = sum(f.get("deletions", 0) for f in all_files)
            
            # Filter: only files with patches (skip binaries)
            files_with_patches = [f for f in all_files if f.get("patch")]
            
            # Take first 10
            files = files_with_patches[:10]
            
            # Truncate each patch to 100 lines
            for file in files:
                original_patch = file["patch"]
                truncated_patch, was_truncated = self._truncate_patch_with_flag(
                    original_patch, max_lines=100
                )
                file["patch"] = truncated_patch
                file["patch_truncated"] = was_truncated
            
            # Check if file list is truncated (showing fewer files than exist)
            file_list_truncated = len(files_with_patches) > len(files)
            
            # Build result with metadata
            result = {
                "summary": {
                    "total_files": len(all_files),
                    "files_with_patches": len(files_with_patches),
                    "files_included": len(files),
                    "total_additions": total_additions,
                    "total_deletions": total_deletions,
                    "truncated": file_list_truncated
                },
                "files": files
            }
            
            logger.info(
                f"Fetched {len(files)} files for PR #{pr_number} "
                f"({len(files_with_patches)} total with patches, "
                f"{len(all_files)} total files, "
                f"{total_additions}+ {total_deletions}- lines)"
            )
            
            return result
            
        except requests.RequestException as e:
            logger.error(f"Error fetching files for PR #{pr_number}: {e}")
            raise
    
    def extract_issue_numbers(self, pr_body: Optional[str]) -> list[int]:
        """Extract linked issue numbers from PR body.
        
        Searches for common GitHub issue-closing keywords followed by #number.
        Examples: "Fixes #123", "Closes #456", "Resolves #789"
        
        Args:
            pr_body: PR description text (can be None or empty)
        
        Returns:
            List of issue numbers found (empty list if none found)
        """
        if not pr_body:
            return []
        
        # Pattern matches: fix/fixes/fixed/close/closes/closed/resolve/resolves/resolved #123
        pattern = r'(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s+#(\d+)'
        matches = re.findall(pattern, pr_body, re.IGNORECASE)
        
        # Convert to integers and remove duplicates while preserving order
        issue_numbers = []
        seen = set()
        for match in matches:
            num = int(match)
            if num not in seen:
                issue_numbers.append(num)
                seen.add(num)
        
        logger.debug(f"Extracted {len(issue_numbers)} issue numbers from PR body")
        return issue_numbers
    
    def fetch_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int
    ) -> Optional[dict[str, Any]]:
        """Fetch issue metadata (Phase 2 - Enrichment).
        
        Args:
            owner: Repository owner (e.g., "facebook")
            repo: Repository name (e.g., "react")
            issue_number: Issue number
        
        Returns:
            Issue dictionary with fields:
            - number: int
            - title: str
            - body: str
            - state: str ("open" or "closed")
            - labels: list
            - created_at: str
            - closed_at: str or None
            - comments: int (comment count)
            
            Returns None if issue is not found (404 - deleted/private issue).
        
        Raises:
            requests.HTTPError: On authentication errors or other HTTP errors (not 404)
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}"
        
        try:
            response = self._make_github_request(url)
            
            # 404 is expected for deleted/private issues - return None
            if response.status_code == 404:
                logger.debug(f"Issue #{issue_number} not found (404)")
                return None
            
            # Handle auth errors
            if response.status_code in (401, 403):
                logger.error(f"Authentication error: {response.status_code}")
                response.raise_for_status()
            
            response.raise_for_status()
            
            issue = response.json()
            logger.debug(f"Fetched issue #{issue_number}: {issue.get('title', '')[:50]}")
            
            return issue
            
        except requests.RequestException as e:
            logger.error(f"Error fetching issue #{issue_number}: {e}")
            raise
    
    def fetch_issue_comments(
        self,
        owner: str,
        repo: str,
        issue_number: int
    ) -> list[dict[str, Any]]:
        """Fetch comments for an issue (Phase 2 - Enrichment).
        
        Handles pagination to fetch all comments (up to a reasonable limit).
        Most issues have <100 comments, so this typically requires 1 API call.
        
        Args:
            owner: Repository owner (e.g., "facebook")
            repo: Repository name (e.g., "react")
            issue_number: Issue number
        
        Returns:
            List of comment dictionaries. Each comment contains:
            - id: int
            - user: dict (with "login" field)
            - body: str (comment text)
            - created_at: str
            - updated_at: str
            
            Returns empty list if no comments or on error.
        
        Raises:
            requests.HTTPError: On authentication errors or other HTTP errors
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        all_comments = []
        page = 1
        max_pages = 5  # Limit to 500 comments (most issues have far fewer)
        
        try:
            while page <= max_pages:
                params = {"per_page": 100, "page": page}
                response = self._make_github_request(url, params=params)
                
                # Handle auth errors
                if response.status_code in (401, 403):
                    logger.error(f"Authentication error: {response.status_code}")
                    response.raise_for_status()
                
                response.raise_for_status()
                
                comments = response.json()
                
                if not comments:
                    break
                
                all_comments.extend(comments)
                page += 1
            
            logger.debug(f"Fetched {len(all_comments)} comments for issue #{issue_number}")
            return all_comments
            
        except requests.RequestException as e:
            logger.error(f"Error fetching comments for issue #{issue_number}: {e}")
            raise
    
    def _truncate_patch(self, patch: str, max_lines: int = 100) -> str:
        """Truncate patch to maximum number of lines.
        
        Args:
            patch: Unified diff string
            max_lines: Maximum lines to include (default: 100)
        
        Returns:
            Truncated patch with marker if truncated, otherwise original patch
        """
        truncated_patch, _ = self._truncate_patch_with_flag(patch, max_lines)
        return truncated_patch
    
    def _truncate_patch_with_flag(
        self, patch: str, max_lines: int = 100
    ) -> tuple[str, bool]:
        """Truncate patch and return truncation status.
        
        Args:
            patch: Unified diff string
            max_lines: Maximum lines to include (default: 100)
        
        Returns:
            Tuple of (truncated_patch, was_truncated)
        """
        lines = patch.split('\n')
        
        if len(lines) <= max_lines:
            return patch, False
        
        truncated = '\n'.join(lines[:max_lines])
        remaining = len(lines) - max_lines
        
        return f"{truncated}\n... [TRUNCATED: {remaining} more lines]", True
    
    def enrich_pr(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        pr_body: str
    ) -> dict[str, Any]:
        """Fetch all enrichment data for a PR (Phase 2 - Enrichment).
        
        This orchestrates fetching files, linked issue, and issue comments.
        All components are fetched; if any fail, the exception propagates.
        
        Args:
            owner: Repository owner (e.g., "facebook")
            repo: Repository name (e.g., "react")
            pr_number: Pull request number
            pr_body: PR body/description text (for extracting linked issues)
        
        Returns:
            Dict with structure:
            {
                "files": dict,           # From fetch_pr_files()
                "linked_issue": dict,    # From fetch_issue() or None if not found
                "issue_comments": list   # From fetch_issue_comments() or []
            }
        
        Raises:
            requests.HTTPError: On authentication errors or other HTTP errors
        """
        logger.info(f"Enriching PR #{pr_number} in {owner}/{repo}")
        
        # Step 1: Fetch files with diffs
        files = self.fetch_pr_files(owner, repo, pr_number)
        
        # Step 2: Extract and fetch linked issue
        issue_numbers = self.extract_issue_numbers(pr_body)
        linked_issue = None
        issue_comments = []
        
        if issue_numbers:
            issue_number = issue_numbers[0]  # Take first linked issue
            logger.debug(f"PR #{pr_number} links to issue #{issue_number}")
            
            # Fetch issue (returns None if 404)
            linked_issue = self.fetch_issue(owner, repo, issue_number)
            
            # Fetch comments if issue exists
            if linked_issue:
                issue_comments = self.fetch_issue_comments(owner, repo, issue_number)
        else:
            logger.debug(f"PR #{pr_number} has no linked issues")
        
        result = {
            "files": files,
            "linked_issue": linked_issue,
            "issue_comments": issue_comments
        }
        
        logger.info(
            f"Enriched PR #{pr_number}: "
            f"{files['summary']['files_included']} files, "
            f"{'linked issue' if linked_issue else 'no linked issue'}, "
            f"{len(issue_comments)} comments"
        )
        
        return result