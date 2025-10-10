# Onboarding Workflow Enhancement - Design Document

**Date:** October 9, 2025  
**Status:** Design Phase  
**Purpose:** Enable onboarding designers to curate historical PRs as training exercises

## Problem Statement

The core purpose of this system is to create onboarding experiences for large codebases. New engineers learn by implementing historical issues against a time-rewound codebase fork.

**Current Limitations:**
- No way to filter PRs by date cutoff (to match the rewound codebase state)
- PRs sorted descending by date (newest first), opposite of onboarding progression
- No classification-based filtering (onboarding suitability, difficulty, etc.)
- Cannot see the LLM payload that produced classifications
- No way to mark PRs as training candidates

**Consequence:** Onboarding designers cannot efficiently curate appropriate training exercises.

## Requirements

### Must Have
1. **Date cutoff filter**: Select a date (default: 3 months ago). Show only PRs merged after this date.
2. **Ascending date sort**: PRs ordered chronologically (oldest first) to match onboarding progression
3. **Classification filters**: Filter by:
   - `onboarding_suitability` (primary filter - "excellent" or "poor")
   - `difficulty` (trivial/easy/medium/hard)
   - `task_clarity` (clear/partial/poor)
   - `is_reproducible` (highly likely/maybe/unclear)
4. **Enhanced PR detail view**: Reorder sections:
   - PR title and body (context)
   - Classification recommendation (what LLM decided)
   - LLM payload (what LLM saw - for debugging misclassifications)
5. **Favorites system**: Mark PRs as training candidates with database persistence

### Nice to Have
- "Only show favorites" toggle

### Out of Scope (for now)
- Issue generation from PRs (future challenge - separate design needed)
- Multi-user favorites (single user assumed for now)
- PR difficulty re-ranking or adjustment
- Training progress tracking

## User Workflow

**As an onboarding designer, my workflow is:**

1. **Select repository and date cutoff**
   - Choose repo from dropdown (existing feature)
   - Select cutoff date via calendar picker (default: 3 months ago)
   - System shows PRs merged *after* this date (simulating a codebase state)

2. **Filter by classification**
   - Primary filter: `onboarding_suitability = "excellent"`
   - Secondary: adjust difficulty range (e.g., easy → medium)
   - Tertiary: filter by task clarity, reproducibility

3. **Browse chronologically**
   - PRs displayed in ascending date order (oldest first)
   - Matches temporal progression of onboarding experience
   - Engineer will encounter these PRs in chronological order

4. **Inspect individual PRs**
   - Click PR to view detail
   - Read PR title/body (context)
   - Review classification (difficulty, suitability, concepts taught)
   - Examine LLM payload to understand why it was classified this way
   - Debug misclassifications by seeing what context LLM received

5. **Mark training candidates**
   - Click star icon to favorite promising PRs
   - Favorites persist in database
   - Later: review all favorites to finalize training set

## Technical Design

### Database Schema Changes

Add favorites support to `pull_requests` table:

```sql
-- Add is_favorite column
ALTER TABLE pull_requests 
ADD COLUMN is_favorite BOOLEAN DEFAULT FALSE;

-- Add index for efficient favorite queries
CREATE INDEX idx_pr_favorite ON pull_requests(is_favorite);

-- Add index for date filtering (if not exists)
CREATE INDEX idx_pr_merged_at ON pull_requests(merged_at);
```

**Migration Strategy:** Run via `setup/setup_database.py` or manual SQL script.

### Backend Changes

#### New API Endpoints

**1. Enhanced PR List Endpoint**

Extend existing `/api/prs` with new query parameters:

```python
@router.get("/api/prs")
def list_prs(
    repo: Optional[str] = None,
    cutoff_date: Optional[str] = None,  # NEW: ISO date "YYYY-MM-DD"
    sort_order: str = "desc",           # NEW: "asc" or "desc"
    onboarding_suitability: Optional[str] = None,  # NEW: filter
    difficulty: Optional[str] = None,   # NEW: filter
    task_clarity: Optional[str] = None, # NEW: filter
    is_reproducible: Optional[str] = None, # NEW: filter
    is_favorite: Optional[bool] = None, # NEW: filter favorites
    page: int = 1,
    per_page: int = 50
):
    """
    List PRs with enhanced filtering for onboarding workflow.
    
    New filters:
    - cutoff_date: Only show PRs merged on or after this date (YYYY-MM-DD)
    - sort_order: "asc" (oldest first) or "desc" (newest first)
    - onboarding_suitability: Filter by classification.onboarding_suitability
    - difficulty: Filter by classification.difficulty
    - task_clarity: Filter by classification.task_clarity
    - is_reproducible: Filter by classification.is_reproducible
    - is_favorite: If true, only show favorited PRs
    """
    # Query pull_requests with LEFT JOIN classifications
    # Filter by classifications.* fields as needed
```

**Implementation Note:** Need to JOIN `pull_requests` with `classifications` table to filter by classification fields.

**2. LLM Payload Endpoint**

```python
@router.get("/api/prs/{repo:path}/{pr_number}/llm_payload")
def get_llm_payload(repo: str, pr_number: int):
    """
    Reconstruct the LLM payload (context + prompt) for a PR.
    
    This shows exactly what the LLM saw when classifying the PR.
    Useful for debugging misclassifications.
    
    Returns:
    {
        "pr_context": "...",  # Output of build_pr_context()
        "full_prompt": "...", # Context + classification prompt template
        "prompt_template": "..." # The template used
    }
    """
    # 1. Fetch PR data
    pr = supabase.get_pr_by_number(repo, pr_number)
    
    # 2. Reconstruct context using classifier.context_builder
    from classifier.context_builder import build_pr_context
    from classifier.prompt_template import CLASSIFICATION_PROMPT
    
    pr_context = build_pr_context(pr)
    full_prompt = CLASSIFICATION_PROMPT.format(pr_context=pr_context)
    
    return {
        "pr_context": pr_context,
        "full_prompt": full_prompt,
        "prompt_template": CLASSIFICATION_PROMPT
    }
```

**3. Favorite Toggle Endpoint**

```python
@router.post("/api/prs/{repo:path}/{pr_number}/favorite")
def toggle_favorite(repo: str, pr_number: int):
    """
    Toggle favorite status for a PR.
    
    Returns updated PR with new is_favorite value.
    """
    # 1. Get current PR
    pr = supabase.get_pr_by_number(repo, pr_number)
    if not pr:
        raise HTTPException(404)
    
    # 2. Toggle is_favorite
    new_value = not pr.get("is_favorite", False)
    
    # 3. Update in database
    result = supabase.client.table("pull_requests").update({
        "is_favorite": new_value
    }).eq("id", pr["id"]).execute()
    
    return result.data[0]
```

**4. List Favorites Endpoint**

```python
@router.get("/api/prs/favorites")
def list_favorites(repo: Optional[str] = None):
    """
    List all favorited PRs, optionally filtered by repo.
    
    Useful for reviewing training candidate set.
    """
    query = supabase.client.table("pull_requests").select("*")
    query = query.eq("is_favorite", True)
    
    if repo:
        query = query.eq("repo", repo)
    
    query = query.order("merged_at", desc=False)  # Chronological order
    result = query.execute()
    
    return {"favorites": result.data}
```

### Frontend Changes

#### 1. PRList Component Enhancements

**New UI Elements:**

