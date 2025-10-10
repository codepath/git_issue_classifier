# PR Explorer - Implementation Milestones

**Project:** PR Context Explorer Web UI
**Status:** Planning
**Start Date:** TBD
**Design Doc:** [002_diff_explorer.md](../design/002_diff_explorer.md)

## Overview

Build a React + FastAPI web application to browse ~1000 PRs stored in Supabase. The explorer enables visual inspection of PR data and supports developing LLM classification prompts.

**Stack:** React + TypeScript + shadcn/ui + Vite (frontend) + FastAPI (backend)

## Milestones

### Milestone 1: Backend API Foundation ✅❌⏸️

**Goal:** Create FastAPI REST API that serves PR data from Supabase

**Time Estimate:** 1-2 hours

**Tasks:**
- [ ] Add FastAPI dependency to `pyproject.toml`
- [ ] Create `backend/` directory structure:
  - [ ] `backend/app.py` - FastAPI app initialization
  - [ ] `backend/routes.py` - API route definitions
  - [ ] `backend/server.py` - Uvicorn entry point
- [ ] Initialize `SupabaseClient` in backend (reuse from `storage/supabase_client.py`)
- [ ] Implement `GET /api/prs` endpoint:
  - [ ] Accept query params: `repo` (optional), `page` (default 1), `per_page` (default 50)
  - [ ] Return paginated list of PRs
  - [ ] Include total count for pagination
  - [ ] Filter by repo if provided
- [ ] Implement `GET /api/prs/{repo}/{pr_number}` endpoint:
  - [ ] Use existing `supabase.get_pr_by_number()` method
  - [ ] Return single PR with full details
  - [ ] Return 404 if not found
- [ ] Create standalone server entry point in `backend/server.py`:
  - [ ] Run FastAPI with uvicorn
  - [ ] Accept `--host` and `--port` parameters (default 127.0.0.1:8000)
  - [ ] Enable CORS for local development
- [ ] Test API endpoints with curl/Postman:
  - [ ] List all PRs
  - [ ] List PRs filtered by repo
  - [ ] Get single PR
  - [ ] Test pagination
  - [ ] Verify 404 handling

**Deliverable:** Working REST API at `http://localhost:8000` returning PR data

**Dependencies:** None - uses existing `SupabaseClient`

**Acceptance Criteria:**
- [ ] `python backend/server.py` or `uvicorn backend.app:app --reload` starts FastAPI server
- [ ] Can fetch paginated list of PRs via `/api/prs?page=1&per_page=50`
- [ ] Can filter by repo via `/api/prs?repo=facebook/react`
- [ ] Can fetch single PR via `/api/prs/facebook/react/12345`
- [ ] Returns proper 404 for non-existent PRs
- [ ] CORS enabled for frontend development

---

### Milestone 2: Frontend Project Setup ✅❌⏸️

**Goal:** Initialize React + TypeScript + Vite project with shadcn/ui

**Time Estimate:** 3-4 hours

**Tasks:**
- [ ] Create `frontend/` directory
- [ ] Initialize Vite + React + TypeScript project:
  ```bash
  npm create vite@latest frontend -- --template react-ts
  cd frontend
  npm install
  ```
- [ ] Install and configure shadcn/ui:
  - [ ] Run `npx shadcn-ui@latest init`
  - [ ] Choose options: TypeScript, Tailwind CSS, base color (slate/zinc)
  - [ ] Add components:
    - [ ] `npx shadcn-ui@latest add table`
    - [ ] `npx shadcn-ui@latest add card`
    - [ ] `npx shadcn-ui@latest add select`
    - [ ] `npx shadcn-ui@latest add button`
    - [ ] `npx shadcn-ui@latest add pagination`
- [ ] Install additional dependencies:
  - [ ] React Router: `npm install react-router-dom`
  - [ ] TanStack Query: `npm install @tanstack/react-query`
- [ ] Set up project structure:
  - [ ] `src/lib/api.ts` - API client functions
  - [ ] `src/components/PRList.tsx` - PR list component (stub)
  - [ ] `src/components/PRDetail.tsx` - PR detail component (stub)
  - [ ] `src/types/pr.ts` - TypeScript types for PR data
