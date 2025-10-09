"""
Supabase storage client for pull request data.

Implements the two-phase workflow:
- Phase 1 (Index): Save basic PR metadata with enrichment_status='pending'
- Phase 2 (Enrichment): Update with files, diffs, and linked issues

All methods are idempotent and can be safely re-run.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from supabase import Client, create_client

from utils.logger import setup_logger

logger = setup_logger(__name__)


class SupabaseClient:
    """Client for interacting with Supabase storage."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize Supabase client.
        
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase API key (anon/public key)
        """
        self.client: Client = create_client(supabase_url, supabase_key)
        self.table_name = "pull_requests"
        logger.info(f"Initialized SupabaseClient for {supabase_url}")
    
    def insert_pr_index(self, pr_data: Dict[str, Any], platform: str = "github") -> Dict[str, Any]:
        """
        Insert or update basic PR/MR data from the index phase (Phase 1).
        
        This is the first phase of the two-phase workflow. Items are saved with
        enrichment_status='pending' and will be enriched in Phase 2.
        
        Uses UPSERT behavior - if item already exists (same repo + pr_number),
        it updates the basic fields but preserves enrichment data.
        
        Args:
            pr_data: Dict with keys:
                - repo: str (e.g., "facebook/react" or "gitlab-org/gitlab")
                - pr_number: int (GitHub PR number or GitLab MR iid)
                - title: str
                - body: str (can be None)
                - merged_at: str (ISO 8601 timestamp)
                - created_at: str (ISO 8601 timestamp)
                - linked_issue_number: int or None (parsed from description - Phase 1 hint)
                - platform: str (optional, defaults to parameter)
            platform: Platform name ("github" or "gitlab"), default: "github"
        
        Returns:
            Dict with the inserted/updated record
            
        Raises:
            Exception if insert fails
        """
        # Prepare record with enrichment_status='pending'
        record = {
            "repo": pr_data["repo"],
            "pr_number": pr_data["pr_number"],
            "title": pr_data["title"],
            "body": pr_data.get("body"),
            "merged_at": pr_data["merged_at"],
            "created_at": pr_data["created_at"],
            "linked_issue_number": pr_data.get("linked_issue_number"),
            "enrichment_status": "pending",
            "platform": pr_data.get("platform", platform),  # NEW: Store platform
        }
        
        try:
            # Use upsert to handle duplicates
            # onConflict specifies which fields constitute a unique constraint
            result = self.client.table(self.table_name).upsert(
                record,
                on_conflict="repo,pr_number"
            ).execute()
            
            logger.debug(
                f"Inserted/updated PR index: {record['repo']}#{record['pr_number']}"
            )
            return result.data[0] if result.data else record
            
        except Exception as e:
            logger.error(
                f"Failed to insert PR index {record['repo']}#{record['pr_number']}: {e}"
            )
            raise
    
    def insert_pr_index_batch(self, pr_data_list: List[Dict[str, Any]], platform: str = "github") -> List[Dict[str, Any]]:
        """
        Insert or update multiple PRs/MRs in a single batch operation.
        
        Much faster than calling insert_pr_index() multiple times.
        
        Args:
            pr_data_list: List of PR/MR data dicts (same format as insert_pr_index)
            platform: Platform name ("github" or "gitlab"), default: "github"
        
        Returns:
            List of inserted/updated records
            
        Raises:
            Exception if insert fails
        """
        if not pr_data_list:
            return []
        
        # Prepare all records
        records = []
        for pr_data in pr_data_list:
            records.append({
                "repo": pr_data["repo"],
                "pr_number": pr_data["pr_number"],
                "title": pr_data["title"],
                "body": pr_data.get("body"),
                "merged_at": pr_data["merged_at"],
                "created_at": pr_data["created_at"],
                "linked_issue_number": pr_data.get("linked_issue_number"),
                "enrichment_status": "pending",
                "platform": pr_data.get("platform", platform),  # NEW: Store platform
            })
        
        try:
            # Bulk upsert - much faster than individual inserts
            result = self.client.table(self.table_name).upsert(
                records,
                on_conflict="repo,pr_number"
            ).execute()
            
            logger.info(
                f"Batch inserted/updated {len(records)} PRs"
            )
            return result.data if result.data else records
            
        except Exception as e:
            logger.error(f"Failed to batch insert PRs: {e}")
            raise
    
    def get_prs_needing_enrichment(
        self,
        limit: int = 100,
        repo: Optional[str] = None,
        platform: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query PRs/MRs that need enrichment (status = 'pending' or 'failed').
        
        This supports resumable workflows - can query for work that needs
        to be done and retry only failed items.
        
        Args:
            limit: Maximum number of items to return (default 100)
            repo: Optional filter by repository (e.g., "facebook/react")
            platform: Optional filter by platform ("github" or "gitlab")
        
        Returns:
            List of PR/MR records with basic fields (id, repo, pr_number, body, platform, etc.)
            Returns empty list if no items need enrichment
        """
        try:
            # Build query
            query = self.client.table(self.table_name).select("*")
            
            # Filter by enrichment status
            query = query.in_("enrichment_status", ["pending", "failed"])
            
            # Optional: filter by repo
            if repo:
                query = query.eq("repo", repo)
            
            # Optional: filter by platform
            if platform:
                query = query.eq("platform", platform)
            
            # Order by merged_at DESC (newest first) and limit
            query = query.order("merged_at", desc=True).limit(limit)
            
            # Execute query
            result = query.execute()
            
            filter_desc = []
            if repo:
                filter_desc.append(f"repo={repo}")
            if platform:
                filter_desc.append(f"platform={platform}")
            
            logger.info(
                f"Found {len(result.data)} items needing enrichment"
                f"{f' ({', '.join(filter_desc)})' if filter_desc else ''}"
            )
            return result.data
            
        except Exception as e:
            logger.error(f"Failed to query items needing enrichment: {e}")
            raise
    
    def update_pr_enrichment(
        self,
        pr_id: int,
        enrichment_data: Optional[Dict[str, Any]] = None,
        status: str = "success",
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update PR with enrichment data from Phase 2.
        
        This is the second phase of the two-phase workflow. Updates a PR
        with enriched data (files, linked issues) and tracks success/failure.
        
        Args:
            pr_id: Database ID of the PR record
            enrichment_data: Dict with keys:
                - files: List[Dict] (changed files with diffs)
                - linked_issue: Dict or None (issue metadata)
                - issue_comments: List[Dict] (issue comments)
            status: 'success' | 'failed' | 'partial'
            error: Error message if status='failed' (truncated to 500 chars)
        
        Returns:
            Dict with the updated record
            
        Raises:
            Exception if update fails
        """
        # Prepare update record
        update_record = {
            "enrichment_status": status,
            "enrichment_attempted_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Add enrichment data if provided (success case)
        if enrichment_data:
            update_record["files"] = enrichment_data.get("files")
            update_record["linked_issue"] = enrichment_data.get("linked_issue")
            update_record["issue_comments"] = enrichment_data.get("issue_comments")
        
        # Add error message if provided (failure case)
        if error:
            # Truncate error to prevent huge strings in DB
            update_record["enrichment_error"] = error[:500]
        
        try:
            # Update by ID
            result = self.client.table(self.table_name).update(
                update_record
            ).eq("id", pr_id).execute()
            
            logger.debug(
                f"Updated PR enrichment (id={pr_id}, status={status})"
            )
            return result.data[0] if result.data else update_record
            
        except Exception as e:
            logger.error(f"Failed to update PR enrichment (id={pr_id}): {e}")
            raise
    
    def get_pr_by_number(self, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        """
        Get a single PR by repo and PR number.
        
        Useful for checking if a PR exists or viewing its current state.
        
        Args:
            repo: Repository name (e.g., "facebook/react")
            pr_number: PR number
        
        Returns:
            PR record dict or None if not found
        """
        try:
            result = self.client.table(self.table_name).select("*").eq(
                "repo", repo
            ).eq("pr_number", pr_number).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to get PR {repo}#{pr_number}: {e}")
            return None
    
    def get_enrichment_stats(self, repo: Optional[str] = None) -> Dict[str, int]:
        """
        Get enrichment status statistics.
        
        Useful for monitoring progress and identifying issues.
        
        Args:
            repo: Optional filter by repository
        
        Returns:
            Dict with counts: {
                'total': int,
                'pending': int,
                'success': int,
                'failed': int
            }
        """
        try:
            # Use count queries instead of fetching all rows
            # This avoids the default 1000 row limit and is more efficient
            
            stats = {
                'total': 0,
                'pending': 0,
                'success': 0,
                'failed': 0
            }
            
            # Count total PRs
            query = self.client.table(self.table_name).select("*", count="exact", head=True)
            if repo:
                query = query.eq("repo", repo)
            result = query.execute()
            stats['total'] = result.count or 0
            
            # Count pending PRs
            query = self.client.table(self.table_name).select("*", count="exact", head=True)
            if repo:
                query = query.eq("repo", repo)
            query = query.eq("enrichment_status", "pending")
            result = query.execute()
            stats['pending'] = result.count or 0
            
            # Count success PRs
            query = self.client.table(self.table_name).select("*", count="exact", head=True)
            if repo:
                query = query.eq("repo", repo)
            query = query.eq("enrichment_status", "success")
            result = query.execute()
            stats['success'] = result.count or 0
            
            # Count failed PRs
            query = self.client.table(self.table_name).select("*", count="exact", head=True)
            if repo:
                query = query.eq("repo", repo)
            query = query.eq("enrichment_status", "failed")
            result = query.execute()
            stats['failed'] = result.count or 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get enrichment stats: {e}")
            return {'total': 0, 'pending': 0, 'success': 0, 'failed': 0}
    
    def get_unclassified_prs(
        self,
        limit: int = 100,
        repo: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query PRs that have been enriched but not yet classified.
        
        Returns PRs where enrichment_status='success' and no classification exists.
        
        Args:
            limit: Maximum number of PRs to return (default 100)
            repo: Optional filter by repository (e.g., "facebook/react")
        
        Returns:
            List of PR records with all fields (id, repo, pr_number, title, body,
            files, linked_issue, issue_comments, etc.)
            Returns empty list if no unclassified PRs found
        """
        try:
            # Build query - get enriched PRs
            query = self.client.table(self.table_name).select("*")
            
            # Filter: only successfully enriched PRs
            query = query.eq("enrichment_status", "success")
            
            # Optional: filter by repo
            if repo:
                query = query.eq("repo", repo)
            
            # Order by merged_at DESC (newest first) and limit
            query = query.order("merged_at", desc=True).limit(limit)
            
            # Execute query
            result = query.execute()
            prs = result.data
            
            # Filter out PRs that already have classifications
            # We do this client-side because Supabase doesn't support LEFT JOIN filtering easily
            unclassified_prs = []
            for pr in prs:
                # Check if classification exists for this PR
                classification_query = self.client.table("classifications").select("id").eq("pr_id", pr["id"]).execute()
                if not classification_query.data:
                    unclassified_prs.append(pr)
            
            logger.info(
                f"Found {len(unclassified_prs)} unclassified PRs"
                f"{f' in {repo}' if repo else ''}"
            )
            return unclassified_prs
            
        except Exception as e:
            logger.error(f"Failed to query unclassified PRs: {e}")
            raise
    
    def save_classification(
        self,
        pr_id: int,
        pr_data: Dict[str, Any],
        classification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Save classification for a PR to the classifications table.
        
        Uses UPSERT for idempotency - safe to call multiple times.
        The classifications table is denormalized for easy export to Google Sheets.
        
        Args:
            pr_id: Database ID of the PR (foreign key)
            pr_data: PR data dict with keys: repo, pr_number, title, body, merged_at
            classification: Classification dict with keys:
                - difficulty: str (trivial/easy/medium/hard)
                - categories: List[str]
                - concepts_taught: List[str]
                - prerequisites: List[str]
                - reasoning: str
        
        Returns:
            Dict with the inserted/updated classification record
        
        Raises:
            Exception if insert fails
        """
        repo = pr_data["repo"]
        pr_number = pr_data["pr_number"]
        platform = pr_data.get("platform", "github")  # Default to github for backwards compatibility
        
        try:
            # Generate platform-specific URL
            if platform == "gitlab":
                repo_url = f"https://gitlab.com/{repo}/-/merge_requests/{pr_number}"
            else:  # github
                repo_url = f"https://github.com/{repo}/pull/{pr_number}"
            
            # Prepare classification record
            # Denormalized with PR info for standalone export
            record = {
                "pr_id": pr_id,
                "repo_url": repo_url,
                "repo": repo,
                "pr_number": pr_number,
                "title": pr_data["title"],
                "body": pr_data.get("body"),
                "merged_at": pr_data["merged_at"],
                "difficulty": classification["difficulty"],
                "task_clarity": classification["task_clarity"],
                "is_reproducible": classification["is_reproducible"],
                "onboarding_suitability": classification["onboarding_suitability"],
                "categories": classification["categories"],
                "concepts_taught": classification["concepts_taught"],
                "prerequisites": classification["prerequisites"],
                "reasoning": classification["reasoning"],
                "classified_at": datetime.now(timezone.utc).isoformat(),
            }
            
            # Upsert to handle re-classification (idempotent)
            result = self.client.table("classifications").upsert(
                record,
                on_conflict="pr_id"
            ).execute()
            
            logger.info(
                f"Saved classification for {repo}#{pr_number} "
                f"(difficulty: {classification['difficulty']})"
            )
            return result.data[0] if result.data else record
            
        except Exception as e:
            logger.error(
                f"Failed to save classification for {repo}#{pr_number}: {e}"
            )
            raise
    
    def get_classification_stats(self, repo: Optional[str] = None) -> Dict[str, Any]:
        """
        Get classification statistics.
        
        Useful for monitoring classification progress.
        
        Args:
            repo: Optional filter by repository
        
        Returns:
            Dict with counts by difficulty, onboarding suitability, and total classified
        """
        try:
            stats = {
                'total_classified': 0,
                'by_difficulty': {
                    'trivial': 0,
                    'easy': 0,
                    'medium': 0,
                    'hard': 0
                },
                'by_task_clarity': {
                    'clear': 0,
                    'partial': 0,
                    'poor': 0
                },
                'by_reproducible': {
                    'highly likely': 0,
                    'maybe': 0,
                    'unclear': 0
                },
                'by_onboarding': {
                    'excellent': 0,
                    'poor': 0
                }
            }
            
            # Build base query
            query = self.client.table("classifications").select("*", count="exact", head=True)
            if repo:
                query = query.eq("repo", repo)
            
            # Total classified
            result = query.execute()
            stats['total_classified'] = result.count or 0
            
            # Count by difficulty
            for difficulty in ['trivial', 'easy', 'medium', 'hard']:
                query = self.client.table("classifications").select("*", count="exact", head=True)
                if repo:
                    query = query.eq("repo", repo)
                query = query.eq("difficulty", difficulty)
                result = query.execute()
                stats['by_difficulty'][difficulty] = result.count or 0
            
            # Count by task clarity
            for clarity in ['clear', 'partial', 'poor']:
                query = self.client.table("classifications").select("*", count="exact", head=True)
                if repo:
                    query = query.eq("repo", repo)
                query = query.eq("task_clarity", clarity)
                result = query.execute()
                stats['by_task_clarity'][clarity] = result.count or 0
            
            # Count by reproducibility
            for reproducible in ['highly likely', 'maybe', 'unclear']:
                query = self.client.table("classifications").select("*", count="exact", head=True)
                if repo:
                    query = query.eq("repo", repo)
                query = query.eq("is_reproducible", reproducible)
                result = query.execute()
                stats['by_reproducible'][reproducible] = result.count or 0
            
            # Count by onboarding suitability
            for suitability in ['excellent', 'poor']:
                query = self.client.table("classifications").select("*", count="exact", head=True)
                if repo:
                    query = query.eq("repo", repo)
                query = query.eq("onboarding_suitability", suitability)
                result = query.execute()
                stats['by_onboarding'][suitability] = result.count or 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get classification stats: {e}")
            return {'total_classified': 0, 'trivial': 0, 'easy': 0, 'medium': 0, 'hard': 0}