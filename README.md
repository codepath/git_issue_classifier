# Git Issue Classifier

An onboarding tool that helps developers learn large codebases by classifying historical GitHub/GitLab merge requests for educational purposes.

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

- **GitHub Token**: Personal access token with `repo` scope (for GitHub repositories)
- **GitLab Token**: Personal access token with `read_api` scope (for GitLab repositories)
- **Supabase**: Database credentials for storing PR/MR data
- **LLM API**: OpenAI or Anthropic API key for classification
- **Google Sheets** (optional): Service account credentials for export

**Note:** You only need the token for the platform(s) you're using. At least one platform token is required.

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

Fetch and classify PRs/MRs from GitHub or GitLab repositories:

#### GitHub Repositories

```bash
# Short format (GitHub only - backward compatible)
uv run python main.py fetch facebook/react

# Full URL format (also works)
uv run python main.py fetch https://github.com/facebook/react

# Fetch with limits and options
uv run python main.py fetch facebook/react --limit 500
uv run python main.py fetch microsoft/vscode --limit 5000
uv run python main.py fetch facebook/react --no-enrich
uv run python main.py fetch facebook/react --enrich-only

# Classify and export
uv run python main.py classify facebook/react
uv run python main.py export facebook/react
```

#### GitLab Repositories

**Note:** GitLab repositories **must** use full URL format.

```bash
# Fetch 1000 merged MRs (default) from GitLab
uv run python main.py fetch https://gitlab.com/gitlab-org/gitlab

# Fetch with limits and options
uv run python main.py fetch https://gitlab.com/gitlab-org/gitlab --limit 500
uv run python main.py fetch https://gitlab.com/gitlab-org/gitlab --no-enrich
uv run python main.py fetch https://gitlab.com/gitlab-org/gitlab --enrich-only

# Classify and export
uv run python main.py classify https://gitlab.com/gitlab-org/gitlab
uv run python main.py export https://gitlab.com/gitlab-org/gitlab
```

#### Enrichment Across All Repositories

```bash
# Enrich ALL pending/failed PRs/MRs across all repositories (both GitHub and GitLab)
uv run python main.py fetch --enrich-only
```

**How it works:**
- **Phase 1 (Index)**: Fetches PR/MR metadata from GitHub/GitLab and stores in database
- **Phase 2 (Enrichment)**: Adds files, diffs, linked issues, and comments/notes to each PR/MR
- **Idempotent**: Safe to run multiple times, skips already-enriched items
- **Resumable**: If interrupted, just run again to continue from where it left off
- **Rate limiting**: Automatically waits when API rate limit is hit
  - GitHub: 5000 requests/hour
  - GitLab: 2000 requests/minute (more generous!)
- Default limit: 1000 PRs/MRs (automatically handles pagination)

**Flags:**
- `--limit N`: Fetch up to N PRs/MRs (default: 1000)
- `--no-enrich`: Skip Phase 2, only fetch and index
- `--enrich-only`: Skip Phase 1, only enrich PRs/MRs already in database (pending/failed). If repository is omitted, enriches all repositories.

### Stage 2: Multiple Repositories (Planned)

```bash
# Process multiple repositories (mix of GitHub and GitLab)
uv run python main.py fetch \
  facebook/react \
  https://github.com/microsoft/vscode \
  https://gitlab.com/gitlab-org/gitlab

# Or from a file (one repository per line)
uv run python main.py fetch --repo-list repos.txt
```

**repos.txt example:**
```
facebook/react
https://github.com/microsoft/vscode
https://gitlab.com/gitlab-org/gitlab
https://github.com/vercel/next.js
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
- `fetchers/` - API clients for GitHub and GitLab
- `storage/` - Database and export clients (coming soon)
- `classifier/` - LLM classification logic (coming soon)
- `tests/` - Test suite

## Reference

- [Initial Design Document](memory/design/001_initial_design.md)
- [Implementation Milestones](milestones.md)