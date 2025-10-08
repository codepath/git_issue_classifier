#!/usr/bin/env python3
"""
Git Issue Classifier - Main CLI entrypoint

This tool fetches historical GitHub PRs, enriches them with files/issues/comments,
and prepares them for LLM classification to help developers learn codebases.

Usage:
    python main.py fetch facebook/react              # Fetch 1000 PRs (default)
    python main.py fetch facebook/react --limit 500  # Fetch 500 PRs
"""

import argparse
import sys
from utils.config_loader import load_config
from utils.logger import setup_logger
from fetchers.github import GitHubFetcher
from storage.supabase_client import SupabaseClient

logger = setup_logger(__name__)


def fetch_and_enrich_prs(
    repo_full_name: str,
    limit: int = 1000,
    enrich: bool = True,
    github: GitHubFetcher = None,
    supabase: SupabaseClient = None
):
    """
    Fetch PRs from GitHub and optionally enrich them in Supabase.
    
    This implements a two-phase workflow:
    1. Fetch PR list from GitHub (with pagination)
    2. Upsert basic PR data to Supabase
    3. (Optional) Enrich each PR with files, linked issue, and comments
    4. (Optional) Update Supabase with enriched data
    
    The process is idempotent - already-enriched PRs are skipped automatically.
    
    Args:
        repo_full_name: Repository in format "owner/repo" (e.g., "facebook/react")
        limit: Maximum number of PRs to fetch (default: 1000)
        enrich: Whether to enrich PRs after fetching (default: True)
        github: GitHubFetcher instance (optional, will create if not provided)
        supabase: SupabaseClient instance (optional, will create if not provided)
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Parse owner/repo
    if "/" not in repo_full_name:
        logger.error("Invalid repository format. Use 'owner/repo' (e.g., 'facebook/react')")
        return False
    
    owner, repo = repo_full_name.split("/", 1)
    
    # Initialize clients if not provided
    if github is None or supabase is None:
        config = load_config()
        if github is None:
            github = GitHubFetcher(config.credentials.github_token)
        if supabase is None:
            supabase = SupabaseClient(
                config.credentials.supabase_url,
                config.credentials.supabase_key
            )
    
    logger.info("=" * 80)
    logger.info(f"FETCHING AND ENRICHING: {repo_full_name}")
    logger.info("=" * 80)
    
    # Step 1: Fetch PRs from GitHub
    logger.info(f"Fetching up to {limit} PRs from GitHub...")
    
    try:
        # Calculate pages needed (100 PRs per page)
        max_pages = (limit + 99) // 100  # Round up
        prs = github.fetch_pr_list(owner=owner, repo=repo, max_pages=max_pages)
        
        # Limit to exactly what user asked for
        prs = prs[:limit]
        
        logger.info(f"✓ Fetched {len(prs)} merged PRs from {repo_full_name}")
    except Exception as e:
        logger.error(f"✗ Failed to fetch PRs from GitHub: {e}")
        return False
    
    if not prs:
        logger.warning(f"No merged PRs found in {repo_full_name}")
        return True
    
    # Step 2: Insert all PRs into Supabase (Phase 1 - Index)
    logger.info(f"\nPhase 1: Inserting {len(prs)} PRs into database...")
    logger.info("-" * 80)
    
    # Prepare all PR data
    pr_data_list = []
    for pr in prs:
        # Extract linked issue number from PR body
        issue_numbers = github.extract_issue_numbers(pr.get("body"))
        linked_issue_number = issue_numbers[0] if issue_numbers else None
        
        pr_data_list.append({
            "repo": repo_full_name,
            "pr_number": pr["number"],
            "title": pr["title"],
            "body": pr.get("body"),
            "merged_at": pr["merged_at"],
            "created_at": pr["created_at"],
            "linked_issue_number": linked_issue_number
        })
    
    # Batch insert all PRs at once (much faster than individual inserts)
    try:
        supabase.insert_pr_index_batch(pr_data_list)
        inserted = len(pr_data_list)
        insert_errors = 0
    except Exception as e:
        logger.error(f"✗ Failed to batch insert PRs: {e}")
        inserted = 0
        insert_errors = len(pr_data_list)
    
    logger.info(f"✓ Phase 1 complete: {inserted} PRs in database, {insert_errors} errors")
    logger.info(f"\nYou can now view these PRs in Supabase Dashboard!")
    
    # Step 3: Enrich PRs that need it (Phase 2 - Enrichment)
    if not enrich:
        logger.info(f"\nSkipping enrichment (--no-enrich flag set)")
    else:
        logger.info(f"\nPhase 2: Enriching PRs...")
        logger.info("-" * 80)
        
        # Query database for PRs that need enrichment
        prs_to_enrich = supabase.get_prs_needing_enrichment(limit=10000, repo=repo_full_name)
        
        if not prs_to_enrich:
            logger.info("No PRs need enrichment - all done!")
        else:
            logger.info(f"Found {len(prs_to_enrich)} PRs needing enrichment")
            
            enriched = 0
            failed = 0
            
            for i, pr_record in enumerate(prs_to_enrich, 1):
                pr_number = pr_record["pr_number"]
                pr_id = pr_record["id"]
                
                try:
                    logger.info(f"  PR #{pr_number}: Enriching...")
                    
                    # Enrich the PR
                    enrichment_data = github.enrich_pr(
                        owner=owner,
                        repo=repo,
                        pr_number=pr_number,
                        pr_body=pr_record.get("body", "")
                    )
                    
                    # Update Supabase with enriched data
                    supabase.update_pr_enrichment(
                        pr_id=pr_id,
                        enrichment_data=enrichment_data,
                        status="success",
                        error=None
                    )
                    
                    enriched += 1
                    logger.info(f"  PR #{pr_number}: ✓ Enriched")
                    
                except Exception as e:
                    logger.error(f"  PR #{pr_number}: ✗ Failed - {e}")
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
                        logger.error(f"  PR #{pr_number}: Could not update failure status: {update_error}")
                
                # Show progress every 10 PRs
                if i % 10 == 0:
                    logger.info(f"  Progress: {i}/{len(prs_to_enrich)} PRs processed...")
    
    # Step 4: Show summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Repository: {repo_full_name}")
    logger.info(f"PRs fetched from GitHub: {len(prs)}")
    logger.info(f"PRs inserted to database: {inserted}")
    if 'enriched' in locals():
        logger.info(f"PRs newly enriched: {enriched}")
        logger.info(f"PRs failed to enrich: {failed}")
    else:
        logger.info(f"PRs enriched: 0 (none needed enrichment)")
    
    # Get enrichment stats from database
    try:
        stats = supabase.get_enrichment_stats(repo=repo_full_name)
        logger.info(f"\nDatabase stats for {repo_full_name}:")
        logger.info(f"  Total PRs: {stats['total']}")
        logger.info(f"  Pending enrichment: {stats['pending']}")
        logger.info(f"  Successfully enriched: {stats['success']}")
        logger.info(f"  Failed enrichment: {stats['failed']}")
    except Exception as e:
        logger.warning(f"Could not fetch database stats: {e}")
    
    logger.info("\n✓ Fetch and enrichment complete!")
    
    if 'failed' in locals() and failed > 0:
        logger.warning(f"\n⚠ {failed} PRs failed to enrich. Run again to retry.")
    
    logger.info("\nNext steps:")
    logger.info("  1. View PRs in Supabase Dashboard")
    logger.info("  2. Run this command again to enrich newly added PRs (idempotent)")
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
        help="Repository in format 'owner/repo' (e.g., 'facebook/react')"
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
    
    # Future commands (not yet implemented)
    subparsers.add_parser(
        "classify",
        help="Classify enriched PRs using LLM (coming soon)"
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
        
        # Initialize clients
        try:
            github = GitHubFetcher(config.credentials.github_token)
            supabase = SupabaseClient(
                config.credentials.supabase_url,
                config.credentials.supabase_key
            )
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            sys.exit(1)
        
        # Fetch and enrich
        success = fetch_and_enrich_prs(
            repo_full_name=args.repository,
            limit=args.limit,
            enrich=not args.no_enrich,
            github=github,
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

