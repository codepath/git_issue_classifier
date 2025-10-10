"""
API routes for PR Explorer.

Provides endpoints for listing and retrieving PR data from Supabase.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from utils.config_loader import load_config
from utils.logger import setup_logger
from storage.supabase_client import SupabaseClient
from classifier.context_builder import build_pr_context
from classifier.prompt_template import CLASSIFICATION_PROMPT

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
    per_page: int = Query(50, ge=1, le=100, description="PRs per page (max 100)"),
    cutoff_date: Optional[str] = Query(None, description="Filter PRs merged after this date (YYYY-MM-DD). Automatically adds 2-day buffer."),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Sort order by merged_at: 'asc' (oldest first, chronological) or 'desc' (newest first)"),
    is_favorite: Optional[bool] = Query(None, description="Filter by favorite status (true = only favorites, false = only non-favorites)"),
    onboarding_suitability: Optional[str] = Query(None, pattern="^(excellent|poor)$", description="Filter by onboarding suitability"),
    difficulty: Optional[str] = Query(None, pattern="^(trivial|easy|medium|hard)$", description="Filter by difficulty level"),
    task_clarity: Optional[str] = Query(None, pattern="^(clear|partial|poor)$", description="Filter by task clarity"),
    is_reproducible: Optional[str] = Query(None, pattern="^(highly likely|maybe|unclear)$", description="Filter by reproducibility")
):
    """
    List PRs with pagination and optional filtering.

    Returns a paginated list of PRs from Supabase. Can filter by PR metadata
    (repo, date) and classification fields (suitability, difficulty, etc.).

    Query Parameters:
    - repo: Optional filter by repository (e.g., "facebook/react")
    - page: Page number (default: 1)
    - per_page: Number of PRs per page (default: 50, max: 100)
    - cutoff_date: Filter PRs merged after this date (YYYY-MM-DD format).
                   NOTE: Automatically adds 2-day buffer to prevent fork/PR overlap issues.
                   Example: cutoff_date=2024-06-15 filters PRs merged after 2024-06-17.
    - sort_order: Sort order by merged_at - 'asc' (chronological, oldest first) or 'desc' (newest first, default)
    - is_favorite: Filter by favorite status (true = only favorites)
    - onboarding_suitability: Filter by classification (excellent/poor)
    - difficulty: Filter by difficulty (trivial/easy/medium/hard)
    - task_clarity: Filter by clarity (clear/partial/poor)
    - is_reproducible: Filter by reproducibility (highly likely/maybe/unclear)

    Returns:
    - prs: List of PR objects with classification data included (if available)
    - total: Total count of PRs matching the filter
    - page: Current page number
    - per_page: Number of PRs per page
    """
    try:
        # Parse and validate cutoff_date if provided
        adjusted_cutoff_date = None
        if cutoff_date:
            try:
                # Parse date string to datetime object
                parsed_date = datetime.strptime(cutoff_date, "%Y-%m-%d")
                # Add 2-day buffer to prevent fork/PR overlap
                adjusted_date = parsed_date + timedelta(days=2)
                # Format back to ISO 8601 string for Supabase query
                adjusted_cutoff_date = adjusted_date.strftime("%Y-%m-%d")
                logger.debug(f"Cutoff date: {cutoff_date} → adjusted to {adjusted_cutoff_date} (2-day buffer)")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid date format: '{cutoff_date}'. Expected YYYY-MM-DD (e.g., '2024-06-15')"
                )

        # Calculate offset for pagination
        offset = (page - 1) * per_page

        # Build query for PRs
        query = supabase.client.table("pull_requests").select("*")

        # Apply repository filter if provided
        if repo:
            query = query.eq("repo", repo)

        # Apply favorite filter if provided
        if is_favorite is not None:
            query = query.eq("is_favorite", is_favorite)
        
        # Apply classification filters (now directly on pull_requests table)
        if onboarding_suitability:
            query = query.eq("onboarding_suitability", onboarding_suitability)
        if difficulty:
            query = query.eq("difficulty", difficulty)
        if task_clarity:
            query = query.eq("task_clarity", task_clarity)
        if is_reproducible:
            query = query.eq("is_reproducible", is_reproducible)

        # Apply cutoff date filter if provided (with 2-day buffer already added)
        if adjusted_cutoff_date:
            query = query.gte("merged_at", adjusted_cutoff_date)

        # Apply sort order (asc = chronological/oldest first, desc = newest first)
        query = query.order("merged_at", desc=(sort_order == "desc"))
        
        # Apply pagination
        query = query.range(offset, offset + per_page - 1)

        # Execute query
        result = query.execute()
        prs = result.data

        # Get total count for pagination
        count_query = supabase.client.table("pull_requests").select("*", count="exact", head=True)
        
        # Apply same filters to count query
        if repo:
            count_query = count_query.eq("repo", repo)
        if is_favorite is not None:
            count_query = count_query.eq("is_favorite", is_favorite)
        if onboarding_suitability:
            count_query = count_query.eq("onboarding_suitability", onboarding_suitability)
        if difficulty:
            count_query = count_query.eq("difficulty", difficulty)
        if task_clarity:
            count_query = count_query.eq("task_clarity", task_clarity)
        if is_reproducible:
            count_query = count_query.eq("is_reproducible", is_reproducible)
        if adjusted_cutoff_date:
            count_query = count_query.gte("merged_at", adjusted_cutoff_date)
        
        count_result = count_query.execute()
        total = count_result.count or 0

        # Build log message with filters
        filters_log = []
        if repo:
            filters_log.append(f"repo={repo}")
        if is_favorite is not None:
            filters_log.append(f"favorite={is_favorite}")
        if cutoff_date:
            filters_log.append(f"cutoff={cutoff_date} (adjusted={adjusted_cutoff_date})")
        if sort_order != "desc":
            filters_log.append(f"sort={sort_order}")
        if onboarding_suitability:
            filters_log.append(f"suitability={onboarding_suitability}")
        if difficulty:
            filters_log.append(f"difficulty={difficulty}")
        if task_clarity:
            filters_log.append(f"clarity={task_clarity}")
        if is_reproducible:
            filters_log.append(f"reproducible={is_reproducible}")
        filters_str = f" with filters: {', '.join(filters_log)}" if filters_log else ""

        logger.info(
            f"Listed {len(prs)} PRs (page {page}, per_page {per_page}, total {total}){filters_str}"
        )

        return {
            "prs": prs,
            "total": total,
            "page": page,
            "per_page": per_page
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to list PRs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list PRs: {str(e)}")


# NOTE: More specific routes (with /llm_payload, /favorite) must come BEFORE
# the general /prs/{repo:path}/{pr_number} route to avoid path conflicts

@router.get("/prs/{repo:path}/{pr_number}/llm_payload")
def get_llm_payload(repo: str, pr_number: int):
    """
    Reconstruct the exact LLM payload that was used to classify this PR.

    This endpoint helps with debugging classifications by showing exactly
    what context and prompt the LLM received.

    Path Parameters:
    - repo: Repository name (e.g., "facebook/react")
    - pr_number: PR number

    Returns:
    - pr_context: The formatted PR context (metadata, files, issue, comments)
    - full_prompt: The complete prompt sent to the LLM (context + template)
    - prompt_template: The classification prompt template used

    Raises:
    - 404: If PR is not found

    Use Case:
    Copy the full_prompt and paste it into Claude/ChatGPT to understand
    why the LLM made a particular classification decision.
    """
    try:
        # Get the PR
        pr = supabase.get_pr_by_number(repo, pr_number)

        if not pr:
            logger.warning(f"PR not found for LLM payload: {repo}#{pr_number}")
            raise HTTPException(status_code=404, detail=f"PR not found: {repo}#{pr_number}")

        # Build the PR context using the same function the classifier uses
        pr_context = build_pr_context(pr)

        # Build the full prompt by inserting context into template
        full_prompt = CLASSIFICATION_PROMPT.format(pr_context=pr_context)

        logger.info(f"Generated LLM payload for {repo}#{pr_number}")

        return {
            "pr_context": pr_context,
            "full_prompt": full_prompt,
            "prompt_template": CLASSIFICATION_PROMPT
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to generate LLM payload for {repo}#{pr_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate LLM payload: {str(e)}")


@router.post("/prs/{repo:path}/{pr_number}/favorite")
def toggle_favorite(repo: str, pr_number: int):
    """
    Toggle the favorite status of a PR.

    This endpoint toggles the `is_favorite` field for a PR between TRUE and FALSE.
    It's idempotent - you can call it multiple times.

    Path Parameters:
    - repo: Repository name (e.g., "facebook/react")
    - pr_number: PR number

    Returns:
    - Updated PR object with new is_favorite value

    Raises:
    - 404: If PR is not found
    """
    try:
        # Get the PR
        pr = supabase.get_pr_by_number(repo, pr_number)

        if not pr:
            logger.warning(f"PR not found for favorite toggle: {repo}#{pr_number}")
            raise HTTPException(status_code=404, detail=f"PR not found: {repo}#{pr_number}")

        # Toggle the favorite status
        current_favorite = pr.get("is_favorite", False)
        new_favorite = not current_favorite

        # Update in database
        result = supabase.client.table("pull_requests").update(
            {"is_favorite": new_favorite}
        ).eq("id", pr["id"]).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to update favorite status")

        updated_pr = result.data[0]
        logger.info(f"Toggled favorite for {repo}#{pr_number}: {current_favorite} → {new_favorite}")

        return updated_pr

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to toggle favorite for {repo}#{pr_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle favorite: {str(e)}")


@router.get("/prs/{repo:path}/{pr_number}")
def get_pr(repo: str, pr_number: int):
    """
    Get a single PR by repository and PR number.

    Path Parameters:
    - repo: Repository name (e.g., "facebook/react")
    - pr_number: PR number

    Returns:
    - PR object with all fields (metadata, files, linked issue, comments, classification)

    Raises:
    - 404: If PR is not found
    """
    try:
        # Use existing SupabaseClient method
        pr = supabase.get_pr_by_number(repo, pr_number)

        if not pr:
            logger.warning(f"PR not found: {repo}#{pr_number}")
            raise HTTPException(status_code=404, detail=f"PR not found: {repo}#{pr_number}")

        # Generate LLM payload (full prompt) for debugging classifications
        try:
            pr_context = build_pr_context(pr)
            full_prompt = CLASSIFICATION_PROMPT.format(pr_context=pr_context)
            pr["llm_payload"] = full_prompt
        except Exception as payload_error:
            logger.warning(f"Failed to generate LLM payload for PR {repo}#{pr_number}: {payload_error}")
            pr["llm_payload"] = None

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

        # Check if PR is classified (has classified_at timestamp)
        is_classified = pr.get("classified_at") is not None
        logger.info(f"Retrieved PR: {repo}#{pr_number} (classified: {is_classified})")
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
