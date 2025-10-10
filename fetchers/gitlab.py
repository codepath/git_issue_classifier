"""GitLab API client for fetching merge request data.

This module implements both phases of the two-phase fetch workflow:
- Phase 1 (Index): Fetch basic MR metadata from the list endpoint (cheap, reliable)
- Phase 2 (Enrichment): Fetch MR diffs and linked issues (expensive, per-MR)

Key differences from GitHub:
- Uses PRIVATE-TOKEN header instead of Authorization Bearer
- state='merged' filter (not 'closed' + filter)
- Has /closes_issues endpoint (first-class issue tracking!)
- Returns 'iid' (internal ID) not 'number'
- Supports cross-project issues
"""

import logging
import re
import time
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)


class GitLabFetcher:
    """Fetch merge request data from GitLab API.
    
    Parallel implementation to GitHubFetcher with similar method signatures.
    """
    
    def __init__(self, token: str):
        """Initialize GitLab API client.
        
        Args:
            token: GitLab personal access token (private token)
        """
        self.token = token
        self.base_url = "https://gitlab.com/api/v4"
        self.headers = {
            "Accept": "application/json",
            "PRIVATE-TOKEN": token  # Different from GitHub!
        }
    
    def _make_gitlab_request(self, url: str, params: Optional[dict] = None) -> requests.Response:
        """Make GitLab API request with automatic rate limit handling.
        
        If rate limited (429), waits and retries.
        
        Args:
            url: GitLab API URL to request
            params: Optional query parameters
        
        Returns:
            Response object from requests
            
        Raises:
            requests.HTTPError: On non-rate-limit errors (401, 403, 404, etc.)
        """
        while True:
            response = requests.get(url, headers=self.headers, params=params)
            
            # Log rate limit info (GitLab uses different headers than GitHub)
            remaining = response.headers.get("RateLimit-Remaining")
            limit = response.headers.get("RateLimit-Limit")
            if remaining and limit:
                logger.debug(f"Rate limit: {remaining}/{limit} remaining")
            
            # Handle rate limiting (429)
            if response.status_code == 429:
                # GitLab may provide Retry-After header
                retry_after = int(response.headers.get("Retry-After", 60))
                
                logger.warning(
                    f"⏳ Rate limited! Waiting {retry_after} seconds..."
                )
                time.sleep(retry_after)
                logger.info("Rate limit reset - resuming...")
                continue  # Retry the request
            
            # Return response for caller to handle other status codes
            return response
    
    def fetch_mr_list(
        self,
        owner: str,
        repo: str,
        max_pages: int = 10
    ) -> list[dict[str, Any]]:
        """Fetch list of merged merge requests (Phase 1 - Index).
        
        This method fetches basic MR metadata from GitLab's list endpoint,
        which is cheap (1 API call for 100 MRs) and rarely fails.
        
        Uses simple page-based pagination with max_pages limit.
        
        Args:
            owner: Repository owner/organization (e.g., "gitlab-org")
            repo: Repository name (e.g., "gitlab")
            max_pages: Maximum number of pages to fetch (default: 10 = up to 1000 MRs)
        
        Returns:
            List of merged MR dictionaries (raw GitLab API response objects).
            Only includes MRs where merged_at is not None.
        
        Raises:
            requests.HTTPError: On authentication errors (401, 403) or other HTTP errors
        """
        # URL-encode project path: gitlab-org/gitlab -> gitlab-org%2Fgitlab
        project_id = quote(f"{owner}/{repo}", safe='')
        
        logger.info(
            f"Fetching merged MRs from {owner}/{repo} (max {max_pages} pages)"
        )
        
        all_mrs = []
        merged_count = 0
        
        for page in range(1, max_pages + 1):
            url = f"{self.base_url}/projects/{project_id}/merge_requests"
            params = {
                "state": "merged",  # Direct filter! (Not 'closed' like GitHub)
                "order_by": "created_at",
                "sort": "desc",
                "per_page": 100,
                "page": page
            }
            
            try:
                response = self._make_gitlab_request(url, params=params)
                
                # Handle authentication errors immediately
                if response.status_code in (401, 403):
                    logger.error(
                        f"Authentication error: {response.status_code} - "
                        f"{response.text[:200]}"
                    )
                    response.raise_for_status()
                
                # Raise on other HTTP errors
                response.raise_for_status()
                
                mrs = response.json()
                
                # Stop if no more MRs
                if not mrs:
                    logger.info(f"No more MRs found at page {page}, stopping pagination")
                    break
                
                # All MRs returned should be merged (we filtered state=merged)
                merged_count += len(mrs)
                all_mrs.extend(mrs)
                
                logger.debug(
                    f"Page {page}: {len(mrs)} merged MRs (total: {merged_count})"
                )
                
                # Check if there's a next page
                if not response.headers.get("x-next-page"):
                    logger.info(f"No more pages (reached end at page {page})")
                    break
                
            except requests.RequestException as e:
                logger.error(f"Error fetching page {page}: {e}")
                raise
        
        logger.info(
            f"Fetched {merged_count} merged MRs from {owner}/{repo}"
        )
        
        return all_mrs
    
    def fetch_mr_diffs(
        self,
        owner: str,
        repo: str,
        mr_iid: int
    ) -> dict[str, Any]:
        """Fetch changed files with diffs for an MR (Phase 2 - Enrichment).
        
        Returns up to 10 files with diffs, truncated to 100 lines each.
        Skips files without diffs (e.g., binary files).
        
        Args:
            owner: Repository owner (e.g., "gitlab-org")
            repo: Repository name (e.g., "gitlab")
            mr_iid: Merge request internal ID (iid, not id!)
        
        Returns:
            Dict with structure:
            {
                "summary": {
                    "total_files": int,
                    "files_with_diffs": int,
                    "files_included": int,
                    "truncated": bool
                },
                "files": [
                    {
                        "old_path": str,
                        "new_path": str,
                        "diff": str,
                        "new_file": bool,
                        "renamed_file": bool,
                        "deleted_file": bool,
                        "diff_truncated": bool
                    }
                ]
            }
        
        Raises:
            requests.HTTPError: On authentication errors or other HTTP errors
        """
        project_id = quote(f"{owner}/{repo}", safe='')
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}/diffs"
        params = {"per_page": 100, "page": 1}
        
        try:
            response = self._make_gitlab_request(url, params=params)
            
            # Handle errors
            if response.status_code in (401, 403):
                logger.error(f"Authentication error: {response.status_code}")
                response.raise_for_status()
            
            response.raise_for_status()
            
            all_diffs = response.json()
            
            # Filter: only files with diffs (skip those without)
            files_with_diffs = [f for f in all_diffs if f.get("diff")]
            
            # Take first 10
            files = files_with_diffs[:10]
            
            # Truncate each diff to 100 lines
            for file in files:
                original_diff = file["diff"]
                truncated_diff, was_truncated = self._truncate_diff_with_flag(
                    original_diff, max_lines=100
                )
                file["diff"] = truncated_diff
                file["diff_truncated"] = was_truncated
            
            # Check if file list is truncated (showing fewer files than exist)
            file_list_truncated = len(files_with_diffs) > len(files)
            
            # Build result with metadata
            result = {
                "summary": {
                    "total_files": len(all_diffs),
                    "files_with_diffs": len(files_with_diffs),
                    "files_included": len(files),
                    "truncated": file_list_truncated
                },
                "files": files
            }
            
            logger.info(
                f"Fetched {len(files)} files for MR !{mr_iid} "
                f"({len(files_with_diffs)} total with diffs, "
                f"{len(all_diffs)} total files)"
            )
            
            return result
            
        except requests.RequestException as e:
            logger.error(f"Error fetching diffs for MR !{mr_iid}: {e}")
            raise
    
    def extract_issue_numbers(self, mr_description: Optional[str]) -> list[int]:
        """Extract linked issue numbers from MR description (Phase 1 hint).
        
        Searches for common GitLab issue-closing keywords followed by #number or issue URLs.
        Examples: "Fixes #123", "Closes https://gitlab.com/.../issues/456"
        
        Note: This is a Phase 1 hint for prioritization. The actual linked issues
        come from the /closes_issues endpoint in Phase 2, which is 100% accurate.
        
        Args:
            mr_description: MR description text (can be None or empty)
        
        Returns:
            List of issue numbers found (empty list if none found)
        """
        if not mr_description:
            return []
        
        # Pattern matches:
        # - fix/fixes/close/closes/resolve/resolves #123
        # - Full issue URLs: https://gitlab.com/.../issues/123
        patterns = [
            r'(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)[s]?\s+#(\d+)',
            r'https://[^\s]+/-/issues/(\d+)'
        ]
        
        matches = []
        for pattern in patterns:
            matches.extend(re.findall(pattern, mr_description, re.IGNORECASE))
        
        # Convert to integers and remove duplicates while preserving order
        issue_numbers = []
        seen = set()
        for match in matches:
            num = int(match)
            if num not in seen:
                issue_numbers.append(num)
                seen.add(num)
        
        logger.debug(f"Extracted {len(issue_numbers)} issue numbers from MR description (hint)")
        return issue_numbers
    
    def fetch_closes_issues(
        self,
        owner: str,
        repo: str,
        mr_iid: int
    ) -> list[dict[str, Any]]:
        """Fetch issues that will be closed by this MR (Phase 2 - Enrichment).
        
        This is GitLab's first-class issue tracking endpoint! Much better than GitHub.
        Returns full issue objects directly - no need to fetch them separately.
        
        Supports cross-project issues automatically.
        
        Args:
            owner: Repository owner (e.g., "gitlab-org")
            repo: Repository name (e.g., "gitlab")
            mr_iid: Merge request internal ID
        
        Returns:
            List of issue dictionaries. Each issue contains:
            - iid: int (internal ID)
            - title: str
            - description: str
            - state: str ("opened" or "closed")
            - labels: list
            - created_at: str
            - closed_at: str or None
            - user_notes_count: int (comment count)
            - project_id: int (for cross-project issues!)
            - web_url: str
            
            Returns empty list if no linked issues.
        
        Raises:
            requests.HTTPError: On authentication errors or other HTTP errors
        """
        project_id = quote(f"{owner}/{repo}", safe='')
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}/closes_issues"
        
        try:
            response = self._make_gitlab_request(url)
            
            # Handle errors
            if response.status_code in (401, 403):
                logger.error(f"Authentication error: {response.status_code}")
                response.raise_for_status()
            
            response.raise_for_status()
            
            issues = response.json()
            logger.debug(f"Fetched {len(issues)} linked issues for MR !{mr_iid}")
            
            return issues
            
        except requests.RequestException as e:
            logger.error(f"Error fetching linked issues for MR !{mr_iid}: {e}")
            raise
    
    def fetch_issue_notes(
        self,
        project_id: str,
        issue_iid: int
    ) -> list[dict[str, Any]]:
        """Fetch notes (comments) for an issue (Phase 2 - Enrichment).
        
        Handles pagination to fetch all notes (up to a reasonable limit).
        Filters out system-generated notes (system: true).
        
        Note: project_id can be numeric or URL-encoded path. This is important
        for cross-project issues where the issue is in a different project.
        
        Args:
            project_id: Project ID (numeric like "278964" or URL-encoded like "gitlab-org%2Fgitlab")
            issue_iid: Issue internal ID
        
        Returns:
            List of note dictionaries (system notes filtered out). Each note contains:
            - id: int
            - body: str (note text)
            - author: dict (with "username" field)
            - created_at: str
            - updated_at: str
            - system: bool (always False in returned list)
            
            Returns empty list if no notes or on error.
        
        Raises:
            requests.HTTPError: On authentication errors or other HTTP errors
        """
        url = f"{self.base_url}/projects/{project_id}/issues/{issue_iid}/notes"
        all_notes = []
        page = 1
        max_pages = 5  # Limit to 500 notes (most issues have far fewer)
        
        try:
            while page <= max_pages:
                params = {"per_page": 100, "page": page}
                response = self._make_gitlab_request(url, params=params)
                
                # Handle auth errors
                if response.status_code in (401, 403):
                    logger.error(f"Authentication error: {response.status_code}")
                    response.raise_for_status()
                
                response.raise_for_status()
                
                notes = response.json()
                
                if not notes:
                    break
                
                all_notes.extend(notes)
                page += 1
            
            # Filter out system-generated notes
            user_notes = [note for note in all_notes if not note.get("system", False)]
            
            logger.debug(
                f"Fetched {len(user_notes)} user notes for issue #{issue_iid} "
                f"({len(all_notes)} total including system notes)"
            )
            return user_notes
            
        except requests.RequestException as e:
            logger.error(f"Error fetching notes for issue #{issue_iid}: {e}")
            raise
    
    def _truncate_diff(self, diff: str, max_lines: int = 100) -> str:
        """Truncate diff to maximum number of lines.
        
        Args:
            diff: Unified diff string
            max_lines: Maximum lines to include (default: 100)
        
        Returns:
            Truncated diff with marker if truncated, otherwise original diff
        """
        truncated_diff, _ = self._truncate_diff_with_flag(diff, max_lines)
        return truncated_diff
    
    def _truncate_diff_with_flag(
        self, diff: str, max_lines: int = 100
    ) -> tuple[str, bool]:
        """Truncate diff and return truncation status.
        
        Args:
            diff: Unified diff string
            max_lines: Maximum lines to include (default: 100)
        
        Returns:
            Tuple of (truncated_diff, was_truncated)
        """
        lines = diff.split('\n')
        
        if len(lines) <= max_lines:
            return diff, False
        
        truncated = '\n'.join(lines[:max_lines])
        remaining = len(lines) - max_lines
        
        return f"{truncated}\n... [TRUNCATED: {remaining} more lines]", True
    
    def fetch_issue(
        self,
        owner: str,
        repo: str,
        issue_iid: int
    ) -> dict[str, Any]:
        """Fetch a single issue by its internal ID.
        
        Args:
            owner: Repository owner (e.g., "gitlab-org")
            repo: Repository name (e.g., "gitlab")
            issue_iid: Issue internal ID
        
        Returns:
            Issue dictionary with full metadata
        
        Raises:
            requests.HTTPError: On authentication errors, 404 (issue not found), or other HTTP errors
        """
        project_id = quote(f"{owner}/{repo}", safe='')
        url = f"{self.base_url}/projects/{project_id}/issues/{issue_iid}"
        
        try:
            response = self._make_gitlab_request(url)
            
            # Handle errors
            if response.status_code in (401, 403):
                logger.error(f"Authentication error: {response.status_code}")
                response.raise_for_status()
            
            if response.status_code == 404:
                logger.warning(f"Issue #{issue_iid} not found in {owner}/{repo}")
                return None
            
            response.raise_for_status()
            
            issue = response.json()
            logger.debug(f"Fetched issue #{issue_iid}: {issue['title'][:50]}...")
            
            return issue
            
        except requests.RequestException as e:
            logger.error(f"Error fetching issue #{issue_iid}: {e}")
            raise
    
    def enrich_mr(
        self,
        owner: str,
        repo: str,
        mr_iid: int,
        linked_issue_number: int = None
    ) -> dict[str, Any]:
        """Fetch all enrichment data for an MR (Phase 2 - Enrichment).
        
        This orchestrates fetching diffs, linked issue (if hint provided), and issue notes.
        
        Uses the linked_issue_number hint from Phase 1 (parsed from description) to fetch
        the issue directly, rather than relying on GitLab's /closes_issues endpoint which
        is too strict (only returns issues with auto-close keywords).
        
        Args:
            owner: Repository owner (e.g., "gitlab-org")
            repo: Repository name (e.g., "gitlab")
            mr_iid: Merge request internal ID
            linked_issue_number: Issue iid from Phase 1 description parsing (optional)
        
        Returns:
            Dict with structure:
            {
                "files": dict,              # From fetch_mr_diffs()
                "linked_issues": list,      # Array with single issue object (if found)
                "issue_notes": dict         # From fetch_issue_notes() - dict {iid: [notes]}
            }
        
        Raises:
            requests.HTTPError: On authentication errors or other HTTP errors
        """
        logger.info(f"Enriching MR !{mr_iid} in {owner}/{repo}")
        
        # Step 1: Fetch diffs
        files = self.fetch_mr_diffs(owner, repo, mr_iid)
        
        # Step 2: Fetch linked issue (if hint provided from Phase 1)
        linked_issues = []
        issue_notes = {}
        
        if linked_issue_number:
            logger.debug(f"Fetching linked issue #{linked_issue_number} (from Phase 1 hint)")
            
            try:
                issue = self.fetch_issue(owner, repo, linked_issue_number)
                
                if issue:
                    # Store as array for consistency with the schema
                    linked_issues = [issue]
                    
                    # Step 3: Fetch notes for the issue
                    issue_iid = issue['iid']
                    issue_project_id = issue.get('project_id')
                    
                    # Use the issue's project_id (handles cross-project references)
                    if issue_project_id:
                        project_id_str = str(issue_project_id)
                    else:
                        # Fallback to current project
                        project_id_str = quote(f"{owner}/{repo}", safe='')
                    
                    if issue.get('user_notes_count', 0) > 0:
                        notes = self.fetch_issue_notes(project_id_str, issue_iid)
                        issue_notes[issue_iid] = notes
                    else:
                        issue_notes[issue_iid] = []
                else:
                    logger.debug(f"Issue #{linked_issue_number} not found (may be deleted or in different project)")
            
            except Exception as e:
                logger.warning(f"Failed to fetch linked issue #{linked_issue_number}: {e}")
                # Continue without the issue data rather than failing the entire enrichment
        
        result = {
            "files": files,
            "linked_issues": linked_issues,  # Array of issue objects (0 or 1 items)
            "issue_notes": issue_notes  # Dict: {issue_iid: [notes]}
        }
        
        logger.info(
            f"Enriched MR !{mr_iid}: "
            f"{files['summary']['files_included']} files, "
            f"{len(linked_issues)} linked issue(s), "
            f"{sum(len(notes) for notes in issue_notes.values())} total notes"
        )
        
        return result

