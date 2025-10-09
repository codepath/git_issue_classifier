# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Git Issue Classifier is an onboarding tool that fetches historical GitHub PRs, enriches them with files/issues/comments, and prepares them for LLM classification to help developers learn codebases. The tool uses a two-phase workflow to handle large-scale PR processing efficiently.

## Development Commands

### Setup
```bash
# Install dependencies
uv sync

# Set up environment
cp .env.example .env
# Edit .env with API credentials

# Create database schema
uv run python setup/setup_database.py

# Verify database setup
uv run python setup/setup_database.py --verify
```

### Running Tests
```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_config.py

# Run specific test
uv run pytest tests/test_config.py::TestConfig::test_valid_config
```

### Main Operations
```bash
# Fetch and enrich PRs from a repository (default: 1000 PRs)
uv run python main.py fetch facebook/react

# Fetch specific number of PRs
uv run python main.py fetch facebook/react --limit 500

# Fetch only (skip enrichment)
uv run python main.py fetch facebook/react --no-enrich

# Enrich existing PRs without fetching new ones (retry failed/pending)
uv run python main.py fetch facebook/react --enrich-only

# Enrich ALL pending/failed PRs across ALL repositories
uv run python main.py fetch --enrich-only
```

## Architecture

### Two-Phase Workflow

The core architecture separates cheap, reliable operations from expensive, error-prone ones:

**Phase 1 (Index)**: Fetch basic PR metadata from GitHub's list endpoint
- 1 API call for 100 PRs
- Rarely fails
- Stores: repo, pr_number, title, body, merged_at, created_at
- Sets enrichment_status='pending'

**Phase 2 (Enrichment)**: Enrich each PR with detailed data
- 1-3 API calls per PR (files, issue, comments)
- Can fail individually
- Adds: files (with diffs), linked_issue, issue_comments
- Updates enrichment_status to 'success' or 'failed'

**Phase 3 (Classification)**: LLM analysis (not yet implemented)
- Will analyze enriched PRs to generate difficulty ratings, concepts, etc.

This design enables:
- Resumable workflows (can retry Phase 2 without re-indexing)
- Error recovery (retry only failed PRs)
- Progress tracking via enrichment_status field

### Key Components

**fetchers/github.py**: GitHub API client
- `fetch_pr_list()`: Phase 1 - bulk PR list with pagination
- `enrich_pr()`: Phase 2 - orchestrates files/issue/comments fetching
- `_make_github_request()`: Automatic rate limit handling (waits and retries on 429)
- Truncates patches to 100 lines to manage token usage

**storage/supabase_client.py**: Supabase database client
- `insert_pr_index_batch()`: Bulk upsert for Phase 1 (much faster than individual inserts)
- `get_prs_needing_enrichment()`: Query PRs with status='pending' or 'failed'
- `update_pr_enrichment()`: Update PR with enrichment data and status
- `get_enrichment_stats()`: Returns counts by enrichment_status

**main.py**: CLI entrypoint
- `fetch_and_enrich_prs()`: Main workflow orchestration
- Handles both phases sequentially
- Shows progress every 10 PRs during enrichment
- Provides detailed summary with database stats

**models/data_models.py**: Pydantic models
- `PullRequest`: Matches two-phase database schema
- `Classification`: LLM output format (planned)
- Uses Optional fields for Phase 2 data (nullable)

### Database Schema

**Table: pull_requests**
```sql
-- Phase 1 fields (always present)
repo TEXT NOT NULL
pr_number INTEGER NOT NULL
title TEXT NOT NULL
body TEXT
merged_at TIMESTAMP NOT NULL
created_at TIMESTAMP NOT NULL
linked_issue_number INTEGER

-- Phase 2 fields (nullable, populated during enrichment)
files JSONB
linked_issue JSONB
issue_comments JSONB

-- Status tracking
enrichment_status TEXT NOT NULL DEFAULT 'pending'
enrichment_attempted_at TIMESTAMP
enrichment_error TEXT

UNIQUE(repo, pr_number)
```

**Table: classifications** (planned)
- Denormalized table for easy export to Google Sheets
- Contains PR metadata + LLM classifications
- One classification per PR (UNIQUE constraint on pr_id)

### Important Patterns

1. **Batch Operations**: Always use `insert_pr_index_batch()` for Phase 1, not individual inserts
2. **Idempotency**: All operations use UPSERT behavior and can be safely re-run
3. **Rate Limiting**: GitHub requests automatically wait and retry on 429 responses
4. **Resumability**: Query `get_prs_needing_enrichment()` to find work that needs doing
5. **Error Tracking**: Failed enrichments store error message in `enrichment_error` field
6. **Multi-repo Support**: enrichment_status='pending' queries support repo=None to enrich all repos

### Configuration

Environment variables loaded via `utils/config_loader.py`:
- `GITHUB_TOKEN`: Personal access token with repo scope
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_KEY`: Supabase anon/public key
- `DATABASE_URL`: PostgreSQL connection string (for setup scripts)
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`: For LLM classification (planned)
- `GOOGLE_SHEETS_CREDENTIALS`: For export (planned)

Validated using Pydantic models in `models/config_models.py`.

### Testing

Tests use pytest with fixtures in `tests/conftest.py`:
- `mock_config`: Provides test configuration
- `mock_github_fetcher`: Mocked GitHub client
- Tests validate models, config loading, and utility functions
- Integration tests for GitHub fetcher exist but require real API credentials

## Common Development Tasks

### Adding New Test
Create test file in `tests/` with name pattern `test_*.py`. Use pytest fixtures from `conftest.py`.

### Database Schema Changes
1. Update `setup/setup_database.py` with new schema
2. Run `uv run python setup/setup_database.py --drop` (DANGEROUS - deletes data)
3. Run `uv run python setup/setup_database.py` to recreate
4. Update `models/data_models.py` to match new schema

### Adding New Repository to Fetch
Just run: `uv run python main.py fetch owner/repo`

The database automatically tracks multiple repositories using the `repo` field.

### Retrying Failed Enrichments
Run: `uv run python main.py fetch owner/repo --enrich-only`

This queries for PRs with enrichment_status='pending' or 'failed' and retries them.
