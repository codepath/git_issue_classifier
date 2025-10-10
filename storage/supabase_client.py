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
        # Get platform and generate repo_url
        actual_platform = pr_data.get("platform", platform)
        repo = pr_data["repo"]
        pr_number = pr_data["pr_number"]
        
        if actual_platform == "gitlab":
            repo_url = f"https://gitlab.com/{repo}/-/merge_requests/{pr_number}"
        else:  # github
            repo_url = f"https://github.com/{repo}/pull/{pr_number}"
        
        # Prepare record with enrichment_status='pending'
        record = {
            "repo": repo,
            "pr_number": pr_number,
            "title": pr_data["title"],
            "body": pr_data.get("body"),
            "merged_at": pr_data["merged_at"],
            "created_at": pr_data["created_at"],
            "linked_issue_number": pr_data.get("linked_issue_number"),
            "enrichment_status": "pending",
            "platform": actual_platform,
            "repo_url": repo_url,
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
            actual_platform = pr_data.get("platform", platform)
            repo = pr_data["repo"]
            pr_number = pr_data["pr_number"]
            
            # Generate platform-specific URL
            if actual_platform == "gitlab":
                repo_url = f"https://gitlab.com/{repo}/-/merge_requests/{pr_number}"
            else:  # github
                repo_url = f"https://github.com/{repo}/pull/{pr_number}"
            
            records.append({
                "repo": repo,
                "pr_number": pr_number,
                "title": pr_data["title"],
                "body": pr_data.get("body"),
                "merged_at": pr_data["merged_at"],
                "created_at": pr_data["created_at"],
                "linked_issue_number": pr_data.get("linked_issue_number"),
                "enrichment_status": "pending",
                "platform": actual_platform,
                "repo_url": repo_url,
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
            
            filter_str = f" ({', '.join(filter_desc)})" if filter_desc else ""
            logger.info(
                f"Found {len(result.data)} items needing enrichment{filter_str}"
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
        
        Returns PRs where enrichment_status='success' and classified_at IS NULL.
        
        Args:
            limit: Maximum number of PRs to return (default 100)
            repo: Optional filter by repository (e.g., "facebook/react")
        
        Returns:
            List of PR records with all fields (id, repo, pr_number, title, body,
            files, linked_issue, issue_comments, etc.)
            Returns empty list if no unclassified PRs found
        """
        try:
            # Build query for enriched PRs that don't have a classification
            query = self.client.table(self.table_name).select("*")
            
            # Filter: only successfully enriched PRs
            query = query.eq("enrichment_status", "success")
            
            # Filter: not yet classified (classified_at is NULL)
            query = query.is_("classified_at", "null")
            
            # Optional: filter by repo
            if repo:
                query = query.eq("repo", repo)
            
            # Order by merged_at DESC (newest first)
            query = query.order("merged_at", desc=True)
            
            # Supabase has a max row limit (default 1000), so we need to paginate
            # if the requested limit is higher
            prs = []
            batch_size = 1000  # Supabase default max
            offset = 0
            
            while len(prs) < limit:
                # How many more do we need?
                remaining = limit - len(prs)
                fetch_size = min(remaining, batch_size)
                
                # Fetch this batch
                batch_query = query.limit(fetch_size).offset(offset)
                result = batch_query.execute()
                batch = result.data
                
                if not batch:
                    # No more PRs available
                    break
                
                prs.extend(batch)
                offset += len(batch)
                
                # If we got fewer than requested, there are no more PRs
                if len(batch) < fetch_size:
                    break
            
            logger.info(
                f"Found {len(prs)} unclassified PRs"
                f"{f' in {repo}' if repo else ''}"
            )
            return prs
            
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
        Save classification for a PR by updating the pull_requests table.
        
        Uses UPDATE with WHERE id = pr_id to add classification data to existing PR.
        Idempotent - safe to call multiple times (will overwrite previous classification).
        
        Args:
            pr_id: Database ID of the PR
            pr_data: PR data dict (used for logging only)
            classification: Classification dict with keys:
                - difficulty: str (trivial/easy/medium/hard)
                - task_clarity: str (clear/partial/poor)
                - is_reproducible: str (highly likely/maybe/unclear)
                - onboarding_suitability: str (excellent/poor)
                - categories: List[str]
                - concepts_taught: List[str]
                - prerequisites: List[str]
                - reasoning: str
        
        Returns:
            Dict with the updated PR record
        
        Raises:
            Exception if update fails
        """
        repo = pr_data["repo"]
        pr_number = pr_data["pr_number"]
        
        try:
            # Prepare classification update
            update_record = {
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
            
            # Update the PR record with classification data
            result = self.client.table(self.table_name).update(
                update_record
            ).eq("id", pr_id).execute()
            
            logger.info(
                f"Saved classification for {repo}#{pr_number} "
                f"(difficulty: {classification['difficulty']})"
            )
            return result.data[0] if result.data else update_record
            
        except Exception as e:
            logger.error(
                f"Failed to save classification for {repo}#{pr_number}: {e}"
            )
            raise
    
    def get_classification_stats(self, repo: Optional[str] = None) -> Dict[str, Any]:
        """
        Get classification statistics from pull_requests table.
        
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
            
            # Fetch all classified PRs (where classified_at is not NULL) in one query
            # Much more efficient than separate queries!
            query = self.client.table(self.table_name).select(
                "difficulty,task_clarity,is_reproducible,onboarding_suitability"
            ).not_.is_("classified_at", "null")
            
            if repo:
                query = query.eq("repo", repo)
            
            result = query.execute()
            classifications = result.data
            
            stats['total_classified'] = len(classifications)
            
            # Count by each field in Python (faster than separate queries)
            for c in classifications:
                # Count by difficulty
                difficulty = c.get('difficulty')
                if difficulty in stats['by_difficulty']:
                    stats['by_difficulty'][difficulty] += 1
                
                # Count by task clarity
                clarity = c.get('task_clarity')
                if clarity in stats['by_task_clarity']:
                    stats['by_task_clarity'][clarity] += 1
                
                # Count by reproducibility
                reproducible = c.get('is_reproducible')
                if reproducible in stats['by_reproducible']:
                    stats['by_reproducible'][reproducible] += 1
                
                # Count by onboarding suitability
                onboarding = c.get('onboarding_suitability')
                if onboarding in stats['by_onboarding']:
                    stats['by_onboarding'][onboarding] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get classification stats: {e}")
            return {
                'total_classified': 0,
                'by_difficulty': {'trivial': 0, 'easy': 0, 'medium': 0, 'hard': 0},
                'by_task_clarity': {'clear': 0, 'partial': 0, 'poor': 0},
                'by_reproducible': {'highly likely': 0, 'maybe': 0, 'unclear': 0},
                'by_onboarding': {'excellent': 0, 'poor': 0}
            }