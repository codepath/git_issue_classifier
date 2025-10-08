"""
Supabase storage client for pull request data.

Implements the two-phase workflow:
- Phase 1 (Index): Save basic PR metadata with enrichment_status='pending'
- Phase 2 (Enrichment): Update with files, diffs, and linked issues

All methods are idempotent and can be safely re-run.
"""

from datetime import datetime
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
    
    def insert_pr_index(self, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert or update basic PR data from the index phase (Phase 1).
        
        This is the first phase of the two-phase workflow. PRs are saved with
        enrichment_status='pending' and will be enriched in Phase 2.
        
        Uses UPSERT behavior - if PR already exists (same repo + pr_number),
        it updates the basic fields but preserves enrichment data.
        
        Args:
            pr_data: Dict with keys:
                - repo: str (e.g., "facebook/react")
                - pr_number: int
                - title: str
                - body: str (can be None)
                - merged_at: str (ISO 8601 timestamp)
                - created_at: str (ISO 8601 timestamp)
                - linked_issue_number: int or None (parsed from PR body)
        
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
    
    def insert_pr_index_batch(self, pr_data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Insert or update multiple PRs in a single batch operation.
        
        Much faster than calling insert_pr_index() multiple times.
        
        Args:
            pr_data_list: List of PR data dicts (same format as insert_pr_index)
        
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
        repo: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query PRs that need enrichment (status = 'pending' or 'failed').
        
        This supports resumable workflows - can query for work that needs
        to be done and retry only failed PRs.
        
        Args:
            limit: Maximum number of PRs to return (default 100)
            repo: Optional filter by repository (e.g., "facebook/react")
        
        Returns:
            List of PR records with basic fields (id, repo, pr_number, body, etc.)
            Returns empty list if no PRs need enrichment
        """
        try:
            # Build query
            query = self.client.table(self.table_name).select("*")
            
            # Filter by enrichment status
            query = query.in_("enrichment_status", ["pending", "failed"])
            
            # Optional: filter by repo
            if repo:
                query = query.eq("repo", repo)
            
            # Order by merged_at DESC (newest first) and limit
            query = query.order("merged_at", desc=True).limit(limit)
            
            # Execute query
            result = query.execute()
            
            logger.info(
                f"Found {len(result.data)} PRs needing enrichment"
                f"{f' in {repo}' if repo else ''}"
            )
            return result.data
            
        except Exception as e:
            logger.error(f"Failed to query PRs needing enrichment: {e}")
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
            "enrichment_attempted_at": datetime.utcnow().isoformat(),
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
            # Base query
            query = self.client.table(self.table_name).select("enrichment_status")
            
            if repo:
                query = query.eq("repo", repo)
            
            result = query.execute()
            
            # Count by status
            stats = {
                'total': len(result.data),
                'pending': 0,
                'success': 0,
                'failed': 0
            }
            
            for row in result.data:
                status = row.get('enrichment_status', 'pending')
                if status in stats:
                    stats[status] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get enrichment stats: {e}")
            return {'total': 0, 'pending': 0, 'success': 0, 'failed': 0}
