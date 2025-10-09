#!/usr/bin/env python3
"""
Git Issue Classifier - Main CLI entrypoint

This tool fetches historical GitHub PRs and GitLab MRs, enriches them with 
files/issues/comments, and prepares them for LLM classification to help 
developers learn codebases.

Usage:
    python main.py fetch facebook/react                              # GitHub (short format)
    python main.py fetch https://github.com/facebook/react           # GitHub (URL)
    python main.py fetch https://gitlab.com/gitlab-org/gitlab        # GitLab (URL required)
    python main.py fetch https://gitlab.com/gitlab-org/gitlab --limit 500
"""

import argparse
import sys
from typing import Tuple
from utils.config_loader import load_config
from utils.logger import setup_logger
from storage.supabase_client import SupabaseClient

logger = setup_logger(__name__)


def parse_repository_url(repo_url_or_path: str) -> Tuple[str, str, str]:
    """
    Parse repository URL or owner/repo format to detect platform.
    
    Args:
        repo_url_or_path: Either:
            - "owner/repo" (assumes GitHub for backward compatibility)
            - "https://github.com/owner/repo"
            - "https://gitlab.com/owner/repo"
    
    Returns:
        Tuple of (platform, owner, repo)
        - platform: "github" or "gitlab"
        - owner: Owner/organization name
        - repo: Repository name
    
    Examples:
        "facebook/react" -> ("github", "facebook", "react")
        "https://github.com/facebook/react" -> ("github", "facebook", "react")
        "https://gitlab.com/gitlab-org/gitlab" -> ("gitlab", "gitlab-org", "gitlab")
    
    Note:
        GitLab repos MUST use full URL format to be detected.
        Short format "owner/repo" always assumes GitHub for backward compatibility.
    """
    # If it's a URL, extract platform and owner/repo
    if repo_url_or_path.startswith("http"):
        if "gitlab.com" in repo_url_or_path:
            platform = "gitlab"
        elif "github.com" in repo_url_or_path:
            platform = "github"
        else:
            raise ValueError(f"Unsupported platform in URL: {repo_url_or_path}")
        
        # Extract owner/repo from URL
        # https://github.com/owner/repo -> owner/repo
        # https://gitlab.com/owner/repo -> owner/repo
        parts = repo_url_or_path.rstrip("/").split("/")
        if len(parts) < 5:
            raise ValueError(f"Invalid repository URL: {repo_url_or_path}")
        owner = parts[-2]
        repo = parts[-1]
    else:
        # Short format "owner/repo" defaults to GitHub (backward compatibility)
        platform = "github"
        if "/" not in repo_url_or_path:
            raise ValueError("Invalid repository format. Use 'owner/repo' or full URL")
        owner, repo = repo_url_or_path.split("/", 1)
    
    return platform, owner, repo


def initialize_fetcher(platform: str, config):
    """
    Initialize the correct fetcher based on platform.
    
    Args:
        platform: "github" or "gitlab"
        config: Config object with credentials
    
    Returns:
        Fetcher instance (GitHubFetcher or GitLabFetcher)
    
    Raises:
        ValueError: If platform is unsupported or token is missing
    """
    if platform == "github":
        if not config.credentials.github_token:
            raise ValueError(
                "GitHub token not set in .env file. "
                "Add GITHUB_TOKEN to access GitHub repositories."
            )
        from fetchers.github import GitHubFetcher
        return GitHubFetcher(config.credentials.github_token)
    
    elif platform == "gitlab":
        if not config.credentials.gitlab_token:
            raise ValueError(
                "GitLab token not set in .env file. "
                "Add GITLAB_TOKEN to access GitLab repositories. "
                "Get one at: https://gitlab.com/-/profile/personal_access_tokens"
            )
        from fetchers.gitlab import GitLabFetcher
        return GitLabFetcher(config.credentials.gitlab_token)
    
    else:
        raise ValueError(f"Unsupported platform: {platform}")