```tsx
// Date picker (default: 3 months ago)
<div className="mb-4">
  <label>Cutoff Date (show PRs after):</label>
  <input 
    type="date" 
    value={cutoffDate} 
    onChange={(e) => setCutoffDate(e.target.value)}
  />
  <button onClick={() => setCutoffDate(threeMonthsAgo)}>
    Reset to 3 months ago
  </button>
</div>

// Sort order toggle
<div>
  <label>Sort Order:</label>
  <select value={sortOrder} onChange={(e) => setSortOrder(e.target.value)}>
    <option value="asc">Oldest First (Chronological)</option>
    <option value="desc">Newest First</option>
  </select>
</div>

// Classification filters (priority order)
<div className="flex gap-4">
  <select 
    value={onboardingSuitability} 
    onChange={(e) => setOnboardingSuitability(e.target.value)}
  >
    <option value="">All Suitability</option>
    <option value="excellent">Excellent</option>
    <option value="poor">Poor</option>
  </select>
  
  <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
    <option value="">All Difficulties</option>
    <option value="trivial">Trivial</option>
    <option value="easy">Easy</option>
    <option value="medium">Medium</option>
    <option value="hard">Hard</option>
  </select>
  
  <select value={taskClarity} onChange={(e) => setTaskClarity(e.target.value)}>
    <option value="">All Clarity</option>
    <option value="clear">Clear</option>
    <option value="partial">Partial</option>
    <option value="poor">Poor</option>
  </select>
  
  <select value={reproducible} onChange={(e) => setReproducible(e.target.value)}>
    <option value="">All Reproducibility</option>
    <option value="highly likely">Highly Likely</option>
    <option value="maybe">Maybe</option>
    <option value="unclear">Unclear</option>
  </select>
  
  <label>
    <input 
      type="checkbox" 
      checked={showOnlyFavorites} 
      onChange={(e) => setShowOnlyFavorites(e.target.checked)}
    />
    Favorites Only
  </label>
</div>
```

**New Table Columns:**

Add columns for classification fields and favorite star:

```tsx
<table>
  <thead>
    <tr>
      <th>★</th> {/* Favorite */}
      <th>Repository</th>
      <th>PR #</th>
      <th>Title</th>
      <th>Merged Date</th>
      <th>Suitability</th> {/* NEW */}
      <th>Difficulty</th>  {/* NEW */}
      <th>Clarity</th>     {/* NEW */}
      <th>Status</th>
    </tr>
  </thead>
  <tbody>
    {prs.map(pr => (
      <tr key={pr.id}>
        <td>
          <button onClick={(e) => {
            e.stopPropagation(); // Don't trigger row click
            toggleFavorite(pr);
          }}>
            {pr.is_favorite ? "★" : "☆"}
          </button>
        </td>
        <td>{pr.repo}</td>
        <td>#{pr.pr_number}</td>
        <td>{pr.title}</td>
        <td>{formatDate(pr.merged_at)}</td>
        <td>
          <Badge variant={pr.classification?.onboarding_suitability}>
            {pr.classification?.onboarding_suitability || "N/A"}
          </Badge>
        </td>
        <td>{pr.classification?.difficulty || "N/A"}</td>
        <td>{pr.classification?.task_clarity || "N/A"}</td>
        <td>
          <Badge variant={pr.enrichment_status}>
            {pr.enrichment_status}
          </Badge>
        </td>
      </tr>
    ))}
  </tbody>
</table>
```

**Data Fetching:**

```tsx
const { data, isLoading, error } = useQuery({
  queryKey: [
    "prs", 
    selectedRepo, 
    cutoffDate, 
    sortOrder, 
    onboardingSuitability, 
    difficulty,
    taskClarity,
    reproducible,
    showOnlyFavorites,
    page
  ],
  queryFn: () => fetchPRs({
    repo: selectedRepo || undefined,
    cutoff_date: cutoffDate,
    sort_order: sortOrder,
    onboarding_suitability: onboardingSuitability || undefined,
    difficulty: difficulty || undefined,
    task_clarity: taskClarity || undefined,
    is_reproducible: reproducible || undefined,
    is_favorite: showOnlyFavorites ? true : undefined,
    page,
    per_page: perPage
  }),
});
```

#### 2. PRDetail Component Enhancements

**Reorganized Layout:**

