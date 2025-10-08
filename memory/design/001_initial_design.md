# Git Issue Reviewer - Initial Design

**Date:** October 7, 2025  
**Status:** Design Phase

## Product Requirements

### Purpose
Create an onboarding tool for developers joining large codebases. New developers learn system architecture and coding practices by implementing historical GitHub pull requests or GitLab merge requests.

### Core Functionality
1. Fetch historical PRs/MRs from GitHub or GitLab
2. Collect all related context (comments, issues, diffs)
3. Classify PRs using LLM analysis (Claude or OpenAI)
4. Store complete data in Supabase
5. Export summary data to Google Sheets

### Initial Scope
- CLI or script-based execution (no UI initially)
- GitHub and GitLab support (lightweight, pluggable design)
- Best-effort data collection with partial success handling

## Architecture Design

### System Components

```
git_issue_reviewer/
├── config/
│   └── config.yaml          # Repo, credentials, filters
├── fetchers/
│   ├── base.py              # Abstract fetcher interface
│   ├── github.py            # GitHub API client
│   └── gitlab.py            # GitLab API client
├── storage/
│   ├── supabase_client.py   # Supabase operations
│   └── sheets_client.py     # Google Sheets export
├── classifier/
│   ├── prompt_builder.py    # Build LLM prompts from PR data
│   ├── llm_client.py        # Claude/OpenAI client
│   └── classifier.py        # Classification orchestration
├── models/
│   └── data_models.py       # Pydantic models
├── utils/
│   ├── logger.py
│   └── rate_limiter.py      # Handle API rate limits
├── main.py                  # CLI entrypoint
└── requirements.txt
```

### Data Model

**Design Decision: Use JSON blobs instead of normalized schema**
- Rationale: Data is fetched as JSON from APIs and sent as JSON to LLMs
- No need for granular queries across entities
- Faster to implement and more flexible to API changes

#### Supabase Schema

```sql
CREATE TABLE pull_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_name TEXT NOT NULL,
    pr_number INTEGER NOT NULL,
    source TEXT NOT NULL,  -- 'github' or 'gitlab'
    
    -- Three main data blobs
    pr_data JSONB,      -- PR metadata (title, body, merged_at, etc.)
    issue_data JSONB,   -- Linked issue + comments (null if no linked issue)
    diff_data JSONB,    -- Changed files with diffs
    
    -- Fetch tracking
    fetch_status JSONB,  -- {"pr_data": "success", "issue_data": "not_found", "diff_data": "success"}
    fetch_errors JSONB,  -- {"issue_data": "404: Not found"}
    fetched_at TIMESTAMP DEFAULT NOW(),
    
    -- Classification results
    classification JSONB,
    classified_at TIMESTAMP,
    
    UNIQUE(repo_name, pr_number, source)
);

CREATE INDEX idx_pr_repo ON pull_requests(repo_name, source);
CREATE INDEX idx_pr_classification ON pull_requests USING GIN (classification);
```

#### Data Blob Structures

**pr_data:**
```json
{
  "number": 123,
  "title": "...",
  "body": "...",
  "author": "...",
  "created_at": "...",
  "merged_at": "...",
  "state": "merged",
  "labels": [...],
  "files_changed": 5,
  "additions": 150,
  "deletions": 20
}
```

**issue_data:** (null if no linked issue)
```json
{
  "number": 89,
  "title": "...",
  "body": "...",
  "author": "...",
  "created_at": "...",
  "labels": [...],
  "comments": [...]
}
```

**diff_data:**
```json
{
  "files": [
    {
      "filename": "src/auth.py",
      "status": "added",
      "additions": 100,
      "deletions": 0,
      "patch": "diff --git..."
    }
  ],
  "total_additions": 150,
  "total_deletions": 20,
  "truncated": false
}
```

**classification:** (output from LLM)
```json
{
  "difficulty": "medium",
  "categories": ["backend", "api", "database"],
  "learning_value": "high",
  "estimated_time_hours": 4,
  "concepts": ["REST API", "SQL", "error handling"],
  "prerequisites": ["understanding of HTTP", "basic SQL"],
  "reasoning": "..."
}
```

#### Google Sheets Structure
Summary view with key fields:
- PR Number, Title, Link
- Difficulty, Categories, Learning Value
- Estimated Time, Concepts
- Status (classified/pending)

### Error Handling Strategy

**Best-effort fetch with status tracking:**
- Each of the 3 data blobs (pr_data, issue_data, diff_data) fetched independently
- Track success/failure per blob in `fetch_status`
- Store errors in `fetch_errors` for debugging
- Continue with partial data rather than failing entire PR

**Error scenarios:**
- Issue doesn't exist (404) → `fetch_status.issue_data = "not_found"` (not an error)
- Rate limit → Retry with exponential backoff
- Diff too large → Truncate or summarize
- Network timeout → Retry
- Auth failure → Abort immediately

**Fetcher pseudo-code:**
```python
async def fetch_pr_complete(repo, pr_number):
    # 1. Fetch PR (required)
    # 2. Fetch linked issue (optional)
    # 3. Fetch diff (best effort)
    # Return with status for each component
```

### Workflow

```
1. Configure (config.yaml): repo, date range, credentials
2. Fetch PRs from GitHub/GitLab → Save to Supabase
3. For each PR: Build prompt → Send to LLM → Save classification
4. Export summary to Google Sheets
```

### Key Design Decisions

1. **JSON blobs over normalization**: Optimized for "fetch all → send to LLM" pattern
2. **Partial success model**: Don't lose entire PR if one component fails
3. **Status tracking**: Explicit success/failure per component for observability
4. **Pluggable fetchers**: Abstract base class for GitHub/GitLab support
5. **CLI-first**: Start simple, add UI later

## Open Questions

1. **Classification dimensions**: Which fields matter most for learning exercises?
   - Difficulty (easy/medium/hard)
   - Categories (backend/frontend/infrastructure/etc)
   - Learning value (high/medium/low)
   - Time estimate
   - Concepts/skills taught
   - Prerequisites

2. **PR filtering criteria**:
   - Date range?
   - Exclude very small/large PRs?
   - Only merged PRs?
   - Minimum description/comment length?

3. **Multi-repo support**: Single repo per run vs batch processing?

4. **Rate limiting**: How many PRs to process? Need caching/incremental updates?

5. **Cost management**: 
   - Skip re-classification of already-classified PRs?
   - Batch processing with progress tracking?

6. **Diff handling**: How to handle huge diffs that exceed LLM token limits?

## Future Considerations

- Web UI for browsing classified PRs
- Incremental updates (only fetch new PRs)
- Re-classification with improved prompts (versioning)
- Data quality filters (exclude trivial/massive PRs)
- Multiple classification profiles for different audiences
- Caching layer to avoid re-fetching
