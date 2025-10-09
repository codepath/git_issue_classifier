# GitLab API Notes: Fetching Merge Requests for Classification

## Recommended Sequence of API Calls

### Overview
To fully classify a merged merge request, you'll need **2-3 API requests per MR**:
1. Get MR diffs/changes
2. Get linked issues (**always call** - returns full issue objects!)
3. Get linked issue notes/comments (if issue exists)

Plus **1 initial request** to list all MRs.

**Two-Phase Approach:**

**Phase 1 - Index (1 request total):**
- List MRs: title, description, labels, merged_at, author, branches
- Parse description for `has_linked_issue_hint` (no API call)
- Store hint for prioritization

**Phase 2 - Enrichment (2-3 requests per MR):**
- Get diffs: 1 request
- Get linked issues via `/closes_issues`: 1 request (always!)
- Get issue notes: 1 request (only if issues exist)

**Why always call `/closes_issues`?**
- Returns full issue objects (no separate detail fetch needed)
- Works for cross-project issues
- 100% accurate (database-backed)
- Returns empty array if no issues
- GitLab's rate limit (2000/min) makes this feasible

---

## Complete Workflow

### Step 1: List All Merge Requests (Index)

```bash
GET /projects/:id/merge_requests?state=merged&order_by=created_at&sort=desc&per_page=100&page=1
```

**Headers:**
```
Accept: application/json
PRIVATE-TOKEN: {GITLAB_TOKEN}
```

**Parameters:**
- `state`: `merged` - Get merged MRs only (also: `opened`, `closed`, `all`)
- `order_by`: `created_at` - Sort by creation date (also: `updated_at`, `merged_at`, `title`)
- `sort`: `desc` - Newest first (or `asc`)
- `per_page`: `100` - Results per page (max 100, default 20)
- `page`: `1` - Page number (starts at 1)

**Project ID Format:**
- Numeric ID: `278964`
- **OR** URL-encoded path: `gitlab-org%2Fgitlab` (encode `gitlab-org/gitlab`)

**Returns:** Array of MR objects with ~60 fields each including:
- `id`, `iid` (internal ID)
- `title`, `description`
- `state` - `opened`, `closed`, `merged`
- `merged_at` - Timestamp when merged (null if not merged)
- `closed_at` - Timestamp when closed
- `created_at`, `updated_at`
- `labels` - Array of label names
- `author`, `assignees`, `reviewers`
- `source_branch`, `target_branch`
- `web_url`

**State Filter Behavior:**
- `state=merged` - Returns **ONLY** merged MRs (merged_at is set)
- `state=closed` - Returns closed but **NOT** merged MRs
- `state=opened` - Returns open MRs
- `state=all` - Returns all states (mix of opened, closed, merged)