- [ ] Configure Vite to proxy API requests:
  - [ ] Add proxy config in `vite.config.ts` for `/api` → `http://localhost:8000`
- [ ] Set up React Router:
  - [ ] Route: `/` → `PRList`
  - [ ] Route: `/pr/:repo/:number` → `PRDetail`
- [ ] Set up TanStack Query:
  - [ ] Create `QueryClient` in `main.tsx`
  - [ ] Wrap app with `QueryClientProvider`
- [ ] Create API client functions in `src/lib/api.ts`:
  - [ ] `fetchPRs(repo?, page, perPage)` - calls `/api/prs`
  - [ ] `fetchPR(repo, number)` - calls `/api/prs/{repo}/{number}`
- [ ] Test dev server runs: `npm run dev`

**Deliverable:** React app scaffold with routing, shadcn/ui components, and API client ready

**Dependencies:** Milestone 1 (backend API)

**Acceptance Criteria:**
- [ ] `npm run dev` starts Vite dev server at `http://localhost:5173`
- [ ] shadcn/ui components are available and styled
- [ ] React Router navigation works
- [ ] TanStack Query provider is configured
- [ ] API proxy forwards `/api/*` requests to backend
- [ ] TypeScript types defined for PR data
- [ ] No console errors in browser

---

### Milestone 3: PR List Component ✅❌⏸️

**Goal:** Implement paginated, filterable list of PRs

**Time Estimate:** 2-3 hours

**Tasks:**
- [ ] Implement `PRList.tsx` component:
  - [ ] Use TanStack Query `useQuery` to fetch PRs
  - [ ] Display PRs in shadcn Table component
  - [ ] Table columns:
    - [ ] Repo (e.g., "facebook/react")
    - [ ] PR Number (clickable link)
    - [ ] Title
    - [ ] Merged Date (formatted)
  - [ ] Add repository filter dropdown (shadcn Select):
    - [ ] Options: "All Repositories", then individual repos
    - [ ] Updates query when changed
  - [ ] Add pagination controls (shadcn Pagination):
    - [ ] Show current page / total pages
    - [ ] Previous/Next buttons
    - [ ] Updates query when changed
  - [ ] Handle loading state:
    - [ ] Show skeleton loader or spinner
  - [ ] Handle error state:
    - [ ] Display error message
  - [ ] Handle empty state:
    - [ ] "No PRs found" message
  - [ ] Make table rows clickable:
    - [ ] Navigate to `/pr/{repo}/{number}` on click
- [ ] Style the component:
  - [ ] Add padding/margins for clean layout
  - [ ] Responsive design (works on desktop)
  - [ ] Hover effects on table rows
- [ ] Add header with title: "Pull Request Explorer"

**Deliverable:** Functional PR list page with filtering and pagination

**Dependencies:** Milestone 2 (frontend setup)

**Acceptance Criteria:**
- [ ] Can view list of all PRs in a table
- [ ] Can filter PRs by repository using dropdown
- [ ] Can navigate pages using pagination controls
- [ ] Loading state displays while fetching
- [ ] Error message shows if API fails
- [ ] Clicking PR row navigates to detail page
- [ ] Table shows 50 PRs per page
- [ ] UI looks clean and professional

---

### Milestone 4: PR Detail Component ✅❌⏸️

**Goal:** Display detailed information for a single PR

**Time Estimate:** 2-3 hours

