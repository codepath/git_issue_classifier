# Git Issue Reviewer - Implementation Milestones

**Reference:** [Initial Design](memory/design/001_initial_design.md)  
**Last Updated:** October 8, 2025

---

## Milestone 1: Project Foundation ✅
**Goal:** Set up Python project structure and dependencies

- [x] Create project directory structure (`fetchers/`, `storage/`, `classifier/`, `models/`, `utils/`)
- [x] Create `pyproject.toml` with initial dependencies (requests, pydantic, python-dotenv)
- [x] Create `.env.example` file for credential templates
- [x] Create basic `README.md` with setup instructions
- [x] Add `.gitignore` for Python projects

**Manual Test:** Run `uv sync` successfully ✅

---

## Milestone 2: Configuration System ✅
**Goal:** Load and validate configuration from environment variables

- [x] Create Pydantic models for config validation in `models/config_models.py`
- [x] Create `utils/config_loader.py` to load from `.env` and validate
- [x] Add basic logging setup in `utils/logger.py`
- [x] Verify `.env.example` has all required fields with descriptions

**Manual Test:** Load config and print parsed configuration to verify all credentials are read correctly

---

## Milestone 3: Core Data Models ✅
**Goal:** Define Pydantic models for all data structures

- [x] Create `models/data_models.py` with models for:
  - `PullRequest` (PR metadata, files, linked issues)
  - `Classification` (LLM output structure)

**Manual Test:** Create sample instances of each model and validate serialization to JSON ✅

**Design Note:** Data models support two-phase workflow:
- **Phase 1 (Index)**: Basic PR metadata from list endpoint (cheap, reliable)
- **Phase 2 (Enrichment)**: Files, diffs, linked issues (expensive, can fail per-PR)
This allows resuming enrichment on failures without re-indexing.

---

## Milestone 4: GitHub Fetcher - Phase 1 (Index) ✅
**Goal:** Fetch and store basic PR list from GitHub API

- [x] Create `fetchers/github.py` with `GitHubFetcher` class (single class, no abstract base)
- [x] Implement `__init__()` with authentication (token from config)
- [x] Implement `fetch_pr_list()` - fetch PR index with pagination
  - Uses `GET /repos/{owner}/{repo}/pulls?state=closed`
  - Returns basic metadata: number, title, body, author, merged_at, labels
  - Handle pagination (up to max_pages parameter)
  - Filter for merged PRs only (`merged_at is not None`)
- [x] Add basic error handling for auth failures (401, 403)
- [x] Set up standard GitHub API headers

**Manual Test:** Fetch 100-200 PRs from a public repo and print count of merged PRs ✅ (Fetched 165 merged PRs from rails/rails)

**Design Rationale:**
- **No BaseFetcher abstract class**: YAGNI - we don't have GitLab yet (Milestone 19)
- **Single GitHubFetcher class**: All methods share headers, auth, base URL - no need to split
- **Index first**: PR list endpoint rarely fails and is cheap (1 API call for 100 PRs)
- This creates our "index" in Supabase that we'll enrich later

---

## Milestone 5: Supabase Setup with Two-Phase Schema ✅
**Goal:** Set up database to support index + enrichment workflow

- [x] Create Supabase project (manual setup)
- [x] Design schema with two-phase structure:
  - Basic fields (from index): number, title, body, author, merged_at, labels
  - Enriched fields (nullable): files, linked_issue, issue_comments
  - Status tracking: `enrichment_status` ('pending', 'success', 'failed', 'partial')
  - Error tracking: `enrichment_error`, `enrichment_attempted_at`
- [x] Create `storage/supabase_client.py` with connection
- [x] Implement `insert_pr_index()` - save basic PR data with `enrichment_status='pending'`
- [x] Implement `get_prs_needing_enrichment()` - query PRs with status 'pending' or 'failed'
- [x] Implement `update_pr_enrichment()` - update enriched data and status

**Manual Test:** Insert 5 PRs from index, verify all marked as 'pending' - Run `verify_milestone5.py`

**Design Rationale:**
- **Separate index from enrichment**: Index succeeds as a batch, enrichment can fail per-PR
- **Resumable workflow**: Can query for PRs that need enrichment and retry only those
- **Status per PR**: Know exactly which PRs failed and why, don't lose successful work