```tsx
<div className="container mx-auto p-6">
  {/* 1. PR Header - title, body, metadata */}
  <PRHeader pr={pr} />
  
  {/* 2. Classification Card - recommendation */}
  <ClassificationCard classification={pr.classification} />
  
  {/* 3. LLM Payload - collapsible, copyable */}
  <LLMPayloadCard repo={pr.repo} prNumber={pr.pr_number} />
  
  {/* 4. Files Changed (existing) */}
  <FilesChangedCard files={pr.files} />
  
  {/* 5. Linked Issue (existing) */}
  {pr.linked_issue && <LinkedIssueCard issue={pr.linked_issue} />}
  
  {/* 6. Issue Comments (existing) */}
  {pr.issue_comments && <IssueCommentsCard comments={pr.issue_comments} />}
</div>
```

**New Component: ClassificationCard**

```tsx
function ClassificationCard({ classification }) {
  if (!classification) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
        <p>No classification available for this PR</p>
      </div>
    );
  }
  
  return (
    <div className="bg-white rounded-lg shadow p-6 mb-6">
      <h2 className="text-lg font-bold mb-3">Classification Recommendation</h2>
      
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <span className="text-sm font-medium text-gray-500">Onboarding Suitability:</span>
          <Badge variant={classification.onboarding_suitability}>
            {classification.onboarding_suitability}
          </Badge>
        </div>
        <div>
          <span className="text-sm font-medium text-gray-500">Difficulty:</span>
          <Badge>{classification.difficulty}</Badge>
        </div>
        <div>
          <span className="text-sm font-medium text-gray-500">Task Clarity:</span>
          <Badge>{classification.task_clarity}</Badge>
        </div>
        <div>
          <span className="text-sm font-medium text-gray-500">Reproducibility:</span>
          <Badge>{classification.is_reproducible}</Badge>
        </div>
      </div>
      
      <div className="mb-3">
        <span className="text-sm font-medium text-gray-500">Categories:</span>
        <div className="flex gap-2 mt-1">
          {classification.categories.map(cat => (
            <Badge key={cat} variant="outline">{cat}</Badge>
          ))}
        </div>
      </div>
      
      <div className="mb-3">
        <span className="text-sm font-medium text-gray-500">Concepts Taught:</span>
        <ul className="list-disc list-inside text-sm text-gray-700 mt-1">
          {classification.concepts_taught.map(concept => (
            <li key={concept}>{concept}</li>
          ))}
        </ul>
      </div>
      
      <div className="mb-3">
        <span className="text-sm font-medium text-gray-500">Prerequisites:</span>
        <ul className="list-disc list-inside text-sm text-gray-700 mt-1">
          {classification.prerequisites.map(prereq => (
            <li key={prereq}>{prereq}</li>
          ))}
        </ul>
      </div>
      
      <div>
        <span className="text-sm font-medium text-gray-500">Reasoning:</span>
        <p className="text-sm text-gray-700 mt-1">{classification.reasoning}</p>
      </div>
    </div>
  );
}
```

**New Component: LLMPayloadCard**