**Tasks:**
- [ ] Implement `PRDetail.tsx` component:
  - [ ] Get `repo` and `number` params from React Router
  - [ ] Use TanStack Query `useQuery` to fetch PR detail
  - [ ] Display PR in shadcn Card component
  - [ ] Show PR metadata section:
    - [ ] Repository name
    - [ ] PR number and title (as heading)
    - [ ] Created date
    - [ ] Merged date
    - [ ] Stats: files changed, additions, deletions (if available)
  - [ ] Show PR body/description:
    - [ ] Display as plain text or markdown (plain text for MVP)
    - [ ] Handle empty body gracefully
  - [ ] Show linked issue section (if exists):
    - [ ] Issue number and title
    - [ ] Issue body preview
    - [ ] "No linked issue" message if none
  - [ ] Show files changed section:
    - [ ] List of changed files with filename and status (added/modified/deleted)
    - [ ] Show summary: "X files changed"
  - [ ] Add "Back to List" button:
    - [ ] Navigates back to PR list
  - [ ] Handle loading state:
    - [ ] Show skeleton or spinner
  - [ ] Handle error state:
    - [ ] Show error message
    - [ ] Show 404 message if PR not found
- [ ] Style the component:
  - [ ] Clean card layout with sections
  - [ ] Readable typography
  - [ ] Proper spacing between sections

**Deliverable:** Functional PR detail page showing all PR information

**Dependencies:** Milestone 3 (PR list)

**Acceptance Criteria:**
- [ ] Can view PR details by clicking from list
- [ ] All PR metadata displays correctly
- [ ] PR body/description is readable
- [ ] Linked issue information shows (when present)
- [ ] Files changed list displays
- [ ] Loading state shows while fetching
- [ ] Error handling works (404, network errors)
- [ ] "Back to List" button works
- [ ] UI is clean and easy to read

---

### Milestone 5: Polish & Testing ✅❌⏸️

**Goal:** Final polish, error handling, and testing

**Time Estimate:** 1-2 hours

**Tasks:**
- [ ] Add final UI polish:
  - [ ] Consistent spacing and padding
  - [ ] Color scheme matches shadcn/ui theme
  - [ ] Smooth transitions/animations (if desired)
  - [ ] Loading states are consistent
- [ ] Improve error handling:
  - [ ] Network error messages
  - [ ] Empty state messages
  - [ ] 404 handling
- [ ] Add page titles:
  - [ ] Set document title for each route
- [ ] Test full user flows:
  - [ ] Browse all PRs → filter by repo → view detail → back to list
  - [ ] Pagination through multiple pages
  - [ ] Direct URL navigation to PR detail
  - [ ] Refresh page maintains state
- [ ] Browser testing:
  - [ ] Chrome
  - [ ] Firefox
  - [ ] Safari (if available)
- [ ] Fix any bugs found
- [ ] Update README with:
  - [ ] How to run backend: `python backend/server.py` or `uvicorn backend.app:app --reload`
  - [ ] How to run frontend: `cd frontend && npm run dev`
  - [ ] Required ports: 8000 (backend), 5173 (frontend)

**Deliverable:** Polished, tested PR explorer ready for use

**Dependencies:** Milestone 4 (PR detail)

**Acceptance Criteria:**
- [ ] UI looks professional and consistent
- [ ] All error states handled gracefully
- [ ] All user flows work end-to-end
- [ ] No console errors or warnings
- [ ] Works in major browsers
- [ ] Documentation updated
- [ ] Can successfully browse and inspect 1000+ PRs

---

## Future Enhancements (Optional)

These are nice-to-have features that can be added later:

### Future: Search Functionality
- [ ] Add search bar to PR list
- [ ] Search by PR title or number
- [ ] Real-time search as user types

### Future: Dark Mode
- [ ] Add dark mode toggle
- [ ] Persist preference in localStorage
- [ ] Use shadcn/ui dark mode support

### Future: Copy Functionality
- [ ] Design context formatting for LLM (separate design doc)
- [ ] Add "Copy Context" button to PR detail
- [ ] Format PR data for LLM prompt testing

---

## Success Metrics

**Core Metrics:**
1. ✅ Can browse all 1000+ PRs with pagination
2. ✅ Can filter PRs by repository
3. ✅ Can view detailed information for any PR
4. ✅ Takes < 5 seconds to find and view a specific PR
5. ✅ UI looks professional using shadcn/ui components
6. ✅ Backend reuses existing SupabaseClient (no code duplication)