---

## Milestone 6: GitHub Fetcher - Phase 2 (Enrichment Components) ✅
**Goal:** Implement individual enrichment fetch methods

- [x] Implement `fetch_pr_files()` - get changed files with diffs
  - Uses `GET /repos/{owner}/{repo}/pulls/{pr_number}/files`
  - Returns first 10 files with patches (skips binaries)
  - Truncates patches to 100 lines per file
- [x] Implement `_extract_issue_numbers()` - parse linked issues from PR body
  - Regex pattern: `(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s+#(\d+)`
  - Returns list of issue numbers (removes duplicates)
- [x] Implement `fetch_issue()` - get issue metadata
  - Uses `GET /repos/{owner}/{repo}/issues/{issue_number}`
  - Returns None on 404 (deleted/private issue)
- [x] Implement `fetch_issue_comments()` - get issue discussion
  - Uses `GET /repos/{owner}/{repo}/issues/{issue_number}/comments`
  - Handle pagination (up to 5 pages = 500 comments)
  - Returns empty list if no comments

**Manual Test:** Fetch 10 PRs from Supabase (scalar repository) and enrich them - Run `verify_milestone6.py` ✅

**Design Note:** These are building blocks used by `enrich_pr()` in Milestone 7

---

## Milestone 7: Simple Enrichment Function ✅
**Goal:** Single method to fetch all enrichment data for a PR

- [x] Implement `enrich_pr(owner, repo, pr_number, pr_body) -> dict`
  - Calls `fetch_pr_files()` to get changed files with diffs
  - Extracts issue numbers from PR body using `_extract_issue_numbers()`
  - Fetches linked issue with `fetch_issue()` (returns None if 404)
  - Fetches issue comments with `fetch_issue_comments()` (if issue exists)
  - Returns simple dict: `{files, linked_issue, issue_comments}`
  - Raises exception on failure (no partial success tracking)
- [x] Add logging for enrichment progress

**Manual Test:** Call `enrich_pr()` for a few PRs, verify it returns complete data

**Design Rationale:**
- **Keep it simple**: No complex per-component status tracking
- **Let exceptions bubble up**: Caller handles errors, not the fetcher
- **One function does it all**: Easier to understand and use

---

## Milestone 8: Unified Fetch & Enrich CLI ✅
**Goal:** Single command that fetches and enriches PRs in one pass