```tsx
function LLMPayloadCard({ repo, prNumber }) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const { data: payload, isLoading } = useQuery({
    queryKey: ["llm-payload", repo, prNumber],
    queryFn: () => fetchLLMPayload(repo, prNumber),
    enabled: isExpanded, // Only fetch when expanded
  });
  
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard!");
  };
  
  return (
    <div className="bg-white rounded-lg shadow mb-6">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-6 flex items-center justify-between hover:bg-gray-50"
      >
        <h2 className="text-lg font-bold">LLM Payload (Debug)</h2>
        <span>{isExpanded ? "▼" : "▶"}</span>
      </button>
      
      {isExpanded && (
        <div className="p-6 pt-0">
          {isLoading && <p>Loading payload...</p>}
          
          {payload && (
            <>
              <p className="text-sm text-gray-600 mb-4">
                This shows exactly what the LLM saw when classifying this PR.
                Use this to debug misclassifications.
              </p>
              
              {/* PR Context */}
              <div className="mb-4">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-medium">PR Context</h3>
                  <button
                    onClick={() => copyToClipboard(payload.pr_context)}
                    className="text-sm text-blue-600 hover:underline"
                  >
                    Copy Context
                  </button>
                </div>
                <pre className="bg-gray-50 p-4 rounded border border-gray-200 text-xs overflow-x-auto max-h-96 overflow-y-auto">
                  {payload.pr_context}
                </pre>
              </div>
              
              {/* Full Prompt */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-medium">Full Prompt (Context + Template)</h3>
                  <button
                    onClick={() => copyToClipboard(payload.full_prompt)}
                    className="text-sm text-blue-600 hover:underline"
                  >
                    Copy Full Prompt
                  </button>
                </div>
                <pre className="bg-gray-50 p-4 rounded border border-gray-200 text-xs overflow-x-auto max-h-96 overflow-y-auto">
                  {payload.full_prompt}
                </pre>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
```

### Data Flow

```
User Actions (PRList)
  ↓
1. Select date cutoff (default: 3 months ago)
2. Select classification filters (onboarding_suitability, difficulty, etc.)
3. Choose sort order (asc = chronological)
  ↓
React Query → GET /api/prs?cutoff_date=...&onboarding_suitability=...&sort_order=asc
  ↓
FastAPI Route (explorer/routes.py)
  ↓
Query pull_requests 
  LEFT JOIN classifications ON pull_requests.id = classifications.pr_id
  WHERE merged_at >= cutoff_date
    AND classifications.onboarding_suitability = ...
  ORDER BY merged_at ASC
  ↓
Return paginated results
  ↓
Render table with classification columns + favorite stars
  ↓
User clicks row → Navigate to PR detail
  ↓
PRDetail loads → Shows classification card + LLM payload (collapsible)
  ↓
User expands LLM payload → GET /api/prs/{repo}/{pr}/llm_payload
  ↓
Backend reconstructs context + prompt using build_pr_context()
  ↓
Display in copyable code blocks
  ↓
User clicks favorite star → POST /api/prs/{repo}/{pr}/favorite
  ↓
Toggle is_favorite in database → Return updated PR
  ↓
UI updates (star fills in)
```

## Implementation Plan

### Phase 1: Database Schema (30 minutes)

1. Create migration script in `setup/`
2. Add `is_favorite` column with default FALSE
3. Add indexes for `is_favorite` and `merged_at`
4. Test migration on development database
5. Document migration in setup/README.md

**Deliverable:** Database ready for favorite functionality

### Phase 2: Backend - Basic Filtering (2-3 hours)

1. Extend `/api/prs` endpoint with new query parameters:
   - `cutoff_date`, `sort_order`, `is_favorite`
2. Add classification filters (requires JOIN with classifications table)
3. Update Supabase query builder to handle filters
4. Add tests for filtering logic
5. Test with curl/Postman

**Deliverable:** API returns filtered, sorted PRs

### Phase 3: Backend - LLM Payload & Favorites (1-2 hours)

1. Implement `/api/prs/{repo}/{pr}/llm_payload` endpoint
   - Import `build_pr_context` and `CLASSIFICATION_PROMPT`
   - Reconstruct payload from PR data
2. Implement `/api/prs/{repo}/{pr}/favorite` endpoint (POST)
3. Implement `/api/prs/favorites` endpoint (GET)
4. Add tests for new endpoints

**Deliverable:** API supports payload reconstruction and favorites

### Phase 4: Frontend - PRList Enhancements (3-4 hours)

1. Add date picker with default 3 months ago
2. Add sort order toggle (asc/desc)
3. Add classification filter dropdowns (4 filters)
4. Add "Favorites Only" checkbox
5. Add classification columns to table
6. Add favorite star icon to each row
7. Wire up favorite toggle (API call + optimistic update)
8. Update API client (`lib/api.ts`) with new parameters

