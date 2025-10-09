# PR Context Explorer - Design Document

**Date:** October 8, 2025
**Status:** Design Phase
**Purpose:** Semi-temporary web UI for browsing PRs and developing classification prompts

## Problem Statement

We have ~1000 PRs across 6 repositories stored in Supabase. To develop the LLM classification prompt, we need to:
1. Browse PRs by repository
2. View the complete "context package" that will be sent to the LLM
3. Easily copy/paste this context to manually test classification prompts

Currently, there's no way to view this data without writing SQL queries or Python scripts.

## Requirements

### Must Have
- **PR Index**: List all PRs with filtering by repository
- **Pagination**: 50 PRs per page (too many PRs to show all at once)
- **PR Detail View**: Show PR data:
  - PR metadata (title, dates, stats)
  - PR description/body
  - Linked issue (if exists)
  - Files changed (summary)
- **Visual Polish**: Should look professional (using shadcn/ui components)

### Nice to Have
- Search/filter by PR title or number
- Dark mode toggle
- Copy functionality for PR data (design TBD separately)

### Explicitly Out of Scope (for now)
- Authentication/authorization
- Editing or modifying PR data
- Running classification from the UI
- Multi-user support
- Mobile optimization

## Technical Approach

### Stack: React + shadcn/ui + FastAPI

**Frontend:**
- **React** with TypeScript for interactivity
- **shadcn/ui** for component library (built on Tailwind CSS)
- **Vite** for fast dev server and build
- **TanStack Query** for data fetching and caching

**Backend:**
- **FastAPI** for REST API (serves data to React frontend)
- Reuses existing `SupabaseClient` from `storage/supabase_client.py`

**Why shadcn/ui + Tailwind?**
Yes, you use both together! shadcn/ui is NOT a component library you install - it's copy-paste React components that use Tailwind CSS classes. You get beautiful components with full control over the code. This is the modern approach.

**Why FastAPI?**
React apps need a backend API to fetch data from. FastAPI provides REST endpoints that the React frontend calls. It's the standard architecture for React apps.

**Rationale:**
- Professional, interactive UI from the start
- shadcn/ui gives us beautiful components instantly
- Easy pagination, filtering, and copy functionality
- FastAPI backend reuses existing SupabaseClient - no new data layer needed
- Worth the setup time since this will likely be kept long-term

### Architecture

```
git_issue_classifier/
├── explorer/                    # Backend API
│   ├── app.py                  # FastAPI application
│   └── routes.py               # API routes
├── explorer-ui/                # Frontend React app
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/            # shadcn/ui components (copy-pasted)
│   │   │   ├── PRList.tsx     # PR list with pagination
│   │   │   └── PRDetail.tsx   # PR detail view
│   │   ├── lib/
│   │   │   ├── api.ts         # API client functions
│   │   │   └── utils.ts       # shadcn utilities
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
└── storage/
    └── supabase_client.py      # Existing - used by both main.py and explorer
```

### Data Flow

```
React Component
    ↓
TanStack Query → HTTP Request (fetch)
    ↓
FastAPI Route (explorer/routes.py)
    ↓
SupabaseClient (storage/supabase_client.py) - existing class
    ↓
Supabase Database
    ↓
JSON Response → React State → UI Update
```

### Key Components

#### 1. FastAPI Routes (`explorer/routes.py`)

Uses existing `SupabaseClient` directly - no need to modify models or create new data layer:

```python
from fastapi import FastAPI, HTTPException
from storage.supabase_client import SupabaseClient
from utils.config_loader import load_config

app = FastAPI()

# Initialize at startup
config = load_config()
supabase = SupabaseClient(
    config.credentials.supabase_url,
    config.credentials.supabase_key
)

@app.get("/api/prs")
def list_prs(repo: Optional[str] = None, page: int = 1, per_page: int = 50):
    """List PRs with pagination"""
    offset = (page - 1) * per_page

    # Query using existing supabase client
    query = supabase.client.table("pull_requests").select("*")
    if repo:
        query = query.eq("repo", repo)
    query = query.order("merged_at", desc=True).range(offset, offset + per_page - 1)
    result = query.execute()

    # Get total count
    count_query = supabase.client.table("pull_requests").select("*", count="exact", head=True)
    if repo:
        count_query = count_query.eq("repo", repo)
    count_result = count_query.execute()

    return {
        "prs": result.data,
        "total": count_result.count,
        "page": page,
        "per_page": per_page
    }

@app.get("/api/prs/{repo}/{pr_number}")
def get_pr(repo: str, pr_number: int):
    """Get single PR with full details"""
    # Use existing method
    pr = supabase.get_pr_by_number(repo, pr_number)
    if not pr:
        raise HTTPException(404)
    return pr
```

