"""
API routes for PR Explorer.

Provides endpoints for listing and retrieving PR data from Supabase.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from utils.config_loader import load_config
from utils.logger import setup_logger
from storage.supabase_client import SupabaseClient

logger = setup_logger(__name__)

# Initialize Supabase client for routes
config = load_config()
supabase = SupabaseClient(
    config.credentials.supabase_url,
    config.credentials.supabase_key
)

router = APIRouter(prefix="/api", tags=["prs"])


def _get_file_status_from_gitlab(file: Dict[str, Any]) -> str:
    """Convert GitLab file flags to GitHub-style status."""
    if file.get("new_file"):
        return "added"
    elif file.get("deleted_file"):
        return "removed"
    elif file.get("renamed_file"):
        return "renamed"
    else:
        return "modified"


def _count_additions_from_diff(diff: str) -> int:
    """Count addition lines (starting with +) in a diff."""
    if not diff:
        return 0
    return sum(1 for line in diff.split('\n') if line.startswith('+') and not line.startswith('+++'))


def _count_deletions_from_diff(diff: str) -> int:
    """Count deletion lines (starting with -) in a diff."""
    if not diff:
        return 0
    return sum(1 for line in diff.split('\n') if line.startswith('-') and not line.startswith('---'))


def _count_changes_from_diff(diff: str) -> int:
    """Count total changes (additions + deletions) in a diff."""
    return _count_additions_from_diff(diff) + _count_deletions_from_diff(diff)


class PRListResponse(BaseModel):
    """Response model for PR list endpoint."""
    prs: List[Dict[str, Any]]
    total: int
    page: int
    per_page: int


@router.get("/prs", response_model=PRListResponse)
def list_prs(
    repo: Optional[str] = Query(None, description="Filter by repository (e.g., 'facebook/react')"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(50, ge=1, le=100, description="PRs per page (max 100)")
):
    """
    List PRs with pagination and optional filtering.

    Returns a paginated list of PRs from Supabase. Shows all PRs regardless
    of enrichment status.

    Query Parameters:
    - repo: Optional filter by repository (e.g., "facebook/react")
    - page: Page number (default: 1)
    - per_page: Number of PRs per page (default: 50, max: 100)

    Returns:
    - prs: List of PR objects
    - total: Total count of PRs matching the filter
    - page: Current page number
    - per_page: Number of PRs per page
    """
    try:
        # Calculate offset for pagination
        offset = (page - 1) * per_page

        # Build query for PRs
        query = supabase.client.table("pull_requests").select("*")

        # Apply repository filter if provided
        if repo:
            query = query.eq("repo", repo)

        # Order by merged_at DESC (newest first) and apply pagination
        query = query.order("merged_at", desc=True).range(offset, offset + per_page - 1)

        # Execute query
        result = query.execute()
        prs = result.data

        # Get total count for pagination
        count_query = supabase.client.table("pull_requests").select("*", count="exact", head=True)
        if repo:
            count_query = count_query.eq("repo", repo)
        count_result = count_query.execute()
        total = count_result.count or 0

        logger.info(
            f"Listed {len(prs)} PRs (page {page}, per_page {per_page}, total {total})"
            f"{f' for repo {repo}' if repo else ''}"
        )

        return {
            "prs": prs,
            "total": total,
            "page": page,
            "per_page": per_page
        }

    except Exception as e:
        logger.error(f"Failed to list PRs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list PRs: {str(e)}")


@router.get("/prs/{repo:path}/{pr_number}")
def get_pr(repo: str, pr_number: int):
    """
    Get a single PR by repository and PR number.

    Path Parameters:
    - repo: Repository name (e.g., "facebook/react")
    - pr_number: PR number

    Returns:
    - PR object with all fields (metadata, files, linked issue, comments)

    Raises:
    - 404: If PR is not found
    """
    try:
        # Use existing SupabaseClient method
        pr = supabase.get_pr_by_number(repo, pr_number)

        if not pr:
            logger.warning(f"PR not found: {repo}#{pr_number}")
            raise HTTPException(status_code=404, detail=f"PR not found: {repo}#{pr_number}")

        # Normalize file data: GitLab uses different structure than GitHub
        # Transform GitLab format to GitHub format for frontend compatibility
        if pr.get("files") and "files" in pr["files"]:
            normalized_files = []
            for file in pr["files"]["files"]:
                # Check if this is GitLab format (has 'new_path' but not 'filename')
                if "new_path" in file and "filename" not in file:
                    # GitLab format - normalize to GitHub format
                    normalized_file = {
                        "filename": file.get("new_path", file.get("old_path", "unknown")),
                        "status": _get_file_status_from_gitlab(file),
                        "additions": _count_additions_from_diff(file.get("diff", "")),
                        "deletions": _count_deletions_from_diff(file.get("diff", "")),
                        "changes": _count_changes_from_diff(file.get("diff", "")),
                        "patch": file.get("diff"),  # GitLab calls it 'diff', GitHub calls it 'patch'
                    }
                    normalized_files.append(normalized_file)
                else:
                    # Already in GitHub format, keep as-is
                    normalized_files.append(file)

            pr["files"]["files"] = normalized_files

        logger.info(f"Retrieved PR: {repo}#{pr_number}")
        return pr

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to get PR {repo}#{pr_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get PR: {str(e)}")


@router.get("/repos")
def list_repos():
    """
    Get list of all unique repositories in the database.

    This is used to populate the repository filter dropdown in the UI.

    Returns:
    - repos: List of repository names (e.g., ["facebook/react", "microsoft/vscode"])
    """
    try:
        # Try to use efficient RPC function first (if it exists)
        # This returns only unique repos from the database
        try:
            result = supabase.client.rpc('get_distinct_repos').execute()
            if result.data:
                # RPC returns objects like [{"repo": "..."}, ...], extract the strings
                repos = [row["repo"] if isinstance(row, dict) else row for row in result.data]
                logger.info(f"Found {len(repos)} unique repositories (via RPC)")
                return {"repos": repos}
        except Exception as rpc_error:
            logger.debug(f"RPC function not available, using fallback: {rpc_error}")

        # Fallback: Fetch repos with a high limit and dedupe client-side
        # Since there are typically only a handful of unique repos,
        # fetching 5000 rows will likely cover all PRs
        result = supabase.client.table("pull_requests").select("repo").limit(5000).execute()

        # Get unique repos and sort alphabetically
        repos = sorted(set(row["repo"] for row in result.data))

        logger.info(f"Found {len(repos)} unique repositories (via fallback)")
        return {"repos": repos}

    except Exception as e:
        logger.error(f"Failed to list repos: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list repos: {str(e)}")
