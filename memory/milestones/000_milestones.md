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

## Milestone 9: Context Builder
**Goal:** Extract PR context into formatted string for LLM

- [ ] Create `classifier/context_builder.py`
- [ ] Implement `build_pr_context(pr_data: dict) -> str`:
  - Takes PR dict (title, body, files with diffs, linked issue, comments)
  - Returns formatted string with sections:
    - PR metadata (title, author, merged date)
    - PR body
    - Changed files with diffs
    - Linked issue context (if present)
    - Issue comments (if present)
  - Handle missing/optional fields gracefully
  - Add clear section markers for readability
- [ ] Keep it under token limits (truncate if needed - rough target: ~20k tokens)

**Manual Test:** Build context from 3 sample PRs (simple, with issue, complex), print and verify formatting

**Design Rationale:**
- **Shared component**: Explorer GUI will import this to show "what the LLM sees"
- **Pure function**: No LLM or database dependencies - just PR data in, formatted string out
- **Token-aware**: Truncates content to stay within reasonable limits

---

## Milestone 10: LLM Client
**Goal:** Send prompts to Claude or OpenAI and get responses

- [ ] Add dependencies: `openai` and `anthropic` to pyproject.toml
- [ ] Add to config: `LLM_PROVIDER` (claude/openai), `LLM_MODEL`, `LLM_API_KEY`
- [ ] Create `classifier/llm_client.py` with `LLMClient` class
- [ ] Implement `__init__()` - read provider + model + API key from config
- [ ] Implement `send_prompt(prompt: str) -> str`:
  - Route to correct provider (Claude vs OpenAI)
  - Handle authentication
  - Make API call with appropriate parameters
  - Return text response
  - Log token usage
- [ ] Add basic error handling (rate limits, auth failures)

**Manual Test:** Send 2-3 simple test prompts to both Claude and OpenAI, verify responses

**Design Rationale:**
- **Provider-agnostic**: Single interface for multiple LLM providers
- **Dumb wrapper**: No PR/classification logic - just sends text, gets text back
- **Use OpenAI client**: Can handle both OpenAI and Claude models

---

## Milestone 11: Classification Prompt Template
**Goal:** Define the prompt structure for classification

- [ ] Create `classifier/prompt_template.py` with `CLASSIFICATION_PROMPT` constant
- [ ] Design prompt that:
  - Explains the classification task
  - Lists all required fields (difficulty, categories, concepts, prerequisites, reasoning)
  - Provides clear instructions for each field
  - Requests JSON output format
  - Includes examples (1-2 sample classifications)
- [ ] Keep prompt concise (target: ~1k tokens)

**Manual Test:** Review prompt manually, ensure it's clear and complete

**Design Rationale:**
- **Separate from code**: Makes it easy to iterate on prompt without touching code
- **Configuration, not logic**: Just the template, no processing
- **Examples included**: Few-shot learning improves classification quality

---

## Milestone 12: Classifier Implementation
**Goal:** Combine context + prompt + LLM to classify PRs

- [ ] Create `classifier/classifier.py` with `Classifier` class
- [ ] Implement `__init__()` - create `LLMClient` instance
- [ ] Implement `classify_pr(pr_data: dict) -> dict`:
  - Call `build_pr_context(pr_data)` to get formatted context
  - Combine with `CLASSIFICATION_PROMPT` template
  - Call `llm_client.send_prompt()`
  - Parse JSON response into dict
  - Validate required fields are present
  - Return classification dict
- [ ] Handle parsing errors (malformed JSON, missing fields)
- [ ] Add retry logic (1-2 retries if parsing fails)

**Manual Test:** Classify 3 sample PRs, verify all fields populated reasonably

**Design Rationale:**
- **Orchestrator**: Combines context builder + prompt + LLM client
- **No database logic**: Takes PR data, returns classification - doesn't touch Supabase
- **Error handling**: Retries on parse failures, raises exception on persistent failures

---

## Milestone 13: Supabase Classification Methods
**Goal:** Add database methods for classification workflow

- [ ] Add to `storage/supabase_client.py`:
  - `get_unclassified_prs(repo: str, limit: int) -> list[dict]`
    - Query PRs where `enrichment_status='success'`
    - LEFT JOIN classifications table
    - WHERE classification is NULL
    - ORDER BY merged_at DESC
    - LIMIT to requested amount
  - `save_classification(repo: str, pr_number: int, classification: dict) -> None`
    - Insert into classifications table
    - Include denormalized fields (github_url, title, etc.)
    - Use UPSERT (idempotent)

**Manual Test:** Query unclassified PRs, verify results; save test classification, verify in Supabase

**Design Rationale:**
- **Database logic isolated**: Can test with real Supabase data
- **Idempotent operations**: UPSERT allows re-running safely
- **Denormalized classifications**: Self-contained for easy export to Google Sheets

---

## Milestone 14: CLI Classify Command
**Goal:** User-facing command to classify PRs

- [ ] Add `classify` command to `main.py`:
  - CLI: `python main.py classify facebook/react --limit 100`
  - Query unclassified PRs via `get_unclassified_prs()`
  - Loop through each PR:
    - Call `classifier.classify_pr(pr_data)`
    - Save via `save_classification()`
    - Handle errors, continue on failures
  - Progress logging every 10 PRs
  - Summary stats (classified, skipped, failed)
- [ ] Default limit: 100 PRs
- [ ] Make idempotent (skip already-classified PRs)

**Manual Test:**
1. Run `python main.py classify facebook/react --limit 20`
2. Verify classifications saved to Supabase
3. Run again - verify skips already-classified PRs

**Design Rationale:**
- **Mirrors `fetch` command**: Same UX pattern - idempotent, resumable, safe to re-run
- **Driver orchestrates**: Fetches data, calls classifier, saves results
- **Continue on failures**: Don't crash entire batch if one PR fails to classify

---

## Milestone 15: Google Sheets Export
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

## Progress Tracking

**Current Milestone:** 9  
**Completed:** 8/19  
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

### Classification Architecture (Milestones 9-14)
**Decision:** Separate context building from classification logic, use shared LLM client
**Rationale:**
- **Context Builder as shared component**: Explorer GUI needs to show "what the LLM sees"
  - Pure function: PR data in, formatted string out
  - No dependencies on LLM or database
  - Can be imported and used independently
- **LLM Client as dumb wrapper**: Just sends prompts, gets responses
  - Provider-agnostic: Supports both Claude and OpenAI
  - No knowledge of PR structure or classification logic
  - Reusable for other LLM tasks
- **Classifier as orchestrator**: Combines context + prompt + LLM
  - No database dependencies - takes PR data, returns classification
  - Handles retries and parsing errors
  - Main entry point: `classify_pr(pr_data) -> dict`
- **Driver in main.py**: Mirrors `fetch` command pattern
  - Queries database for unclassified PRs
  - Calls classifier, saves results
  - Idempotent, resumable, safe to re-run
- **Prompt as configuration**: Separate file makes iteration easy
  - No code changes needed to tweak prompt
  - Can version control prompt iterations
  - Includes few-shot examples
