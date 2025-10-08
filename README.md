# Git Issue Classifier

An onboarding tool that helps developers learn large codebases by classifying historical GitHub/GitLab pull requests for educational purposes.

## Overview

This tool fetches historical PRs, analyzes them using LLM classification, and exports summaries to help new developers find suitable learning exercises based on difficulty, categories, and learning value.

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- API credentials (see Setup section)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd git_issue_classifier
   ```

2. Install dependencies using `uv`:
   ```bash
   uv sync
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

4. (Optional) Run tests to verify setup:
   ```bash
   uv run pytest
   ```

## Configuration

The tool requires several API credentials:

- **GitHub Token**: Personal access token with `repo` scope
- **Supabase**: Database credentials for storing PR data
- **LLM API**: OpenAI or Anthropic API key for classification
- **Google Sheets** (optional): Service account credentials for export

See `.env.example` for the complete list of required environment variables.

## Database Setup

Before using the tool, you need to set up the Supabase database schema:

1. **Get your DATABASE_URL from Supabase**:
   - Dashboard → Project Settings → Database → Connection pooling
   - Copy the URI connection string
   - Add to `.env`: `DATABASE_URL=postgresql://...`

2. **Run the setup script**:
   ```bash
   uv run python setup/setup_database.py
   ```

3. **Verify the setup**:
   ```bash
   uv run python setup/setup_database.py --verify
   ```

The schema supports a two-phase workflow:
- **Phase 1 (Index)**: Store basic PR metadata (cheap, reliable)
- **Phase 2 (Enrichment)**: Add files, diffs, and linked issues (expensive, can fail per-PR)

See [setup/README.md](setup/README.md) for detailed documentation.

## Project Structure

```
git_issue_classifier/
├── fetchers/        # GitHub/GitLab API clients
├── storage/         # Supabase and Google Sheets clients
├── classifier/      # LLM classification logic
├── models/          # Data models (Pydantic)
├── utils/           # Logging, rate limiting, helpers
├── setup/           # Database setup scripts
└── main.py          # CLI entrypoint
```

## Usage

### Stage 1: Single Repository (Current)

Fetch and classify PRs from a repository:

```bash
# Fetch 1000 merged PRs (default) and enrich them
uv run python main.py fetch facebook/react

# Fetch 500 PRs
uv run python main.py fetch facebook/react --limit 500

# Fetch 5000 PRs (takes ~1000 API calls)
uv run python main.py fetch microsoft/vscode --limit 5000

# Fetch PRs but skip enrichment (index only)
uv run python main.py fetch facebook/react --no-enrich

# Enrich existing PRs without fetching new ones (retry failed/pending enrichments)
uv run python main.py fetch facebook/react --enrich-only

# Enrich ALL pending/failed PRs across ALL repositories
uv run python main.py fetch --enrich-only

# Classify fetched PRs (coming soon)
uv run python main.py classify facebook/react

# Export to Google Sheets (coming soon)
uv run python main.py export facebook/react

# Run all steps: fetch → classify → export (coming soon)
uv run python main.py run facebook/react
```

**How it works:**
- **Phase 1 (Index)**: Fetches PR metadata from GitHub and stores in database
- **Phase 2 (Enrichment)**: Adds files, diffs, linked issues, and comments to each PR
- **Idempotent**: Safe to run multiple times, skips already-enriched PRs
- **Resumable**: If interrupted, just run again to continue from where it left off
- **Rate limiting**: Automatically waits when GitHub API rate limit is hit
- Default limit: 1000 PRs (automatically handles pagination)

**Flags:**
- `--limit N`: Fetch up to N PRs (default: 1000)
- `--no-enrich`: Skip Phase 2, only fetch and index PRs
- `--enrich-only`: Skip Phase 1, only enrich PRs already in database (pending/failed). If repository is omitted, enriches all repositories.

### Stage 2: Multiple Repositories (Planned)

```bash
# Process multiple repositories
uv run python main.py fetch facebook/react microsoft/vscode

# Or from a file
uv run python main.py fetch --repo-list repos.txt
```

### Future: Repository Management & Web UI

- Persistent repository tracking in database
- Web interface for browsing and managing classified PRs
- Progress tracking for learning exercises

## Development Status

🚧 **Currently in development** - See [milestones.md](milestones.md) for implementation progress.

## Development

### Running Tests

The project uses pytest for testing:

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

### Project Structure

- `models/` - Pydantic data models for validation
- `utils/` - Configuration loading and logging utilities
- `fetchers/` - API clients for GitHub/GitLab (coming soon)
- `storage/` - Database and export clients (coming soon)
- `classifier/` - LLM classification logic (coming soon)
- `tests/` - Test suite

## Reference

- [Initial Design Document](memory/design/001_initial_design.md)
- [Implementation Milestones](milestones.md)