def classify_prs(
    repo_full_name: str = None,
    limit: int = 100,
    classifier = None,
    supabase: SupabaseClient = None
):
    """
    Classify enriched PRs using LLM.
    
    This queries the database for unclassified PRs, classifies them using
    the LLM, and saves the results back to the classifications table.
    
    The process is idempotent - already-classified PRs are skipped automatically.
    
    Args:
        repo_full_name: Optional repository filter (e.g., "facebook/react").
                       If None, classifies PRs from all repositories.
        limit: Maximum number of PRs to classify (default: 100)
        classifier: Classifier instance (optional, will create if not provided)
        supabase: SupabaseClient instance (optional, will create if not provided)
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Initialize clients if not provided
    if classifier is None or supabase is None:
        config = load_config()
        if supabase is None:
            supabase = SupabaseClient(
                config.credentials.supabase_url,
                config.credentials.supabase_key
            )
        if classifier is None:
            from classifier.classifier import Classifier
            
            if config.credentials.llm_provider == "anthropic":
                api_key = config.credentials.anthropic_api_key
            else:
                api_key = config.credentials.openai_api_key
            
            classifier = Classifier(
                provider=config.credentials.llm_provider,
                model=config.credentials.llm_model,
                api_key=api_key
            )
    
    logger.info("=" * 80)
    if repo_full_name:
        logger.info(f"CLASSIFYING PRs: {repo_full_name}")
    else:
        logger.info(f"CLASSIFYING PRs: ALL REPOSITORIES")
    logger.info("=" * 80)
    
    # Query unclassified PRs
    logger.info(f"Querying unclassified PRs (limit: {limit})...")
    try:
        prs_to_classify = supabase.get_unclassified_prs(
            limit=limit,
            repo=repo_full_name
        )
    except Exception as e:
        logger.error(f"Failed to query unclassified PRs: {e}")
        return False
    
    if not prs_to_classify:
        logger.info("No unclassified PRs found - all done!")
        
        # Show stats
        try:
            stats = supabase.get_classification_stats(repo=repo_full_name)
            logger.info(f"\nClassification stats:")
            logger.info(f"  Total classified: {stats['total_classified']}")
            logger.info(f"  Trivial: {stats['trivial']}")
            logger.info(f"  Easy: {stats['easy']}")
            logger.info(f"  Medium: {stats['medium']}")
            logger.info(f"  Hard: {stats['hard']}")
        except Exception as e:
            logger.warning(f"Could not fetch classification stats: {e}")
        
        return True
    
    logger.info(f"Found {len(prs_to_classify)} PRs to classify")
    logger.info("-" * 80)
    
    # Classify each PR
    classified = 0
    failed = 0
    
    for i, pr_record in enumerate(prs_to_classify, 1):
        pr_id = pr_record["id"]
        pr_repo = pr_record["repo"]
        pr_number = pr_record["pr_number"]
        pr_title = pr_record["title"]
        
        try:
            logger.info(f"[{i}/{len(prs_to_classify)}] {pr_repo} PR #{pr_number}: {pr_title}")
            
            # Classify the PR
            classification = classifier.classify_pr(pr_record)
            
            # Save classification to database
            supabase.save_classification(
                pr_id=pr_id,
                pr_data=pr_record,
                classification=classification
            )
            
            classified += 1
            logger.info(
                f"  ✓ Classified as {classification['difficulty']} "
                f"({', '.join(classification['categories'][:3])})"
            )
            
        except Exception as e:
            logger.error(f"  ✗ Failed to classify: {e}")
            failed += 1
        
        # Show progress every 10 PRs
        if i % 10 == 0 and i < len(prs_to_classify):
            logger.info(f"  Progress: {i}/{len(prs_to_classify)} PRs processed...")
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    
    if repo_full_name:
        logger.info(f"Repository: {repo_full_name}")
    else:
        logger.info(f"Repository: ALL REPOSITORIES")
    
    logger.info(f"PRs classified: {classified}")
    logger.info(f"PRs failed: {failed}")
    
    # Show classification stats
    try:
        stats = supabase.get_classification_stats(repo=repo_full_name)
        logger.info(f"\nClassification stats:")
        logger.info(f"  Total classified: {stats['total_classified']}")
        logger.info(f"  Trivial: {stats['trivial']}")
        logger.info(f"  Easy: {stats['easy']}")
        logger.info(f"  Medium: {stats['medium']}")
        logger.info(f"  Hard: {stats['hard']}")
    except Exception as e:
        logger.warning(f"Could not fetch classification stats: {e}")
    
    logger.info("\n✓ Classification complete!")
    
    if failed > 0:
        logger.warning(f"\n⚠ {failed} PRs failed to classify. Run command again to retry.")
    
    logger.info("\nNext steps:")
    logger.info("  1. View classifications in Supabase Dashboard")
    logger.info("  2. Run this command again to classify more PRs (idempotent)")
    logger.info("  3. Export to Google Sheets: python main.py export (coming soon)")
    
    return True


def fetch_and_enrich_prs(
    repo_url_or_path: str = None,
    limit: int = 1000,
    enrich: bool = True,
    enrich_only: bool = False,
    fetcher = None,
    supabase: SupabaseClient = None
):
    """
    Fetch PRs/MRs from GitHub/GitLab and optionally enrich them in Supabase.
    
    This implements a two-phase workflow:
    - Phase 1 (Index): Fetch PR/MR list and upsert to Supabase
    - Phase 2 (Enrich): Enrich each PR/MR with files, linked issues, and comments/notes
    
    The process is idempotent - already-enriched items are skipped automatically.
    
    Args:
        repo_url_or_path: Repository in format "owner/repo" or full URL.
                         Examples: "facebook/react", "https://gitlab.com/gitlab-org/gitlab"
                         Optional when enrich_only=True (enriches all repos).
        limit: Maximum number of PRs/MRs to fetch (default: 1000)
        enrich: Whether to enrich PRs/MRs after fetching (default: True)
        enrich_only: If True, skip Phase 1 and only enrich existing items (default: False)
        fetcher: Fetcher instance (optional, will create based on platform if not provided)
        supabase: SupabaseClient instance (optional, will create if not provided)
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Validate arguments
    if not enrich_only and not repo_url_or_path:
        logger.error("Repository is required unless using --enrich-only")
        return False
    
    # Parse repository URL to detect platform and extract owner/repo
    platform = None
    owner = None
    repo = None
    repo_full_name = None
    
    if repo_url_or_path:
        try:
            platform, owner, repo = parse_repository_url(repo_url_or_path)
            repo_full_name = f"{owner}/{repo}"
            logger.info(f"Detected platform: {platform}")
        except ValueError as e:
            logger.error(f"Failed to parse repository: {e}")
            return False
    
    # Initialize clients if not provided
    if fetcher is None or supabase is None:
        config = load_config()
        if fetcher is None and platform:
            try:
                fetcher = initialize_fetcher(platform, config)
            except ValueError as e:
                logger.error(str(e))
                return False
        if supabase is None:
            supabase = SupabaseClient(
                config.credentials.supabase_url,
                config.credentials.supabase_key
            )
    
    logger.info("=" * 80)
    if enrich_only:
        if repo_full_name:
            logger.info(f"ENRICHING EXISTING PRs: {repo_full_name}")
        else:
            logger.info(f"ENRICHING EXISTING PRs: ALL REPOSITORIES")
    else:
        logger.info(f"FETCHING AND ENRICHING: {repo_full_name}")
    logger.info("=" * 80)
    
    # Phase 1: Fetch and Index PRs/MRs (skip if enrich_only=True)
    prs_fetched = 0
    prs_inserted = 0
    insert_errors = 0
    
    if not enrich_only:
        logger.info(f"Phase 1: Fetching up to {limit} {platform.upper() if platform else ''} PRs/MRs...")
        
        try:
            # Calculate pages needed (100 items per page)
            max_pages = (limit + 99) // 100  # Round up
            
            # Fetch using platform-specific method (both use same signature)
            if platform == "github":
                prs = fetcher.fetch_pr_list(owner=owner, repo=repo, max_pages=max_pages)
            elif platform == "gitlab":
                prs = fetcher.fetch_mr_list(owner=owner, repo=repo, max_pages=max_pages)
            else:
                logger.error(f"Unknown platform: {platform}")
                return False
            
            # Limit to exactly what user asked for
            prs = prs[:limit]
            prs_fetched = len(prs)
            
            logger.info(f"✓ Fetched {prs_fetched} merged items from {repo_full_name}")
        except Exception as e:
            logger.error(f"✗ Failed to fetch from {platform}: {e}")
            return False
        
        if not prs:
            logger.warning(f"No merged items found in {repo_full_name}")
            return True
        
        # Insert all PRs/MRs into Supabase (Phase 1 - Index)
        logger.info(f"\nPhase 1: Inserting {len(prs)} items into database...")
        logger.info("-" * 80)
        
        # Prepare all PR/MR data
        pr_data_list = []
        for pr in prs:
            # Extract linked issue number from description (Phase 1 hint for both platforms)
            issue_numbers = fetcher.extract_issue_numbers(pr.get("body") or pr.get("description", ""))
            linked_issue_number = issue_numbers[0] if issue_numbers else None
            
            # Use unified field names (pr_number works for both PR number and MR iid)
            pr_data_list.append({
                "repo": repo_full_name,
                "pr_number": pr.get("number") or pr.get("iid"),  # GitHub: number, GitLab: iid
                "title": pr["title"],
                "body": pr.get("body") or pr.get("description"),  # GitHub: body, GitLab: description
                "merged_at": pr["merged_at"],
                "created_at": pr["created_at"],
                "linked_issue_number": linked_issue_number,
                "platform": platform  # NEW: Store platform
            })
        
        # Batch insert all items at once (much faster than individual inserts)
        try:
            supabase.insert_pr_index_batch(pr_data_list, platform=platform)
            prs_inserted = len(pr_data_list)
            insert_errors = 0
        except Exception as e:
            logger.error(f"✗ Failed to batch insert: {e}")
            prs_inserted = 0
            insert_errors = len(pr_data_list)
        
        logger.info(f"✓ Phase 1 complete: {prs_inserted} items in database, {insert_errors} errors")
        logger.info(f"\nYou can now view these items in Supabase Dashboard!")
    else:
        logger.info(f"Skipping Phase 1 (--enrich-only mode)")
    
    # Phase 2: Enrich PRs that need it
    if not enrich and not enrich_only:
        logger.info(f"\nSkipping enrichment (--no-enrich flag set)")
    else:
        logger.info(f"\nPhase 2: Enriching PRs...")
        logger.info("-" * 80)
        
        # Query database for PRs that need enrichment
        # If repo_full_name is None (--enrich-only without repo), enrich all repos
        prs_to_enrich = supabase.get_prs_needing_enrichment(
            limit=10000, 
            repo=repo_full_name  # None = all repos
        )
        
        if not prs_to_enrich:
            logger.info("No PRs need enrichment - all done!")
        else:
            logger.info(f"Found {len(prs_to_enrich)} PRs needing enrichment")
            
            enriched = 0
            failed = 0
            
            for i, pr_record in enumerate(prs_to_enrich, 1):
                pr_number = pr_record["pr_number"]
                pr_id = pr_record["id"]
                pr_repo = pr_record["repo"]  # Format: "owner/repo"
                pr_platform = pr_record.get("platform", "github")  # Default to github for old records
                
                # Extract owner/repo from the PR record (supports multi-repo enrichment)
                if "/" in pr_repo:
                    pr_owner, pr_repo_name = pr_repo.split("/", 1)
                else:
                    logger.error(f"  PR #{pr_number}: Invalid repo format '{pr_repo}', skipping")
                    failed += 1
                    continue
                
                # Initialize platform-specific fetcher if needed (for multi-repo enrichment)
                try:
                    if not hasattr(fetch_and_enrich_prs, '_fetcher_cache'):
                        fetch_and_enrich_prs._fetcher_cache = {}
                    
                    if pr_platform not in fetch_and_enrich_prs._fetcher_cache:
                        config = load_config()
                        fetch_and_enrich_prs._fetcher_cache[pr_platform] = initialize_fetcher(pr_platform, config)
                    
                    pr_fetcher = fetch_and_enrich_prs._fetcher_cache[pr_platform]
                except Exception as e:
                    logger.error(f"  {pr_repo} #{pr_number}: Failed to initialize {pr_platform} fetcher - {e}")
                    failed += 1
                    continue
                
                try:
                    logger.info(f"  {pr_repo} [{pr_platform}] #{pr_number}: Enriching...")
                    
                    # Enrich using platform-specific method
                    if pr_platform == "github":
                        enrichment_data = pr_fetcher.enrich_pr(
                            owner=pr_owner,
                            repo=pr_repo_name,
                            pr_number=pr_number,
                            pr_body=pr_record.get("body", "")
                        )
                    elif pr_platform == "gitlab":
                        enrichment_data_raw = pr_fetcher.enrich_mr(
                            owner=pr_owner,
                            repo=pr_repo_name,
                            mr_iid=pr_number,
                            linked_issue_number=pr_record.get("linked_issue_number")  # Pass Phase 1 hint
                        )
                        
                        # Transform GitLab field names to match database schema
                        enrichment_data = {
                            "files": enrichment_data_raw.get("files"),
                            "linked_issue": enrichment_data_raw.get("linked_issues"),  # plural -> singular (but it's an array for GitLab!)
                            "issue_comments": enrichment_data_raw.get("issue_notes")  # notes -> comments
                        }
                    else:
                        raise ValueError(f"Unsupported platform: {pr_platform}")
                    
                    # Update Supabase with enriched data
                    supabase.update_pr_enrichment(
                        pr_id=pr_id,
                        enrichment_data=enrichment_data,
                        status="success",
                        error=None
                    )
                    
                    enriched += 1
                    logger.info(f"  {pr_repo} PR #{pr_number}: ✓ Enriched")
                    
                except Exception as e:
                    logger.error(f"  {pr_repo} PR #{pr_number}: ✗ Failed - {e}")
                    failed += 1
                    
                    # Update status to failed in Supabase
                    try:
                        supabase.update_pr_enrichment(
                            pr_id=pr_id,
                            enrichment_data=None,
                            status="failed",
                            error=str(e)
                        )
                    except Exception as update_error:
                        logger.error(f"  {pr_repo} PR #{pr_number}: Could not update failure status: {update_error}")
                
                # Show progress every 10 PRs
                if i % 10 == 0:
                    logger.info(f"  Progress: {i}/{len(prs_to_enrich)} PRs processed...")
    
    # Step 4: Show summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    
    if repo_full_name:
        logger.info(f"Repository: {repo_full_name}")
    else:
        logger.info(f"Repository: ALL REPOSITORIES")
    
    if not enrich_only:
        logger.info(f"PRs fetched from GitHub: {prs_fetched}")
        logger.info(f"PRs inserted to database: {prs_inserted}")
    
    if 'enriched' in locals():
        logger.info(f"PRs newly enriched: {enriched}")
        logger.info(f"PRs failed to enrich: {failed}")
    elif enrich_only:
        logger.info(f"PRs enriched: 0 (none needed enrichment)")
    else:
        logger.info(f"PRs enriched: 0 (enrichment skipped)")
    
    # Get enrichment stats from database
    try:
        stats = supabase.get_enrichment_stats(repo=repo_full_name)
        if repo_full_name:
            logger.info(f"\nDatabase stats for {repo_full_name}:")
        else:
            logger.info(f"\nDatabase stats for all repositories:")
        logger.info(f"  Total PRs: {stats['total']}")
        logger.info(f"  Pending enrichment: {stats['pending']}")
        logger.info(f"  Successfully enriched: {stats['success']}")
        logger.info(f"  Failed enrichment: {stats['failed']}")
    except Exception as e:
        logger.warning(f"Could not fetch database stats: {e}")
    
    if enrich_only:
        logger.info("\n✓ Enrichment complete!")
    else:
        logger.info("\n✓ Fetch and enrichment complete!")
    
    if 'failed' in locals() and failed > 0:
        logger.warning(f"\n⚠ {failed} PRs failed to enrich. Run with --enrich-only to retry failed PRs.")
    
    logger.info("\nNext steps:")
    logger.info("  1. View PRs in Supabase Dashboard")
    if enrich_only:
        logger.info("  2. Run with --enrich-only again to retry failed enrichments")
    else:
        logger.info("  2. Run this command again to enrich newly added PRs (idempotent)")
        logger.info("  3. Run with --enrich-only to enrich/retry existing PRs without fetching new ones")
    logger.info("  3. Run classification: python main.py classify (coming soon)")
    logger.info("  4. Export to Google Sheets: python main.py export (coming soon)")
    
    return True


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Git Issue Classifier - Learn codebases through historical PRs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch 1000 PRs (default)
  python main.py fetch facebook/react
  
  # Fetch 500 PRs
  python main.py fetch facebook/react --limit 500
  
  # Fetch 5000 PRs (takes ~1000 API calls)
  python main.py fetch microsoft/vscode --limit 5000
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Fetch command
    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch and enrich PRs from GitHub"
    )
    fetch_parser.add_argument(
        "repository",
        nargs="?",
        default=None,
        help="Repository in format 'owner/repo' (e.g., 'facebook/react'). Optional with --enrich-only to enrich all repos."
    )
    fetch_parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum number of PRs to fetch (default: 1000)"
    )
    fetch_parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Skip enrichment phase (only fetch and insert PRs to database)"
    )
    fetch_parser.add_argument(
        "--enrich-only",
        action="store_true",
        help="Skip fetch phase - only enrich PRs already in database (pending/failed)"
    )
    
    # Classify command
    classify_parser = subparsers.add_parser(
        "classify",
        help="Classify enriched PRs using LLM"
    )
    classify_parser.add_argument(
        "repository",
        nargs="?",
        default=None,
        help="Repository in format 'owner/repo' (e.g., 'facebook/react'). If not specified, classifies all repos."
    )
    classify_parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of PRs to classify (default: 100)"
    )
    # Explore command
    explore_parser = subparsers.add_parser(
        "explore",
        help="Start the PR Explorer web UI"
    )
    explore_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the API server on (default: 8000)"
    )
    explore_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)"
    )

    subparsers.add_parser(
        "export",
        help="Export classified PRs to Google Sheets (coming soon)"
    )
    subparsers.add_parser(
        "run",
        help="Run all steps: fetch → classify → export (coming soon)"
    )
    
    args = parser.parse_args()
    
    # Show help if no command provided
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Handle fetch command
    if args.command == "fetch":
        # Load config
        try:
            config = load_config()
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
        
        # Initialize Supabase client
        try:
            supabase = SupabaseClient(
                config.credentials.supabase_url,
                config.credentials.supabase_key
            )
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            sys.exit(1)
        
        # Validate mutually exclusive flags
        if args.no_enrich and args.enrich_only:
            logger.error("Cannot use both --no-enrich and --enrich-only")
            sys.exit(1)
        
        # Fetch and enrich (fetcher will be created based on platform detection)
        success = fetch_and_enrich_prs(
            repo_url_or_path=args.repository,
            limit=args.limit,
            enrich=not args.no_enrich,
            enrich_only=args.enrich_only,
            fetcher=None,  # Will be created based on platform
            supabase=supabase
        )
        
        sys.exit(0 if success else 1)
    
    # Handle explore command
    elif args.command == "explore":
        logger.info("=" * 80)
        logger.info("Starting PR Explorer API Server")
        logger.info("=" * 80)
        logger.info(f"API will be available at: http://{args.host}:{args.port}")
        logger.info(f"API docs available at: http://{args.host}:{args.port}/docs")
        logger.info("")
        logger.info("To start the frontend:")
        logger.info("  cd explorer-ui && npm run dev")
        logger.info("")
        logger.info("Press Ctrl+C to stop the server")
        logger.info("=" * 80)

        # Start uvicorn server
        import uvicorn
        uvicorn.run(
            "explorer.app:app",
            host=args.host,
            port=args.port,
            reload=True,  # Enable auto-reload during development
            log_level="info"
        )
        sys.exit(0)

    # Handle classify command
    elif args.command == "classify":
        # Load config
        try:
            config = load_config()
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
        
        # Validate LLM credentials
        if config.credentials.llm_provider == "anthropic":
            if not config.credentials.anthropic_api_key:
                logger.error("ANTHROPIC_API_KEY not set in .env file")
                sys.exit(1)
            api_key = config.credentials.anthropic_api_key
        elif config.credentials.llm_provider == "openai":
            if not config.credentials.openai_api_key:
                logger.error("OPENAI_API_KEY not set in .env file")
                sys.exit(1)
            api_key = config.credentials.openai_api_key
        else:
            logger.error(f"Unsupported LLM provider: {config.credentials.llm_provider}")
            sys.exit(1)
        
        # Initialize clients
        try:
            from classifier.classifier import Classifier
            
            classifier = Classifier(
                provider=config.credentials.llm_provider,
                model=config.credentials.llm_model,
                api_key=api_key
            )
            supabase = SupabaseClient(
                config.credentials.supabase_url,
                config.credentials.supabase_key
            )
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            sys.exit(1)
        
        # Classify PRs
        success = classify_prs(
            repo_full_name=args.repository,
            limit=args.limit,
            classifier=classifier,
            supabase=supabase
        )
        
        sys.exit(0 if success else 1)
    
    # Other commands not yet implemented
    else:
        logger.error(f"Command '{args.command}' is not yet implemented")
        logger.info("Coming soon in future milestones!")
        sys.exit(1)


if __name__ == "__main__":
    main()

