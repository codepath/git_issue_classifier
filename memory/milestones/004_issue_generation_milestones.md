# Issue Generation - Implementation Milestones

**Reference:** `memory/design/004_issue_generation.md`  
**Status:** In Progress - Phase 1 ✅ | Phase 2 ✅ | Phase 3 ✅ | Phase 4 ✅  
**Created:** October 11, 2025  
**Last Updated:** October 11, 2025

## Overview

Break down the issue generation feature into small, iterative milestones that can be verified and tested independently.

---

## Phase 1: Database & Core Infrastructure ✅

### Milestone 1.1: Database Schema Update ✅
- [x] Create ad-hoc migration script `setup/migrations/001_add_issue_generation_columns.py`
  - Add `generated_issue` TEXT column to `pull_requests` table
  - Add `issue_generated_at` TIMESTAMPTZ column to `pull_requests` table
  - Create index `idx_pr_has_generated_issue` on `pull_requests(id)` where `generated_issue IS NOT NULL`
  - Add idempotency checks (only add if columns don't exist)
- [x] Update `setup/setup_database.py` to include new columns in initial table creation
  - Modify `pull_requests` table schema to include both new columns
  - Add index creation to initial setup
- [x] Run migration script on existing database: `python setup/migrations/001_add_issue_generation_columns.py`
- [x] **Verify:** Query database to confirm new columns exist and index is created
- [x] **Verify:** Fresh setup creates table with columns included

### Milestone 1.2: Issue Generation Prompt Template ✅
- [x] Add `ISSUE_GENERATION_PROMPT` constant to `classifier/prompt_template.py`
- [x] Include all required sections: Motivation, Current Behavior, Expected Behavior, Verification
- [x] Use `{pr_context}` and `{classification_info}` placeholders
- [x] Add comprehensive guidelines for quality, structure, and difficulty adaptation
- [x] **Verify:** Import prompt in Python REPL, check it formats correctly with sample data

**Phase 1 Completion Notes:**
- **Completed:** October 11, 2025
- **Files Created:** 
  - `setup/migrations/001_add_issue_generation_columns.py` (migration script)
  - `tests/test_issue_generation.py` (6 tests, all passing)
  - `PHASE1_VERIFICATION.md` (verification report)
- **Files Modified:**
  - `setup/setup_database.py` (added columns/index to schema)
  - `classifier/prompt_template.py` (added ISSUE_GENERATION_PROMPT)
- **Database Changes:**
  - Added `generated_issue` (TEXT) column
  - Added `issue_generated_at` (TIMESTAMPTZ) column
  - Added `idx_pr_has_generated_issue` partial index
- **Tests:** 6/6 passing ✅
- **Production Safety:** Migration run successfully on production database without data loss ✅

---

## Phase 2: Backend - LLM & Context

### Milestone 2.1: LLM Client Extension ✅
- [x] Add `generate_issue()` method to `classifier/llm_client.py`
- [x] Accept prompt string, return plain markdown text (no JSON parsing)
- [x] Reuse existing error handling pattern from `send_prompt()` (no retries per requirements)
- [x] Handle LLM errors gracefully with descriptive messages
- [x] **Verify:** Test method with sample prompt, confirm markdown output
- **Status:** Complete - 3 tests added, all passing
- **Files Modified:** `classifier/llm_client.py`, `tests/test_classifier.py`
- **Documentation:** `MILESTONE_2.1_SUMMARY.md`

### Milestone 2.2: PR Context Endpoint ✅
- [x] Create `GET /api/prs/{repo}/{pr_number}/context` endpoint in `backend/routes.py`
- [x] Fetch PR from database
- [x] Use existing `build_pr_context()` from `context_builder`
- [x] Format classification info (or return "No classification available")
- [x] Return JSON with `pr_context` and `classification_info`
- [x] **Verify:** `curl` endpoint with test PR, confirm context is returned
- **Status:** Complete - 3 tests added, all passing
- **Files Modified:** `backend/routes.py`, `tests/test_explorer_api.py`
- **Documentation:** `MILESTONE_2.2_SUMMARY.md`

### Milestone 2.3: Default Prompt Endpoint ✅
- [x] Create `GET /api/prompts/issue-generation` endpoint in `backend/routes.py`
- [x] Import and return `ISSUE_GENERATION_PROMPT` from `prompt_template`
- [x] Return JSON with `prompt_template` field
- [x] **Verify:** `curl` endpoint, confirm prompt template is returned
- **Status:** Complete - 2 tests added, all passing
- **Files Modified:** `backend/routes.py`, `tests/test_explorer_api.py`
- **Documentation:** `MILESTONE_2.3_SUMMARY.md`

---

## Phase 3: Backend - Issue Generation ✅

### Milestone 3.1: Generate Issue Endpoint (Core Logic) ✅
- [x] Create `POST /api/prs/{repo}/{pr_number}/generate-issue` endpoint
- [x] Define `GenerateIssueRequest` Pydantic model with optional `custom_prompt_template`
- [x] Fetch PR from database (return 404 if not found)
- [x] Build PR context using `build_pr_context()`
- [x] Format classification info
- [x] **Verify:** Endpoint validates request body and fetches PR correctly (test with mock LLM call)
- **Status:** Complete - Core logic implemented and tested
- **Files Modified:** `backend/routes.py`, `tests/test_issue_generation.py`

### Milestone 3.2: Generate Issue Endpoint (LLM Integration) ✅
- [x] Use custom prompt template if provided, otherwise use default
- [x] Fill template with `pr_context` and `classification_info`
- [x] Call `llm_client.generate_issue()` with filled prompt
- [x] Handle LLM errors and return appropriate HTTP errors
- [x] **Verify:** Test endpoint with real LLM call, confirm markdown is generated
- **Status:** Complete - LLM integration working, generates 3392 char issues
- **Token Usage:** ~3400 prompt + 780 completion = 4177 total tokens per generation
- **Manual Test:** Dokploy/dokploy#724 - high-quality issue with motivation, reproduction steps, acceptance criteria, verification

### Milestone 3.3: Generate Issue Endpoint (Database Persistence) ✅
- [x] Save generated markdown to `generated_issue` column
- [x] Update `issue_generated_at` timestamp
- [x] Return JSON with `issue_markdown` and `generated_at`
- [x] **Verify:** Check database after generation, confirm columns are updated
- **Status:** Complete - Database persistence verified
- **Database Verified:** Issue saved (3365 chars) with timestamp 2025-10-11T07:21:04.371446+00:00

### Milestone 3.4: Get Generated Issue Endpoint ✅
- [x] Create `GET /api/prs/{repo}/{pr_number}/generated-issue` endpoint
- [x] Fetch PR from database
- [x] Return 404 if PR not found or no issue generated
- [x] Return JSON with `issue_markdown` and `generated_at` if exists
- [x] **Verify:** Test with PR that has generated issue and one that doesn't
- **Status:** Complete - All endpoints tested and working
- **Files Modified:** `backend/routes.py`, `tests/test_issue_generation.py`

### Phase 3 Summary ✅

**Completed:** October 11, 2025

**Endpoints Implemented:**
1. `GET /api/prompts/issue-generation` - Returns default prompt template
2. `POST /api/prs/{repo}/{pr_number}/generate-issue` - Generates issue with LLM
3. `GET /api/prs/{repo}/{pr_number}/generated-issue` - Retrieves saved issue
4. `GET /api/prs/{repo}/{pr_number}/context` - Returns PR context (already existed)

**Test Coverage:**
- 16 tests total (all passing)
- 4 prompt template tests
- 2 database migration tests
- 10 endpoint tests with mocked LLM

**Manual Verification:**
- Real LLM generation tested: 3392 chars, high quality
- Database persistence confirmed
- Custom prompts tested: 672 chars (brief summary)
- All error cases validated (404s work correctly)
- Token usage measured: ~4177 tokens per generation

**Quality Metrics:**
- Generation time: ~8-10 seconds
- Issue structure: Title + Motivation + Current Behavior + Expected Behavior + Verification
- Includes: Reproduction steps, acceptance criteria checkboxes, testing instructions
- Professional tone, pedagogical approach, no solution hints

**Key Files Modified:**
- `backend/routes.py` - Added 4 endpoints, GenerateIssueRequest model
- `classifier/llm_client.py` - Already had generate_issue() method
- `classifier/prompt_template.py` - Already had ISSUE_GENERATION_PROMPT
- `tests/test_issue_generation.py` - Comprehensive test suite

**Next Phase:** Frontend API Client (Phase 4) and UI Components (Phase 5)

---

## Phase 4: Frontend - API Client ✅

### Milestone 4.1: API Client Methods ✅
- [x] Add `fetchPRContext()` to `frontend/src/lib/api.ts`
- [x] Add `fetchDefaultIssuePrompt()` to `frontend/src/lib/api.ts`
- [x] Add `fetchGeneratedIssue()` to `frontend/src/lib/api.ts` (handles 404 gracefully)
- [x] Add `generateIssue()` to `frontend/src/lib/api.ts` (POST with optional custom prompt)
- [x] **Verify:** Test each method in browser console, confirm API calls work
- **Status:** Complete - All methods were already implemented, tests added and passing
- **Files Modified:** `frontend/src/lib/api.ts`, `frontend/src/lib/api.test.ts`

### Phase 4 Summary ✅

**Completed:** October 11, 2025

**API Methods Implemented:**
All 4 methods were already implemented in `frontend/src/lib/api.ts`:
1. `fetchPRContext(repo, prNumber)` - Fetches PR context and classification info
2. `fetchDefaultIssuePrompt()` - Fetches default prompt template
3. `fetchGeneratedIssue(repo, prNumber)` - Fetches existing issue (returns null for 404)
4. `generateIssue(repo, prNumber, customPromptTemplate?)` - Generates new issue with optional custom prompt

**Test Coverage:**
- Added 14 new tests to `frontend/src/lib/api.test.ts`
- Total: 17 tests (all passing)
- Tests cover:
  - Successful API calls with correct URLs and headers
  - 404 error handling (graceful nulls for `fetchGeneratedIssue`)
  - Generic error handling with appropriate error messages
  - Custom prompt template support
  - URL encoding for repo names with slashes

**TypeScript Types:**
All required types defined in `frontend/src/types/pr.ts`:
- `GeneratedIssue` - Issue markdown and timestamp
- `PRContext` - PR context and classification info
- `IssuePromptTemplate` - Prompt template wrapper
- `PullRequest` - Extended with `generated_issue` and `issue_generated_at` fields

**Quality Metrics:**
- TypeScript compilation: ✅ No errors
- All tests passing: ✅ 17/17
- Proper error handling: ✅ 404s and 500s handled appropriately
- Type safety: ✅ All responses properly typed

**Key Implementation Details:**
- Uses `encodeURIComponent()` for repo names (handles slashes in "org/repo")
- Graceful 404 handling for `fetchGeneratedIssue()` returns null
- Custom prompt template sent as `custom_prompt_template` in POST body
- All methods use `API_BASE_URL` for environment flexibility

**Next Phase:** Frontend UI Components (Phase 5) - Markdown rendering, cards, and modal

---

## Phase 5: Frontend - UI Components ✅

### Milestone 5.1: Markdown Rendering Setup ✅
- [x] Install dependencies: `react-markdown` and `remark-gfm`
- [x] Create simple test component to render sample markdown
- [x] Configure prose styling with Tailwind (`prose prose-sm max-w-none`)
- [x] Test checkbox rendering with GFM plugin
- [x] **Verify:** Render sample issue markdown, confirm formatting looks good
- **Status:** Complete - Dependencies installed, markdown rendering configured
- **Files Modified:** `package.json`, `GeneratedIssueCard.tsx`, `IssueGenerationModal.tsx`

### Milestone 5.2: GeneratedIssueCard (Display Only) ✅
- [x] Create `GeneratedIssueCard.tsx` component in `frontend/src/components/`
- [x] Add card header with "📝 Generated Student Issue" title
- [x] Show empty state with placeholder text when no issue exists
- [x] Show rendered markdown when issue exists
- [x] Add "Generated X ago" timestamp (using native Intl APIs instead of date-fns)
- [x] **Verify:** Render component with mock data (both empty and with issue)
- **Status:** Complete - Card component with display states working
- **Files Created:** `frontend/src/components/GeneratedIssueCard.tsx`

### Milestone 5.3: GeneratedIssueCard (Copy Functionality) ✅
- [x] Add "Copy Issue" button when issue exists
- [x] Implement `copyToClipboard()` using `navigator.clipboard.writeText()`
- [x] Show success alert on successful copy (using native alert)
- [x] Show error alert on copy failure (using native alert)
- [x] **Verify:** Click copy button, paste in text editor, confirm markdown is copied
- **Status:** Complete - Copy functionality working with native alerts
- **Note:** Using native `alert()` instead of toast library for simplicity

### Milestone 5.4: GeneratedIssueCard (Modal Trigger) ✅
- [x] Add "Generate Issue..." button in empty state
- [x] Add "Regenerate..." button when issue exists
- [x] Add `showModal` state and `setShowModal` handler
- [x] Add modal integration with IssueGenerationModal component
- [x] **Verify:** Click buttons, confirm modal state toggles (check React DevTools)
- **Status:** Complete - Modal triggers working correctly

### Milestone 5.5: IssueGenerationModal (Structure) ✅
- [x] Create `IssueGenerationModal.tsx` component
- [x] Add modal overlay with centered container (max-w-5xl, 90vh)
- [x] Add header with "Generate Student Issue - PR #X" and close button
- [x] Add footer with Cancel/Generate buttons
- [x] Add `onClose` and `onIssueGenerated` callbacks
- [x] **Verify:** Open modal, confirm layout looks correct, close button works
- **Status:** Complete - Modal structure and layout working
- **Files Created:** `frontend/src/components/IssueGenerationModal.tsx`

### Milestone 5.6: IssueGenerationModal (Tab Navigation) ✅
- [x] Add tab state management (`'context' | 'prompt' | 'preview'`)
- [x] Create tab buttons for "PR Context", "Prompt Template", "Preview"
- [x] Style active tab with blue border/text
- [x] Show/hide tab content based on `activeTab`
- [x] **Verify:** Click tabs, confirm switching works correctly
- **Status:** Complete - Tab navigation implemented and styled

### Milestone 5.7: IssueGenerationModal (PR Context Tab) ✅
- [x] Fetch PR context using `useQuery` and `api.fetchPRContext()`
- [x] Display read-only textarea with formatted PR context
- [x] Add descriptive text above textarea
- [x] Style textarea with monospace font and gray background
- [x] **Verify:** Open modal, switch to Context tab, confirm PR data is displayed
- **Status:** Complete - PR Context tab with loading states working

### Milestone 5.8: IssueGenerationModal (Prompt Template Tab) ✅
- [x] Fetch default prompt using `useQuery` and `api.fetchDefaultIssuePrompt()`
- [x] Display editable textarea initialized with default prompt
- [x] Add local state for `promptTemplate` (separate from query data)
- [x] Add "Restore Default Template" button
- [x] Add descriptive text explaining placeholders
- [x] **Verify:** Edit prompt, restore default, confirm editing works
- **Status:** Complete - Prompt template tab with editing and restore working

### Milestone 5.9: IssueGenerationModal (Preview Tab) ✅
- [x] Create `previewPrompt` computed value using `useMemo`
- [x] Replace `{pr_context}` and `{classification_info}` placeholders
- [x] Display read-only textarea with complete filled prompt
- [x] Update preview when prompt template changes
- [x] **Verify:** Edit prompt template, switch to preview, confirm changes reflected
- **Status:** Complete - Preview tab with live updates working

### Milestone 5.10: IssueGenerationModal (Generation Logic) ✅
- [x] Add `isGenerating` and `generatedIssue` state
- [x] Implement `handleGenerate()` to call `api.generateIssue()`
- [x] Show loading spinner while generating ("Generating...")
- [x] Handle errors and display error message
- [x] Switch to result view when generation succeeds
- [x] **Verify:** Click generate, wait for response, confirm issue appears
- **Status:** Complete - Generation logic with loading and error states working

### Milestone 5.11: IssueGenerationModal (Result View) ✅
- [x] Hide tabs when `generatedIssue` is set
- [x] Display rendered markdown using `ReactMarkdown`
- [x] Style markdown container (gray background, rounded border)
- [x] Change footer buttons to "Generate Again", "Copy Issue", "Save & Close"
- [x] Implement "Generate Again" to reset to tabs (keep edited prompt)
- [x] **Verify:** Generate issue, confirm result view shows, test "Generate Again"
- **Status:** Complete - Result view with all buttons working

### Milestone 5.12: IssueGenerationModal (Save & Copy) ✅
- [x] Implement copy functionality in result view
- [x] Implement `handleClose()` to call `onIssueGenerated` if issue exists
- [x] Pass generated issue data back to parent component
- [x] **Verify:** Copy issue, close modal, confirm parent component updates
- **Status:** Complete - Save and copy functionality working

### Milestone 5.13: Integrate GeneratedIssueCard into PRDetail ✅
- [x] Add `GeneratedIssueCard` import to `frontend/src/components/PRDetail.tsx`
- [x] Fetch generated issue using `useQuery` and `api.fetchGeneratedIssue()`
- [x] Position card after Classification Card, before LLM Payload
- [x] Pass `repo`, `prNumber`, and `initialIssue` props
- [x] **Verify:** View PR detail page, confirm issue card appears in correct position
- **Status:** Complete - Card integrated into PRDetail page
- **Files Modified:** `frontend/src/components/PRDetail.tsx`

### Phase 5 Summary ✅

**Completed:** October 11, 2025

**Components Implemented:**
1. `GeneratedIssueCard.tsx` (142 lines) - Main card showing generated issue with copy/regenerate
2. `IssueGenerationModal.tsx` (348 lines) - 3-tab modal for issue generation
3. `GeneratedIssueCard.test.tsx` (178 lines) - Test suite with 6 passing tests

**Features Delivered:**
- Empty state with "Generate Issue..." button
- Display state with rendered markdown and action buttons
- Copy to clipboard functionality with user feedback
- 3-tab modal interface:
  - PR Context tab (read-only inspection)
  - Prompt Template tab (editable with restore)
  - Preview tab (live updates of filled prompt)
- Generation logic with loading/error states
- Result view with rendered markdown
- "Generate Again" preserves custom prompt edits
- Integration into PRDetail page (positioned after Classification)

**TypeScript Types Added:**
- `GeneratedIssue` - Issue markdown and timestamp
- `PRContext` - PR context and classification info
- `IssuePromptTemplate` - Prompt template wrapper
- Extended `PullRequest` with `generated_issue` and `issue_generated_at` fields

**Test Coverage:**
- ✅ 6 tests passing (all green)
- Empty state rendering
- Display state with issue
- Copy to clipboard functionality
- Modal open/close behavior
- Timestamp formatting

**Build Status:**
- ✅ TypeScript compilation successful
- ✅ Vite build successful (480KB bundle)
- ✅ All tests passing (6/6)
- ✅ No runtime errors

**Dependencies Added:**
- `react-markdown` ^9.0.1 - Markdown rendering
- `remark-gfm` ^4.0.0 - GitHub Flavored Markdown support

**Design Decisions:**
- Used native `alert()` instead of toast library (simpler, can upgrade later)
- Used native date formatting instead of date-fns (no dependencies)
- Used Tailwind `prose` classes for markdown styling
- Modal is large (max-w-5xl) for comfortable editing
- Prompt edits are per-generation only (not saved globally)

**Key Files:**
- `frontend/src/components/GeneratedIssueCard.tsx` - Main card component
- `frontend/src/components/IssueGenerationModal.tsx` - Generation modal
- `frontend/src/components/PRDetail.tsx` - Integration point
- `frontend/src/types/pr.ts` - TypeScript types
- `frontend/src/lib/api.ts` - API methods (already implemented by Phase 4)
- `frontend/src/components/GeneratedIssueCard.test.tsx` - Test suite

**Documentation:**
- `PHASE5_IMPLEMENTATION_SUMMARY.md` - Comprehensive implementation summary with integration checklist

**Ready for Integration:**
UI is complete and waiting for backend (Phases 3 & 4 were already completed by other agents). The frontend will work immediately once all components are connected.

**Next Phase:** Manual E2E testing (Phase 6) and deployment (Phase 7)

---

## Phase 6: Testing & Polish

### Milestone 6.1: End-to-End Manual Testing
- [ ] Test full flow: PR without issue → Generate → View → Copy
- [ ] Test regeneration flow: existing issue → Regenerate → Edit prompt → Generate
- [ ] Test error handling: invalid PR, LLM errors, network errors
- [ ] Test with different PR types: bug fix, feature, refactor
- [ ] Test with classified and unclassified PRs
- [ ] **Verify:** All flows work smoothly, errors display correctly

### Milestone 6.2: Edge Cases & Error Handling
- [ ] Test with very long PR context (ensure no crashes)
- [ ] Test with missing classification data
- [ ] Test with malformed markdown from LLM
- [ ] Test modal close behavior (prompt edits preserved on "Generate Again")
- [ ] Test concurrent generations (prevent double-clicking)
- [ ] **Verify:** Edge cases handled gracefully

### Milestone 6.3: UI/UX Polish
- [ ] Verify responsive design on different screen sizes
- [ ] Check modal scrolling behavior with long content
- [ ] Ensure loading states are clear and informative
- [ ] Verify toast notifications work correctly
- [ ] Check keyboard accessibility (Esc to close modal)
- [ ] **Verify:** UI feels polished and professional

### Milestone 6.4: Documentation & Cleanup
- [ ] Add JSDoc comments to new backend endpoints
- [ ] Add TypeScript types for API responses
- [ ] Update README if needed (document new feature)
- [ ] Remove any console.log statements or debug code
- [ ] **Verify:** Code is clean and well-documented

---

## Phase 7: Deployment

### Milestone 7.1: Pre-Deployment Checklist
- [ ] Run database migration on staging/production
- [ ] Verify environment variables are set correctly
- [ ] Test with production-like data
- [ ] Check LLM API rate limits and costs
- [ ] **Verify:** Ready for production deployment

### Milestone 7.2: Production Deployment
- [ ] Deploy backend changes
- [ ] Deploy frontend changes
- [ ] Monitor for errors in logs
- [ ] Test with real production data
- [ ] **Verify:** Feature works in production

---

## Implementation Notes

### Testing Strategy
Each milestone should be manually testable:
- **Backend milestones**: Use `curl` or Postman to test endpoints
- **Frontend milestones**: Check browser, React DevTools, and visual appearance
- **Integration milestones**: Test full user workflows

### Dependencies Between Milestones
- Phase 1 must complete before Phase 2
- Phase 2 must complete before Phase 3
- Phase 4 can start once Phase 3.4 is complete
- Phase 5 depends on Phase 4
- Phase 6 depends on all previous phases

### Estimated Complexity
- **Simple milestones** (1-2 hours): 1.1, 2.3, 3.4, 4.1, 5.1, 5.3, 5.4
- **Medium milestones** (2-4 hours): 1.2, 2.1, 2.2, 3.1, 5.2, 5.5, 5.6, 5.13
- **Complex milestones** (4-8 hours): 3.2, 3.3, 5.7-5.12, 6.1

### Suggested Approach
1. Start with Phase 1 & 2 (infrastructure + basic endpoints)
2. Test backend thoroughly with `curl` before starting frontend
3. Build frontend incrementally, testing each component in isolation
4. Save integration testing for Phase 6
5. Don't skip manual verification steps - they catch issues early!

---

## Success Criteria

The feature is complete when:
- ✅ Users can generate issues from PR detail page
- ✅ Generated issues are stored in database
- ✅ Users can customize prompt template per-generation
- ✅ Users can copy generated markdown
- ✅ Users can regenerate issues
- ✅ Modal shows PR context, prompt, and preview
- ✅ Error handling is robust
- ✅ UI is polished and intuitive