- [x] Create `main.py` with `fetch` command
  - CLI: `python main.py fetch facebook/react --limit 1000`
  - Fetches PR list from GitHub (handles pagination automatically)
  - For each PR:
    - Upsert basic data to Supabase (by repo + pr_number)
    - Check if `enrichment_status='success'`
    - If not enriched: call `enrich_pr()` and update
    - If already enriched: skip
  - Progress logging (every 10 PRs)
  - Summary stats at end (enriched, skipped, failed)
  - Continue on per-PR failures (don't crash entire batch)
- [x] Default limit: 1000 PRs
- [x] Delete old `populate_database.py` script

**Manual Test:**
1. Run `python main.py fetch facebook/react --limit 100`
2. Verify PRs are fetched and enriched
3. Run same command again - verify already-enriched PRs are skipped
4. Check Supabase - verify enrichment_status is tracked correctly

**Success Criteria:** User runs one command, gets fully enriched PRs in Supabase

**Design Rationale:**
- **Idempotent by default**: Safe to run multiple times, skips already-enriched PRs
- **No separate phases**: Fetch and enrich happen together
- **Simple pagination**: User specifies total limit, tool handles pages internally
- **Stateless**: No cursor to track - just query Supabase to see what's already done

---

## Milestone 9: Rate Limiting & Retries
**Goal:** Handle API rate limits gracefully

- [ ] Create `utils/rate_limiter.py` with retry logic
- [ ] Implement exponential backoff for rate limit errors (429)
- [ ] Add retry logic for transient network errors
- [ ] Log rate limit status (remaining requests)
- [ ] Abort immediately on auth failures (401, 403)

**Manual Test:** Fetch multiple PRs in quick succession, verify rate limiting is respected

**Design Note:** Add rate limiting decorator to fetcher methods in Milestone 6-7 to avoid hitting GitHub's 5000 req/hour limit

---

## Milestone 10: LLM Client Setup
**Goal:** Set up connection to Claude or OpenAI

- [ ] Create `classifier/llm_client.py` with support for Claude and OpenAI
- [ ] Implement authentication from config
- [ ] Create basic `classify()` method that sends prompt and receives response
- [ ] Add error handling for LLM API failures
- [ ] Add token usage logging

**Manual Test:** Send a simple test prompt to LLM and print response

---

## Milestone 11: Classification Prompt Builder
**Goal:** Build effective prompts from PR data

- [ ] Create `classifier/prompt_builder.py`
- [ ] Design prompt template that includes:
  - PR title, body, and metadata
  - Linked issue context (issue body + comments if present)
  - Changed files with diffs (already truncated to 100 lines per file)
- [ ] Handle token limits by truncating/summarizing large content
- [ ] Build structured prompt requesting specific classification fields

**Manual Test:** Build prompt from a sample PR and print it to verify structure and content

---

## Milestone 12: LLM Classification Implementation
**Goal:** Classify PRs using LLM

- [ ] Create `classifier/classifier.py` with main classification logic
- [ ] Implement classification for all dimensions:
  - Difficulty (easy/medium/hard)
  - Categories (backend/frontend/infrastructure/etc)
  - Learning value (high/medium/low)
  - Estimated time (hours)
  - Concepts taught
  - Prerequisites
  - Reasoning
- [ ] Parse LLM response into `Classification` model
- [ ] Save classification to Supabase
- [ ] Handle classification errors gracefully

**Manual Test:** Classify a sample PR and verify all fields are populated reasonably

**Design Note:** Only classify PRs with `enrichment_status='success'` - partial data may give poor classifications

---

## Milestone 13: Batch Processing
**Goal:** Process multiple PRs efficiently

- [ ] Implement CLI option to specify PR range (e.g., #100-110)
- [ ] Add progress tracking and logging
- [ ] Skip already-classified PRs (check Supabase first)
- [ ] Add option to force re-classification
- [ ] Implement graceful shutdown on interrupt

**Manual Test:** Process 5-10 PRs from a repo, verify all are saved and classified

---

## Milestone 14: Google Sheets Export
**Goal:** Export summary data to Google Sheets

- [ ] Set up Google Sheets API credentials
- [ ] Create `storage/sheets_client.py` with Google Sheets client
- [ ] Implement `create_sheet()` - create new sheet with headers
- [ ] Implement `export_prs()` - write PR summary rows:
  - PR Number, Title, Link
  - Difficulty, Categories, Learning Value
  - Estimated Time, Concepts
  - Status (classified/pending)
- [ ] Handle updates to existing sheet

**Manual Test:** Export 10 classified PRs to a new Google Sheet, verify formatting and data accuracy

---

## Milestone 15: CLI Interface
**Goal:** Create polished command-line interface

- [ ] Create `main.py` with argument parsing (argparse or click)
- [ ] Support commands:
  - `index` - fetch PR index and save to Supabase
  - `enrich` - enrich pending/failed PRs
  - `classify` - classify enriched PRs
  - `export` - export to Google Sheets
  - `run` - do all phases in sequence
- [ ] Add flags for:
  - Repo specification
  - PR number range
  - Force re-fetch/re-classify
  - Dry-run mode
- [ ] Add help text and usage examples

**Manual Test:** Run complete workflow from command line: index → enrich → classify → export

---

## Milestone 16: Error Recovery & Observability
**Goal:** Improve debugging and error recovery

- [ ] Enhance logging with structured output (JSON logs optional)
- [ ] Add summary statistics at end (PRs processed, success rate, errors)
- [ ] Create error report function to show all fetch/classification failures
- [ ] Add health check command to verify all credentials and connections

**Manual Test:** 
- Run with invalid credentials, verify clear error message
- Run health check command to verify all services are accessible

---

## Milestone 17: Documentation & Examples
**Goal:** Complete documentation for users

- [ ] Update README with:
  - Installation instructions (using `uv sync`)
  - Configuration guide
  - Usage examples
  - Troubleshooting tips
- [ ] Add docstrings to all public methods
- [ ] Create example config files
- [ ] Add example output (sample classification)

**Manual Test:** Follow README instructions from scratch on a fresh clone

---

## Future Milestones (Not in Initial Scope)

### Milestone 19: GitLab Support
- [ ] Create `fetchers/gitlab.py` following same interface as GitHub
- [ ] Adapt data models for GitLab-specific fields
- [ ] Test with sample GitLab project

### Milestone 20: Advanced Filtering
- [ ] Filter by date range
- [ ] Exclude very small PRs (< 10 lines changed)
- [ ] Exclude very large PRs (> 1000 lines changed)
- [ ] Filter by labels or PR status

### Milestone 21: Web UI
- [ ] Browse classified PRs
- [ ] Filter by difficulty/category
- [ ] Mark PRs as "completed" for learning progress tracking

---

## Progress Tracking

**Current Milestone:** 9  
**Completed:** 8/17  
**In Progress:** 0  
**Blocked:** 0

## Notes
- Each milestone should take 1-3 hours to complete
- Test thoroughly at each step before moving to next
- Update this file as milestones are completed
- Add notes about implementation decisions or issues encountered

### Milestone 4 Implementation Notes (Completed: Oct 8, 2025)
- Updated `PullRequest` model to match two-phase schema from `github_api_notes.md`
- Removed `FetchStatus` model (replaced with single `enrichment_status` field)
- Implemented `GitHubFetcher.fetch_pr_list()` - returns raw dicts (not Pydantic models)
- Created 6 unit tests (all passing) + manual verification script
- Manual test verified: 165 merged PRs fetched from rails/rails in ~4 seconds
- No data truncation - verification script only truncates display for readability

### Milestone 5 Implementation Notes (Completed: Oct 8, 2025)
- Created `setup/` directory with database setup script and documentation
- Implemented `setup/setup_database.py` - executes SQL programmatically via PostgreSQL connection
- Uses `psycopg2` for direct database access (Supabase Python client doesn't support SQL execution)
- Created `storage/supabase_client.py` with `SupabaseClient` class
- Implemented all required methods: `insert_pr_index()`, `get_prs_needing_enrichment()`, `update_pr_enrichment()`
- Added helper methods: `get_pr_by_number()`, `get_enrichment_stats()`
- All methods use UPSERT for idempotency - safe to re-run
- Created `verify_milestone5.py` - comprehensive test script with 6 tests
- Updated main README.md with Database Setup section
- Added `DATABASE_URL` to config (optional field for setup script)
- Dependencies: Added `supabase>=2.0.0` and `psycopg2-binary>=2.9.0` to pyproject.toml
- **Schema update:** Created separate `classifications` table (denormalized) for easy export to Google Sheets
- Classifications table includes: difficulty ('trivial'/'easy'/'medium'/'hard'), categories, concepts_taught, prerequisites, reasoning
- Denormalized fields in classifications: github_url, repo, pr_number, title, body, merged_at (self-contained for exports)
- Removed learning_value and estimated_hours fields based on requirements

### Milestone 6 Implementation Notes (Completed: Oct 8, 2025)
- Added 4 new methods to `GitHubFetcher` class for Phase 2 enrichment
- Implemented `fetch_pr_files()` - fetches first 10 files with patches, skips binaries
  - Simple rule: first 10 files that have a `patch` field (excludes binary files)
  - Truncates each patch to 100 lines (prevents LLM context overflow)
  - Add truncation marker: `... [TRUNCATED: N more lines]` if patch exceeds limit
- Implemented `_extract_issue_numbers()` - regex-based issue number extraction
  - Pattern matches: fix/fixes/fixed/close/closes/closed/resolve/resolves/resolved #N
  - Case-insensitive matching, removes duplicates while preserving order
- Implemented `fetch_issue()` - fetches issue metadata, returns None on 404
  - Distinguishes between "not found" (404 → None) vs other errors (raises exception)
  - Useful for handling deleted or private issues gracefully
- Implemented `fetch_issue_comments()` - fetches issue comments with pagination
  - Handles up to 5 pages (500 comments) - reasonable limit for most issues
  - Returns empty list if no comments (not an error)
- Created 16 new unit tests (22 total for GitHub fetcher, all passing)
  - Tests cover: extraction logic, file filtering, pagination, truncation, 404 handling
- Created `verify_milestone6.py` - fetches 10 PRs from Supabase and enriches them
  - Pulls PRs from `scalar/scalar` repository (already in database)
  - Displays enriched data for visual inspection: files, patches, linked issues, comments
  - Successfully enriched all 10 PRs (one PR had linked issue #7016 which was fetched)
- **Design decision:** Kept enrichment methods simple and predictable
  - No complex heuristics for file filtering (just first 10 with patches)
  - Fixed 100-line limit per patch (not file-size based)
  - Binary files automatically skipped (no `patch` field from GitHub API)
- All methods return raw dicts (not Pydantic models) for flexibility

### Milestone 7 & 8 Implementation Notes (Completed: Oct 8, 2025)
- Simplified design after reviewing README usage patterns
- **Milestone 7:** Added `enrich_pr()` method to `GitHubFetcher`
  - Single method that orchestrates all enrichment: files, issue, comments
  - No per-component status tracking - either succeeds or raises exception
  - Calls existing Milestone 6 methods: `fetch_pr_files()`, `fetch_issue()`, `fetch_issue_comments()`
  - Returns simple dict: `{files, linked_issue, issue_comments}`
- **Milestone 8:** Created `main.py` CLI with unified fetch & enrich workflow
  - Single command: `python main.py fetch facebook/react --limit 1000`
  - Default limit: 1000 PRs (user thinking in terms of "how many PRs", not pages)
  - Handles pagination internally: calculates pages needed (100 PRs per page)
  - Idempotent by design: 
    - Upserts basic PR data to Supabase (handles duplicates automatically)
    - Checks `enrichment_status='success'` before enriching
    - Skips already-enriched PRs automatically
    - Safe to run multiple times
  - Progress logging every 10 PRs
  - Summary stats: enriched, skipped, failed
  - Continues on per-PR failures (doesn't crash entire batch)
  - Updates `enrichment_status` to 'failed' with error message on failures
- Deleted old `populate_database.py` script (replaced by `main.py`)
- **Design simplifications made:**
  - Removed concept of "partial success" tracking (files succeed, issue fails)
  - No separate "orchestrator" complexity
  - No `--force` parameter (idempotent by default makes it unnecessary)
  - No `--skip-existing` parameter (already the default behavior)
  - User specifies total limit, not pages - tool handles pagination
  - No pagination cursor storage - just query Supabase to see what's done
- **User experience:** One command does everything, safe to run multiple times, naturally resumes where it left off

## Key Design Decisions

### Unified Fetch & Enrich Workflow (Milestones 4-8)
**Decision:** Single command does both fetching and enrichment in one pass
**Rationale:**
- User just wants PRs enriched - doesn't care about implementation phases
- Idempotent by design - checks `enrichment_status` before enriching each PR
- Safe to run multiple times - skips already-enriched PRs automatically
- Natural resume on failures - just re-run and it continues where it left off
- Upsert handles duplicates - no need for complex cursor tracking
- **Implementation detail:** Still fetches basic data first (cheap), then enriches (expensive)
- **User experience:** One command, simple pagination by total PRs wanted

### Single Fetcher Class (Milestone 4)
**Decision:** Use one `GitHubFetcher` class, skip abstract `BaseFetcher` base class
**Rationale:**
- YAGNI principle - no GitLab support yet (Milestone 19)
- All methods share headers, auth, base URL - no need to split
- Can refactor to extract interface when adding second platform
- Keeps implementation simple and focused

### Simple Enrichment Model (Milestone 7)
**Decision:** `enrich_pr()` either succeeds completely or raises exception (no partial success)
**Rationale:**
- Simpler to reason about - either it worked or it didn't
- Caller handles retry logic, not the fetcher
- Per-PR status tracking in Supabase is sufficient ('pending', 'success', 'failed')
- No need for per-component status (files, issue, comments) - overengineering