**Pagination:** See [Pagination Section](#pagination) below.

---

### Step 2: Get Changed Files with Diffs

**Option A: Changes Endpoint (Deprecated but still works)**

```bash
GET /projects/:id/merge_requests/:merge_request_iid/changes
```

**Returns:** MR object + `changes` array with file objects:
```json
{
  "id": 123,
  "title": "...",
  "changes": [
    {
      "old_path": "lib/gitlab/tracking.rb",
      "new_path": "lib/gitlab/tracking.rb",
      "a_mode": "100644",
      "b_mode": "100644",
      "diff": "@@ -149,7 +149,7 @@ def method\n context\n- old line\n+ new line\n context",
      "new_file": false,
      "renamed_file": false,
      "deleted_file": false
    }
  ],
  "overflow": false
}
```

**Option B: Diffs Endpoint (Recommended)**

```bash
GET /projects/:id/merge_requests/:merge_request_iid/diffs?per_page=100&page=1
```

**Returns:** Array of diff objects:
```json
[
  {
    "old_path": "app/models/user.rb",
    "new_path": "app/models/user.rb",
    "a_mode": "100644",
    "b_mode": "100644",
    "diff": "@@ -10,6 +10,8 @@ class User\n+ new line\n",
    "new_file": false,
    "renamed_file": false,
    "deleted_file": false,
    "generated_file": false,
    "collapsed": false,
    "too_large": false
  }
]
```

**The `diff` field** contains:
- Unified diff format
- 3 lines of context before and after changes (default)
- Line numbers in headers (`@@ -10,6 +10,8 @@`)
- Method/function context

**Pagination:** May be needed for MRs with many files (>100).

---

### Step 3: Get Linked Issues (First-Class API!)

**GitLab tracks MR → Issue relationships in the database!**

```bash
GET /projects/:id/merge_requests/:merge_request_iid/closes_issues
```

**Returns:** Array of issue objects (full details):
```json
[
  {
    "iid": 17407,
    "title": "Wednesday 2025-10-08 - broken master",
    "description": "...",
    "state": "closed",
    "labels": ["master-broken", "test"],
    "created_at": "2025-10-08T07:35:00Z",
    "closed_at": "2025-10-08T16:31:45Z",
    "web_url": "https://gitlab.com/gitlab-org/project/-/issues/17407",
    "user_notes_count": 13
  }
]
```

**This endpoint:**
- ✅ Returns **full issue objects** (no need for separate issue detail fetch!)
- ✅ Works for **same-project** issues (`#123`)
- ✅ Works for **cross-project** issues (full URLs)
- ✅ 100% accurate (database-backed, not regex parsing)
- ✅ Returns empty array `[]` if no linked issues

**Skip if:** Empty array returned (no linked issues).

---

### Step 3b (Optional): Parse Description for Hints During Index Phase

**For optimization during index phase only - to prioritize which MRs to enrich:**

```python
import re

def has_linked_issue_hint(mr_description):
    """
    Quick check if description MIGHT have linked issues.
    Used during index phase to prioritize enrichment.
    NOT 100% accurate - always use /closes_issues for actual data!
    """
    if not mr_description:
        return False
    
    description = mr_description.lower()
    
    # Check for closing keywords
    keywords = ['fixes', 'closes', 'resolves', 'fix', 'close', 'resolve']
    if any(keyword in description for keyword in keywords):
        return True
    
    # Check for issue references
    if '#' in description or 'issues/' in description:
        return True
    
    return False

# During index phase:
for mr in mrs:
    mr['has_linked_issue_hint'] = has_linked_issue_hint(mr['description'])
    # Use this to prioritize enrichment, but always call /closes_issues during enrichment!
```

**Why not use this for actual data?**
- ❌ Misses cross-project issues with unusual syntax
- ❌ Regex is brittle and might miss edge cases
- ❌ Description might be edited after MR is merged
- ✅ `/closes_issues` endpoint is the source of truth

**Use cases for hints:**
- Prioritize enrichment (do MRs with hints first)
- Estimate how many MRs have linked issues
- Quick filtering in UI

**Note:** GitLab uses:
- `#123` for same-project issues
- `project/path#123` for cross-project short references
- Full URLs for cross-project: `https://gitlab.com/group/project/-/issues/123`
- `!123` for merge requests (not issues)

---

### Step 4: Get Linked Issue Notes/Comments

**Note:** Step 3's `/closes_issues` endpoint already returns full issue objects including `user_notes_count`, so you don't need a separate issue details fetch! Jump straight to getting notes/comments.

```bash
GET /projects/:project_id/issues/:issue_iid/notes?per_page=100&page=1
```

**Important for cross-project issues:**
- If the issue is in a different project than the MR, use the issue's `project_id` (from the issue object)
- The issue object from `/closes_issues` includes `project_id` field
- For same-project issues, use the MR's project ID

**Returns:** Array of note objects:
```json
[
  {
    "id": 302,
    "body": "This is a comment",
    "author": {
      "id": 1,
      "username": "john_doe",
      "name": "John Doe",
      "state": "active",
      "avatar_url": "...",
      "web_url": "..."
    },
    "created_at": "2023-01-15T10:30:00Z",
    "updated_at": "2023-01-15T10:30:00Z",
    "system": false,
    "noteable_type": "Issue"
  }
]
```

**Note:** 
- `system: true` indicates system-generated notes (status changes, etc.)
- Filter `system: false` for user comments

**Pagination:** May be needed for issues with many comments (>100).

**Skip if:** No linked issues or issue has 0 user_notes_count.

---

## Pagination

GitLab REST API uses **page numbers** for pagination. Headers provide pagination metadata.

### Pagination Headers

Every paginated response includes:

```
x-total: 1234              # Total number of items
x-total-pages: 13          # Total number of pages
x-per-page: 100            # Items per page
x-page: 1                  # Current page
x-next-page: 2             # Next page number (empty if last page)
x-prev-page:               # Previous page number (empty if first page)
```

### Simple Pagination

```python
def fetch_mrs_bulk(project_id, headers, max_pages=10):
    """
    Fetch MRs in bulk. Simple pagination - doesn't handle edge cases.
    Perfect for bulk analysis where missing a few MRs is acceptable.
    """
    all_mrs = []
    base_url = "https://gitlab.com/api/v4"
    
    for page in range(1, max_pages + 1):
        params = {
            'state': 'merged',
            'order_by': 'created_at',
            'sort': 'desc',
            'per_page': 100,
            'page': page
        }
        
        response = requests.get(
            f"{base_url}/projects/{project_id}/merge_requests",
            headers=headers,
            params=params
        )
        
        if response.status_code != 200:
            break
            
        mrs = response.json()
        
        if not mrs:  # No more MRs
            break
            
        all_mrs.extend(mrs)
        
        # Check if there's a next page
        if not response.headers.get('x-next-page'):
            break
    
    return all_mrs
```

**Usage:**
```python
# Fetch up to 1,000 MRs (10 pages × 100 per page)
headers = {
    "Accept": "application/json",
    "PRIVATE-TOKEN": "your_token_here"
}
project_id = "gitlab-org%2Fgitlab"  # URL-encoded
mrs = fetch_mrs_bulk(project_id, headers, max_pages=10)
print(f"Fetched {len(mrs)} merged MRs")
```

### Pagination Limits

| Parameter | Value | Notes |
|-----------|-------|-------|
| `per_page` | Max 100 | Always use 100 for efficiency (default is 20) |
| `page` | Starts at 1 | Increment until empty response or no x-next-page header |

**Pro tip:** Set `max_pages` based on how many MRs you need:
- 500 MRs → `max_pages=5`
- 1,000 MRs → `max_pages=10`
- 5,000 MRs → `max_pages=50`

---

## Rate Limits

### Unauthenticated Requests
- **Very limited** - Not recommended
- GitLab.com: ~5 requests per minute per IP
- Rate limit headers may not be present

### Authenticated Requests (with PRIVATE-TOKEN)
- **2,000 requests per minute** for GitLab.com (varies by plan)
- Self-hosted: Configurable by admin

### Rate Limit Headers in Response

GitLab uses different headers than GitHub:

```
RateLimit-Limit: 2000
RateLimit-Remaining: 1999
RateLimit-Reset: 1696838400
RateLimit-ResetTime: Wed, 09 Oct 2024 12:00:00 GMT
```

**Note:** Rate limit headers may not always be present, especially for unauthenticated requests.

### Estimate: 100 MRs

**Recommended workflow:**
- 1 request: List MRs (initial)
- 100 requests: MR diffs
- 50 requests: Linked issues (assume 50% have linked issues)
- 50 requests: Linked issue notes
- **Total: ~201 requests**

**Minimal workflow (no linked issues):**
- 1 request: List MRs (initial)
- 100 requests: MR diffs
- **Total: ~101 requests**

**Time to rate limit:** 
- Recommended: ~9 batches of 100 MRs = **900 MRs per minute**
- Minimal: ~19 batches of 100 MRs = **1,900 MRs per minute**

**Practically:** Much slower rate (1-2 requests per second) is safer and won't hit rate limits.

---

## API Endpoint Summary

| Purpose | Endpoint | Pagination | Notes |
|---------|----------|------------|-------|
| List MRs | `GET /projects/:id/merge_requests` | ✅ Yes | Index endpoint |
| MR changes | `GET /projects/:id/merge_requests/:iid/changes` | ❌ No | Deprecated, includes full MR object |
| MR diffs | `GET /projects/:id/merge_requests/:iid/diffs` | ✅ Yes | Recommended, diffs only |
| Issue details | `GET /projects/:id/issues/:iid` | ❌ No | Linked issues |
| Issue notes | `GET /projects/:id/issues/:iid/notes` | ✅ Yes | Comments on issues |
| Raw diffs | `GET /projects/:id/merge_requests/:iid/raw_diffs` | ❌ No | Plain text diff output |

---

## Best Practices

### 1. Always Set Headers

```python
headers = {
    "Accept": "application/json",
    "PRIVATE-TOKEN": "your_gitlab_token_here"
}
```

### 2. URL-Encode Project Paths

```python
from urllib.parse import quote

# If using project path (not numeric ID)
project_path = "gitlab-org/gitlab"
project_id = quote(project_path, safe='')  # "gitlab-org%2Fgitlab"
```

### 3. Handle Rate Limits

```python
def make_request_with_retry(url, headers):
    response = requests.get(url, headers=headers)
    
    if response.status_code == 429:  # Too Many Requests
        retry_after = int(response.headers.get('Retry-After', 60))
        print(f"Rate limited. Waiting {retry_after}s...")
        time.sleep(retry_after)
        return make_request_with_retry(url, headers)
    
    response.raise_for_status()
    return response.json()
```

### 4. Filter Early

```python
# Use state=merged to get only merged MRs
params = {'state': 'merged'}

# Skip MRs with no description (unlikely to have linked issues)
if not mr['description']:
    skip_linked_issue_fetch()
```

### 5. Batch When Possible

```python
# Fetch list with max per_page
params = {'per_page': 100}  # Not 20 (default)

# This reduces pagination requests
```

### 6. Check Pagination Headers

```python
# Use x-next-page to know when to stop
if not response.headers.get('x-next-page'):
    break  # No more pages
```

---

## Error Handling

### Common HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process data |
| 304 | Not Modified | Use cached data |
| 401 | Unauthorized | Check token |
| 403 | Forbidden | Check permissions or rate limit |
| 404 | Not Found | MR/issue doesn't exist |
| 422 | Unprocessable Entity | Check parameters |
| 429 | Too Many Requests | Respect rate limit (check Retry-After header) |

### Example Error Handler

```python
def fetch_mr_safely(project_id, mr_iid, headers):
    """Fetch MR with error handling."""
    try:
        url = f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests/{mr_iid}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 404:
            print(f"MR !{mr_iid} not found")
            return None
        
        if response.status_code == 403:
            print(f"Permission denied for MR !{mr_iid}")
            return None
        
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            raise Exception(f"Rate limit exceeded, retry after {retry_after}s")
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching MR !{mr_iid}: {e}")
        return None
```

---

## Example: Complete Fetch Functions

### Phase 1: Index Function

```python
import os
import requests
from typing import Dict, List
from urllib.parse import quote

def has_linked_issue_hint(description: str) -> bool:
    """Quick check if description might have linked issues."""
    if not description:
        return False
    
    desc_lower = description.lower()
    keywords = ['fixes', 'closes', 'resolves', 'fix', 'close', 'resolve']
    
    return any(keyword in desc_lower for keyword in keywords) or '#' in description or 'issues/' in description

def fetch_mrs_index(project_id: str, max_pages: int = 10) -> List[Dict]:
    """
    Fetch MR index with hints about linked issues.
    
    Args:
        project_id: Project ID (numeric) or URL-encoded path
        max_pages: Maximum pages to fetch
    
    Returns list of MR objects with added 'has_linked_issue_hint' field
    """
    token = os.getenv("GITLAB_TOKEN")
    headers = {
        "Accept": "application/json",
        "PRIVATE-TOKEN": token
    }
    
    # URL-encode if needed
    if '/' in str(project_id):
        project_id = quote(str(project_id), safe='')
    
    all_mrs = []
    base_url = f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests"
    
    for page in range(1, max_pages + 1):
        params = {
            'state': 'merged',
            'order_by': 'created_at',
            'sort': 'desc',
            'per_page': 100,
            'page': page
        }
        
        response = requests.get(base_url, headers=headers, params=params)
        if response.status_code != 200:
            break
        
        mrs = response.json()
        if not mrs:
            break
        
        # Add hint field for prioritization
        for mr in mrs:
            mr['has_linked_issue_hint'] = has_linked_issue_hint(mr.get('description', ''))
        
        all_mrs.extend(mrs)
        
        # Check if there's a next page
        if not response.headers.get('x-next-page'):
            break
    
    return all_mrs
```

### Phase 2: Enrichment Function

```python
def fetch_mr_complete_data(project_id: str, mr_iid: int, mr_from_index: Dict) -> Dict:
    """
    Fetch complete MR data including linked issues.
    
    Args:
        project_id: Project ID (numeric) or URL-encoded path
        mr_iid: MR internal ID (iid, not id)
        mr_from_index: MR object from index phase
    
    Returns dict with:
        - mr: MR data from index phase
        - diffs: Changed files with diffs
        - linked_issues: List of linked issue objects (includes cross-project!)
        - issue_notes: Dict mapping issue_iid -> notes array
    """
    token = os.getenv("GITLAB_TOKEN")
    headers = {
        "Accept": "application/json",
        "PRIVATE-TOKEN": token
    }
    
    # URL-encode if needed
    if '/' in str(project_id):
        project_id = quote(str(project_id), safe='')
    
    base_url = f"https://gitlab.com/api/v4/projects/{project_id}"
    
    result = {
        "mr": mr_from_index,
        "diffs": [],
        "linked_issues": [],
        "issue_notes": {}
    }
    
    # Step 1: Get MR diffs
    diffs_url = f"{base_url}/merge_requests/{mr_iid}/diffs"
    response = requests.get(diffs_url, headers=headers, params={'per_page': 100})
    if response.status_code == 200:
        result["diffs"] = response.json()
    
    # Step 2: Get linked issues (ALWAYS call this!)
    closes_url = f"{base_url}/merge_requests/{mr_iid}/closes_issues"
    response = requests.get(closes_url, headers=headers)
    if response.status_code == 200:
        linked_issues = response.json()
        result["linked_issues"] = linked_issues
        
        # Step 3: Get notes for each linked issue
        for issue in linked_issues:
            if issue.get('user_notes_count', 0) > 0:
                # Handle cross-project issues - use the issue's project_id
                issue_project_id = issue.get('project_id', project_id)
                notes_url = f"https://gitlab.com/api/v4/projects/{issue_project_id}/issues/{issue['iid']}/notes"
                
                response = requests.get(notes_url, headers=headers, params={'per_page': 100})
                if response.status_code == 200:
                    all_notes = response.json()
                    # Filter out system-generated notes
                    user_notes = [note for note in all_notes if not note.get('system', False)]
                    result["issue_notes"][issue['iid']] = user_notes
    
    return result
```

---

## Authentication

### Creating a GitLab Personal Access Token

1. Go to: https://gitlab.com/-/profile/personal_access_tokens
2. Click "Add new token"
3. Set:
   - **Name:** "MR Classification Script"
   - **Expiration:** Set an appropriate date
   - **Scopes:** Check `read_api` (sufficient for read-only access)
4. Click "Create personal access token"
5. **Copy the token immediately** (shown only once)

### Using the Token

```bash
export GITLAB_TOKEN="glpat-xxxxxxxxxxxxxxxxxxxx"
```

```python
import os

headers = {
    "Accept": "application/json",
    "PRIVATE-TOKEN": os.getenv("GITLAB_TOKEN")
}
```

### Token Scopes

For this use case, you only need:
- ✅ `read_api` - Read-only access to API

You do NOT need:
- ❌ `api` - Full API access (too broad)
- ❌ `write_repository` - Write access
- ❌ `sudo` - Admin access

---

## Supabase Schema

The database uses a **two-phase design** to support resumable enrichment (same as GitHub):

```sql
CREATE TABLE merge_requests (
    -- Primary Key
    id BIGSERIAL PRIMARY KEY,
    
    -- Basic Info (from index phase - Phase 1)
    repo TEXT NOT NULL,              -- e.g., "gitlab-org/gitlab"
    mr_iid INTEGER NOT NULL,         -- Internal ID (use this for API calls, not 'id')
    mr_id BIGINT NOT NULL,           -- Global ID from GitLab
    title TEXT NOT NULL,
    description TEXT,                 -- MR description (may contain linked issue refs)
    merged_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL,
    
    -- Index Phase Hint (from Phase 1 - for prioritization)
    has_linked_issue_hint BOOLEAN NOT NULL DEFAULT FALSE,  -- Quick hint from description parsing
    
    -- Enriched Data (from enrichment phase - Phase 2) - NULLABLE
    diffs JSONB,                      -- Changed files with diffs [{old_path, new_path, diff, ...}, ...]
    linked_issues JSONB,              -- Array of issue objects (from /closes_issues endpoint)
    issue_notes JSONB,                -- Dict mapping issue_iid -> notes array
    
    -- Enrichment Status Tracking
    enrichment_status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'success' | 'failed'
    enrichment_attempted_at TIMESTAMP,
    enrichment_error TEXT,            -- Error message if enrichment failed
    
    -- Classification (from LLM - Phase 3)
    classification JSONB,             -- {difficulty, categories, learning_value, estimated_time, concepts, ...}
    classified_at TIMESTAMP,
    
    -- Constraints
    UNIQUE(repo, mr_iid)
);

-- Indexes for query performance
CREATE INDEX idx_enrichment_status ON merge_requests(enrichment_status);
CREATE INDEX idx_repo ON merge_requests(repo);
CREATE INDEX idx_merged_at ON merge_requests(merged_at DESC);
CREATE INDEX idx_has_linked_issue_hint ON merge_requests(has_linked_issue_hint) WHERE enrichment_status = 'pending';
```

### Field Explanations

**Basic fields (Phase 1 - Index):**
- Fetched from `GET /projects/:id/merge_requests?state=merged` endpoint
- Cheap: 1 API call for 100 MRs
- Rarely fails
- Stored immediately after index phase
- **Note:** Store both `mr_iid` (internal ID for API calls) and `mr_id` (global ID)

**Index hint (Phase 1 - No API call):**
- `has_linked_issue_hint`: Boolean from parsing description for closing keywords
- Used to prioritize which MRs to enrich first
- Not 100% accurate - actual data comes from Phase 2
- Enables smart work scheduling (enrich MRs with hints first)

**Enriched fields (Phase 2 - Enrichment):**
- `diffs`: From `GET /projects/:id/merge_requests/:iid/diffs`
- `linked_issues`: From `GET /projects/:id/merge_requests/:iid/closes_issues` (ALWAYS call!)
  - Returns full array of issue objects (can be cross-project!)
  - Empty array if no linked issues
  - Already includes all issue details
- `issue_notes`: From `GET /projects/:project_id/issues/:iid/notes` (filtered for user notes)
  - Stored as dict: `{issue_iid: [notes]}`
  - Handles cross-project issues (uses issue's project_id)
- All nullable - populated during enrichment
- Cost: 2-3 API calls per MR (diffs + closes_issues + optional notes)

**Status tracking:**
- `enrichment_status`: Track which MRs need enrichment/re-enrichment
- Query for `WHERE enrichment_status IN ('pending', 'failed')` to find work to do
- Enables resumable workflow - don't lose progress on crashes
- Use with `has_linked_issue_hint` for prioritized enrichment

**Classification:**
- Added after enrichment succeeds
- Only classify MRs where `enrichment_status = 'success'`

### Query Examples

```sql
-- Get MRs needing enrichment (prioritized by hint)
SELECT id, repo, mr_iid, description, has_linked_issue_hint
FROM merge_requests
WHERE enrichment_status IN ('pending', 'failed')
ORDER BY has_linked_issue_hint DESC,  -- MRs with hints first
         merged_at DESC                -- Then by recency
LIMIT 100;

-- Get MRs with hints that need enrichment (high priority)
SELECT id, repo, mr_iid, description
FROM merge_requests
WHERE enrichment_status = 'pending'
  AND has_linked_issue_hint = TRUE
ORDER BY merged_at DESC
LIMIT 50;

-- Get successfully enriched MRs ready for classification
SELECT id, repo, mr_iid, diffs, linked_issues
FROM merge_requests
WHERE enrichment_status = 'success'
  AND classification IS NULL
LIMIT 50;

-- Stats: How accurate were our hints?
SELECT 
    has_linked_issue_hint,
    COUNT(*) as total,
    SUM(CASE WHEN jsonb_array_length(COALESCE(linked_issues, '[]'::jsonb)) > 0 THEN 1 ELSE 0 END) as actually_has_issues
FROM merge_requests
WHERE enrichment_status = 'success'
GROUP BY has_linked_issue_hint;

-- Get enrichment failure stats
SELECT enrichment_error, COUNT(*)
FROM merge_requests
WHERE enrichment_status = 'failed'
GROUP BY enrichment_error;
```

---

## Key Differences from GitHub API

| Feature | GitHub | GitLab |
|---------|--------|--------|
| **Primary identifier** | `number` | `iid` (internal ID) |
| **Project identifier** | `owner/repo` | Numeric ID or URL-encoded path |
| **State filter** | `state=closed` + filter `merged_at` | `state=merged` (direct filter) |
| **Diffs endpoint** | `/pulls/:number/files` | `/merge_requests/:iid/diffs` |
| **Comments** | `/issues/:number/comments` | `/issues/:iid/notes` |
| **System notes** | No system notes | Filter `system: false` |
| **Rate limit** | 5,000/hour | 2,000/minute (GitLab.com) |
| **Auth header** | `Authorization: Bearer TOKEN` | `PRIVATE-TOKEN: TOKEN` |
| **Pagination headers** | `Link` header | `x-total`, `x-next-page`, etc. |

---

## Quick Reference Card

```bash
# Environment
export GITLAB_TOKEN="glpat-xxxxxxxxxxxxxxxxxxxx"

# List MRs (has title, description, labels, merged_at, etc.)
curl -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     -H "Accept: application/json" \
     "https://gitlab.com/api/v4/projects/gitlab-org%2Fgitlab/merge_requests?state=merged&per_page=100"

# Get MR diffs
curl -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     -H "Accept: application/json" \
     "https://gitlab.com/api/v4/projects/gitlab-org%2Fgitlab/merge_requests/123/diffs"

# Get linked issue (parse issue number from MR description first)
curl -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     -H "Accept: application/json" \
     "https://gitlab.com/api/v4/projects/gitlab-org%2Fgitlab/issues/456"

# Get linked issue notes
curl -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     -H "Accept: application/json" \
     "https://gitlab.com/api/v4/projects/gitlab-org%2Fgitlab/issues/456/notes"
```

---

## Additional Resources

- [GitLab REST API Documentation](https://docs.gitlab.com/ee/api/)
- [Merge Requests API](https://docs.gitlab.com/ee/api/merge_requests.html)
- [Issues API](https://docs.gitlab.com/ee/api/issues.html)
- [Notes API](https://docs.gitlab.com/ee/api/notes.html)
- [Rate Limits](https://docs.gitlab.com/ee/user/admin_area/settings/rate_limit_on_raw_endpoints.html)
- [Personal Access Tokens](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html)
- [API Pagination](https://docs.gitlab.com/ee/api/index.html#pagination)

---

## Project: gitlab-org/gitlab

**Project Info:**
- **Name:** GitLab
- **Path:** `gitlab-org/gitlab`
- **Numeric ID:** `278964`
- **URL:** https://gitlab.com/gitlab-org/gitlab
- **API Path (URL-encoded):** `gitlab-org%2Fgitlab`
- **Stars:** ~5,753
- **Forks:** ~11,474
- **Open MRs:** ~2,222

**Example API Calls:**
```bash
# Using URL-encoded path
curl -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://gitlab.com/api/v4/projects/gitlab-org%2Fgitlab/merge_requests?state=merged&per_page=5"

# Using numeric ID (more efficient)
curl -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://gitlab.com/api/v4/projects/278964/merge_requests?state=merged&per_page=5"
```

**Recommendation:** Use numeric ID (278964) for better performance and cleaner URLs.

---

## Summary: Two-Phase Strategy

### Why This Approach Works

**Phase 1 - Index (Fast & Cheap):**
```python
# 1 API call per 100 MRs
mrs = GET /merge_requests?state=merged&per_page=100

# Parse descriptions (no API call)
for mr in mrs:
    mr['has_linked_issue_hint'] = has_linked_issue_hint(mr['description'])
    store_in_db(mr)
```

**Phase 2 - Enrichment (Always Call `/closes_issues`):**
```python
# Always call closes_issues - it's GitLab's source of truth!
diffs = GET /merge_requests/:iid/diffs              # 1 API call
closes_issues = GET /merge_requests/:iid/closes_issues  # 1 API call (ALWAYS!)

# If issues exist, get notes
if closes_issues:
    for issue in closes_issues:
        notes = GET /projects/:project_id/issues/:iid/notes  # 1 per issue
```

### Benefits

✅ **Phase 1 hint enables:**
- Prioritized enrichment (do MRs with hints first)
- Better resource allocation
- User feedback ("X of Y MRs have linked issues")

✅ **Phase 2 always calling `/closes_issues` ensures:**
- 100% accuracy (no false negatives)
- Cross-project issues captured
- No regex brittleness
- Source of truth from GitLab's database

✅ **Combined approach:**
- Fast index (1 request per 100 MRs)
- Accurate enrichment (2-3 requests per MR)
- Smart prioritization (hints guide order)
- Feasible with GitLab's 2000/min rate limit

### Comparison with GitHub

| Aspect | GitHub | GitLab (This Strategy) |
|--------|--------|------------------------|
| **Index hint** | ✅ Parse body | ✅ Parse description |
| **Accuracy of hint** | Good (same-project) | Good (same-project, some cross-project) |
| **Enrichment API** | ❌ Parse + fetch issue | ✅ `/closes_issues` (database-backed!) |
| **Cross-project** | ❌ Not supported | ✅ Fully supported |
| **False negatives** | Unlikely | Impossible (always call API) |
| **API calls per MR** | 0-2 (if has issue) | 2-3 (always check) |
| **Rate limit impact** | Low | Low (2000/min is generous) |

**Verdict:** GitLab's `/closes_issues` endpoint makes this strategy **superior** to GitHub's text-parsing approach, while maintaining the same indexing performance.