**Technical Metrics:**
- Page load time: < 2 seconds
- API response time: < 500ms
- No runtime errors in production
- Works on Chrome, Firefox, Safari

---

## Notes

- **Architecture Decision:** FastAPI backend provides REST API that React frontend consumes. This is the standard architecture for React applications.
- **No Model Changes:** Explorer reuses existing `SupabaseClient` class. No changes to `PullRequest` model or database schema needed.
- **shadcn/ui Approach:** Components are copy-pasted into project (not installed as library). This gives full control over styling and behavior.
- **TanStack Query Benefits:** Handles caching, loading states, error handling, and pagination automatically. Industry standard for React data fetching.
- **Context Formatting Separate:** LLM context formatting will be designed and implemented separately. Explorer focuses on browsing and inspection first.

---

## Timeline

**Total Estimated Time:** 9-14 hours

- Milestone 1: 1-2 hours
- Milestone 2: 3-4 hours
- Milestone 3: 2-3 hours
- Milestone 4: 2-3 hours
- Milestone 5: 1-2 hours

**Realistic Schedule (with context switching):** 2-3 days part-time or 2 days full-time

---

## Automated Test Plan

### Backend Tests (pytest)

**Location:** `tests/test_explorer_api.py`

#### Test Suite 1: API Endpoints
- [ ] **Test: List PRs - basic**
  - Request: `GET /api/prs`
  - Assert: Returns 200, data is list, has pagination fields
  - Assert: Default page=1, per_page=50

- [ ] **Test: List PRs - with pagination**
  - Request: `GET /api/prs?page=2&per_page=25`
  - Assert: Returns correct page and per_page in response
  - Assert: Data length <= 25

- [ ] **Test: List PRs - filter by repo**
  - Request: `GET /api/prs?repo=facebook/react`
  - Assert: All returned PRs have repo="facebook/react"

- [ ] **Test: List PRs - empty repo filter**
  - Request: `GET /api/prs?repo=nonexistent/repo`
  - Assert: Returns empty list, total=0

- [ ] **Test: Get single PR - success**
  - Request: `GET /api/prs/facebook/react/12345` (valid PR)
  - Assert: Returns 200, PR data matches expected structure

- [ ] **Test: Get single PR - not found**
  - Request: `GET /api/prs/fake/repo/99999`
  - Assert: Returns 404

- [ ] **Test: CORS headers present**
  - Request: `OPTIONS /api/prs`
  - Assert: CORS headers exist for local development

#### Test Suite 2: SupabaseClient Integration
- [ ] **Test: Client initialization**
  - Assert: SupabaseClient initialized with correct credentials
  - Assert: Can connect to Supabase

- [ ] **Test: Query builder works**
  - Mock Supabase response
  - Assert: Query built correctly with filters and pagination

**How to run:** `uv run pytest tests/test_explorer_api.py -v`

---

### Frontend Tests (Vitest + React Testing Library)

**Location:** `frontend/src/__tests__/`

#### Test Suite 3: API Client Functions
**File:** `api.test.ts`

- [ ] **Test: fetchPRs - default params**
  - Mock fetch response
  - Call `fetchPRs()`
  - Assert: Calls `/api/prs?page=1&per_page=50`

- [ ] **Test: fetchPRs - with repo filter**
  - Call `fetchPRs('facebook/react', 1, 50)`
  - Assert: Calls `/api/prs?repo=facebook/react&page=1&per_page=50`

- [ ] **Test: fetchPR - success**
  - Mock fetch response
  - Call `fetchPR('facebook/react', 12345)`
  - Assert: Calls correct endpoint, returns parsed data

- [ ] **Test: fetchPR - 404 handling**
  - Mock 404 response
  - Assert: Throws appropriate error

#### Test Suite 4: PRList Component
**File:** `PRList.test.tsx`

- [ ] **Test: Renders loading state**
  - Mock loading query state
  - Assert: Shows loading spinner/skeleton

- [ ] **Test: Renders PR list**
  - Mock successful query with 10 PRs
  - Assert: Table renders 10 rows
  - Assert: Repo, number, title, date columns present