**Deliverable:** PRList supports full filtering and favorites

### Phase 5: Frontend - PRDetail Enhancements (2-3 hours)

1. Create `ClassificationCard` component
2. Create `LLMPayloadCard` component (collapsible)
3. Reorganize PRDetail layout (title/body → classification → payload → files)
4. Add copy-to-clipboard functionality for payload
5. Style with shadcn/ui components
6. Add loading states and error handling

**Deliverable:** PRDetail shows classification + LLM payload

### Phase 6: Polish & Testing (2-3 hours)

1. Add loading states for all new features
2. Add error handling (e.g., no classification available)
3. Improve responsive design for filters
4. Add tooltips/help text for filters
5. Test full workflow end-to-end
6. Fix any bugs or UI issues

**Deliverable:** Polished, production-ready onboarding workflow

## Success Criteria

1. Can select a cutoff date (default 3 months ago) and see only PRs after that date
2. Can filter PRs by onboarding suitability, difficulty, task clarity, reproducibility
3. PRs display in chronological order (ascending by merged_at)
4. Can mark PRs as favorites and see favorites persist across sessions
5. PR detail page shows classification recommendation prominently
6. Can view and copy the exact LLM payload used for classification
7. Filtering is performant (< 2 seconds for any filter combination)
8. UI is intuitive and matches existing Explorer design language

## Open Questions & Future Work

### Near-term Questions

1. **Multiple classifications**: If a PR is re-classified, should we show version history?
   - For now: show latest classification only
   
2. **Classification missing**: What if a PR is enriched but not classified?
   - Show "Not Classified" badge
   - Filter should exclude these by default
   
3. **Date picker UX**: Should we add quick presets alongside calendar?
   - Defer to later iteration if there's demand

### Future Enhancements

1. **Issue generation**: Generate training prompts from favorited PRs
   - Challenge: most PRs don't have originating issues
   - Need separate design for issue prompt generation
   
2. **Bulk operations**: Select multiple PRs and favorite/unfavorite in batch
   
3. **Training set export**: Export favorites to structured format (JSON/YAML)
   - Include PR data, classification, and generated issue prompt
   
4. **Multi-user favorites**: Per-user favorite lists
   - Requires user authentication
   - Add `user_id` column to favorites table
   
5. **Advanced filters**: Filter by categories, concepts taught, prerequisites
   - More complex UI (multi-select dropdowns)
   
6. **Filter presets**: Save commonly-used filter combinations
   - "Excellent Easy PRs for Frontend"
   - "Medium Backend PRs with High Clarity"

## Technical Notes

### Performance Considerations

- **Filtering classified PRs**: Requires JOIN between `pull_requests` and `classifications`
  - Most PRs should be classified (if classification pipeline is complete)
  - Index on `classifications.pr_id` for efficient JOIN
  
- **Date filtering**: Index on `merged_at` makes this fast
  
- **Favorite queries**: Index on `is_favorite` for "favorites only" filter

### Error Handling

- **No classification**: Show "Not Classified" in table, hide classification card in detail view
- **LLM payload reconstruction fails**: Show error message in collapsible section
- **Favorite toggle fails**: Show error toast, revert optimistic update

### Migration Path

For existing PRs in database:
1. Run schema migration (adds `is_favorite` column, defaults to FALSE)
2. No data migration needed (all PRs start unfavorited)
3. Classifications table unchanged (already exists)

### Copy-to-Clipboard UX

Use browser Clipboard API:
```tsx
const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard!");
  } catch (err) {
    toast.error("Failed to copy");
  }
};
```

Fallback for older browsers: use `document.execCommand('copy')` or show "Copy failed" message.

---

## Next Steps

1. Review and approve design document
2. Run database migration (Phase 1)
3. Implement backend endpoints (Phases 2-3)
4. Build frontend components (Phases 4-5)
5. Polish and test (Phase 6)
6. Deploy and test with real onboarding workflow
7. Gather feedback and iterate