**Key Point:** Explorer reuses the same `SupabaseClient` that `main.py` uses. No new data access code needed.

#### 2. React Components

**PRList.tsx:**
- Uses shadcn/ui Table component
- Repository filter dropdown (shadcn Select)
- Pagination controls (shadcn Pagination)
- Click row to view detail (React Router)
- Fetches data via TanStack Query from `/api/prs`

**PRDetail.tsx:**
- Uses shadcn/ui Card component
- Displays PR metadata and details
- Fetches data via TanStack Query from `/api/prs/{repo}/{pr_number}`
- Shows: title, body, linked issue, files changed
- Copy button for PR data (implementation TBD in separate design)

## Open Design Questions

### 1. Running the Explorer
**Question:** How should developers start the explorer?

**Recommendation:** Two separate dev servers:

```bash
# Terminal 1: Backend API
uv run python main.py explore --port 8000

# Terminal 2: Frontend dev server (Vite)
cd explorer-ui && npm run dev
```

For production, build React app and serve static files from FastAPI.

**Decision needed:** Confirm this approach

---

### 2. Persistence and State

**Recommendation:** Stateless read-only viewer. No tracking needed.

---

## Implementation Plan

### Phase 1: Backend Foundation (1-2 hours)
1. Add FastAPI to Python dependencies
2. Create `explorer/` directory with:
   - `app.py` - FastAPI app initialization
   - `routes.py` - API route definitions
3. Initialize `SupabaseClient` in explorer (reuse existing class from `storage/`)
4. Implement FastAPI routes:
   - `GET /api/prs` - list with pagination and repo filter
   - `GET /api/prs/{repo}/{pr_number}` - single PR detail
5. Add `explore` subcommand to `main.py` that runs FastAPI
6. Test API with curl/Postman

**Deliverable:** Working REST API returning PR data from Supabase

### Phase 2: Frontend Setup (3-4 hours)
1. Initialize React + TypeScript + Vite project in `explorer-ui/`
2. Install and configure shadcn/ui:
   - Run `npx shadcn-ui@latest init`
   - Add components: Table, Card, Tabs, Button, Select, Pagination
3. Set up TanStack Query for API calls
4. Create API client functions in `lib/api.ts`
5. Set up React Router for /prs and /prs/:repo/:number routes

**Deliverable:** Frontend scaffold with routing and API integration

### Phase 3: Core Features (3-4 hours)
1. Implement `PRList.tsx`:
   - Table with PR data (number, title, repo, merged date)
   - Repository filter dropdown
   - Pagination controls
   - Click row to navigate to detail
2. Implement `PRDetail.tsx`:
   - Display PR metadata (title, dates, stats)
   - Display PR body/description
   - Display linked issue (if exists)
   - Display files changed summary
3. Error handling and loading states
4. Basic styling polish

**Deliverable:** Fully functional PR browser with pagination and filtering

### Phase 4: Nice-to-Haves (optional)
1. Search/filter by PR title or number
2. Dark mode toggle
3. Copy functionality for PR data (requires separate design for context formatting)

## Success Criteria

1. Can browse all 1000 PRs across 6 repositories with pagination
2. Can filter PRs by repository
3. Can view detailed information for any PR
4. UI looks professional and is pleasant to use
5. Takes <5 seconds to find and view any specific PR
6. Backend reuses existing SupabaseClient without code duplication

## Future Considerations

- If we extend this tool:
  - Add authentication for multi-user access
  - Integrate classification directly (run classification from UI)
  - Add PR comparison view (compare 2-3 PRs side-by-side)
  - Add context formatting for LLM (separate design needed)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Large diffs break page rendering | High | Implement diff truncation in `format_context()` |
| Context format changes during prompt dev | High | Make `format_context()` highly configurable |
| Frontend build complexity | Medium | Keep frontend simple, use standard Vite setup |

## Next Steps

1. **Review and answer open design questions** (above)
2. Start Phase 1 implementation
3. Test with sample PRs from different repos
4. Iterate on context format based on manual classification testing
5. Use learnings to build actual classification prompts

---

## Notes

- Built with React + shadcn/ui from the start (worth the setup time)
- Primary value: browsing and inspecting PR data for developing classification prompts
- Secondary value: visual inspection of PR data quality
- Backend reuses existing `SupabaseClient` - no new data layer needed
- shadcn/ui = copy-paste Tailwind components, not a library you install
- FastAPI provides REST API that React frontend consumes (standard React app architecture)
- Context formatting for LLM will be designed separately