- [ ] **Test: Renders empty state**
  - Mock empty query result
  - Assert: Shows "No PRs found" message

- [ ] **Test: Renders error state**
  - Mock query error
  - Assert: Shows error message

- [ ] **Test: Repository filter changes**
  - Render component
  - Change select dropdown to "facebook/react"
  - Assert: Query refetches with repo filter

- [ ] **Test: Pagination controls work**
  - Render component with 100 PRs total
  - Click "Next" button
  - Assert: Query refetches with page=2

- [ ] **Test: Row click navigation**
  - Render component with PRs
  - Click first row
  - Assert: Navigates to `/pr/facebook/react/12345`

#### Test Suite 5: PRDetail Component
**File:** `PRDetail.test.tsx`

- [ ] **Test: Renders loading state**
  - Mock loading query state
  - Assert: Shows loading spinner

- [ ] **Test: Renders PR details**
  - Mock successful query with full PR data
  - Assert: Shows title, body, metadata
  - Assert: Shows linked issue (if present)
  - Assert: Shows files changed list

- [ ] **Test: Renders PR with no linked issue**
  - Mock PR without linked issue
  - Assert: Shows "No linked issue" message

- [ ] **Test: Renders 404 state**
  - Mock 404 error
  - Assert: Shows "PR not found" message

- [ ] **Test: Back button works**
  - Render component
  - Click "Back to List" button
  - Assert: Navigates to `/`

#### Test Suite 6: E2E User Flows (Playwright - Optional)
**File:** `e2e/explorer.spec.ts`

- [ ] **Test: Full browse flow**
  - Navigate to app
  - Assert: PR list loads
  - Filter by repository
  - Assert: List updates
  - Click PR row
  - Assert: Detail page loads
  - Click back button
  - Assert: Returns to list with filter maintained

- [ ] **Test: Pagination flow**
  - Navigate to app
  - Click "Next" page
  - Assert: URL updates with page=2
  - Assert: New PRs load
  - Refresh page
  - Assert: Still on page 2

- [ ] **Test: Direct URL navigation**
  - Navigate directly to `/pr/facebook/react/12345`
  - Assert: Detail page loads correctly

**How to run:**
- Unit tests: `cd frontend && npm test`
- E2E tests: `cd frontend && npm run test:e2e` (optional)

---

### Test Setup Requirements

#### Backend Test Setup
```python
# tests/test_explorer_api.py
import pytest
from fastapi.testclient import TestClient
from backend.app import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_supabase(monkeypatch):
    # Mock SupabaseClient for isolated testing
    pass
```

#### Frontend Test Setup
```bash
# Install test dependencies
cd frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom
npm install -D @testing-library/user-event msw

# Optional: E2E testing
npm install -D @playwright/test
```

**Frontend test config:** `frontend/vitest.config.ts`

---

### Test Coverage Goals

- **Backend:** 80%+ coverage for API routes
- **Frontend:** 70%+ coverage for components and API client
- **E2E:** Core user flows covered (optional for MVP)

---

### CI/CD Integration (Future)

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run backend tests
        run: uv run pytest tests/test_explorer_api.py -v

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run frontend tests
        run: |
          cd frontend
          npm install
          npm test
```

---

## Questions / Blockers

- [ ] **Q:** Running the explorer - confirm approach of two separate dev servers (FastAPI on 8000, Vite on 5173)?
- [ ] **Q:** State management - confirm stateless read-only viewer (no tracking)?
- [ ] **Q:** E2E testing with Playwright - include in MVP or defer?

---

## Completion Checklist

When all milestones are complete:

- [ ] Can run backend: `python backend/server.py` or `uvicorn backend.app:app --reload`
- [ ] Can run frontend: `cd frontend && npm run dev`
- [ ] Can browse, filter, and paginate through all PRs
- [ ] Can view detailed information for any PR
- [ ] UI is polished and professional
- [ ] README documentation updated
- [ ] All tests passing
- [ ] No known bugs or issues
- [ ] Code reviewed (if applicable)
