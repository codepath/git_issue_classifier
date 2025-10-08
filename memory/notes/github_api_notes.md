# GitHub API Notes: Fetching Pull Requests for Classification

## Recommended Sequence of API Calls

### Overview
To fully classify a merged pull request, you'll need **1-3 API requests per PR**:
1. Get PR files/diffs
2. Get linked issue details (if exists)
3. Get linked issue comments (if exists)

Plus **1 initial request** to list all PRs.

**Minimal workflow:** Just 1 request per PR:
- List PRs already has: title, body, labels, merged_at, user, branches
- Files endpoint adds: diffs and change metrics

**With linked issues:** Up to 3 requests per PR when issues are referenced

---

## Complete Workflow

### Step 1: List All Pull Requests (Index)

```bash
GET /repos/{owner}/{repo}/pulls?state=closed&sort=created&direction=desc&per_page=100&page=1
```

**Headers:**
```
Accept: application/vnd.github+json
Authorization: Bearer {GITHUB_TOKEN}
X-GitHub-Api-Version: 2022-11-28
```

**Parameters:**
- `state`: `closed` - Get closed PRs (includes both merged and not merged)
- `sort`: `created` - Sort by creation date (most reliable for pagination)
- `direction`: `desc` - Newest first
- `per_page`: `100` - Results per page (max 100, default 30)
- `page`: `1` - Page number (starts at 1)

**Returns:** Array of PR objects (80 fields each)

**Filter client-side:**
```python
merged_prs = [pr for pr in prs if pr['merged_at'] is not None]
```

**Pagination:** See [Pagination Section](#pagination) below.

---

### Step 2: Get Changed Files with Diffs

```bash
GET /repos/{owner}/{repo}/pulls/{pr_number}/files?per_page=100&page=1
```

**Returns:** Array of file objects, each containing:
```json
{
  "filename": "path/to/file.rb",
  "status": "modified",
  "additions": 10,
  "deletions": 5,
  "changes": 15,
  "patch": "@@ -149,7 +149,7 @@ def method_name\n  context\n- old line\n+ new line\n  context"
}
```

**The `patch` field** contains:
- The diff in unified format
- 3 lines of context before and after changes (default)
- Line numbers
- Method/function signatures

**Pagination:** May be needed for PRs with many files (>100).

---

### Step 3: Parse PR Body for Linked Issues

**No API call - Just string parsing:**

```python
import re

def extract_linked_issues(pr_body):
    """Extract issue numbers from PR body."""
    pattern = r'(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s+#(\d+)'
    matches = re.findall(pattern, pr_body or "", re.IGNORECASE)
    return [int(m) for m in matches]

# Example:
# pr['body'] = "Fixes #123 and closes #456"
# Returns: [123, 456]
```

**Common keywords:**
- `Fixes #123`
- `Closes #456`
- `Resolves #789`
- `Fix #123`
- `Close #456`

---

### Step 4: Get Linked Issue Details

```bash
GET /repos/{owner}/{repo}/issues/{issue_number}
```

**Returns:** Issue object with:
- `number` - Issue number
- `title` - Issue title
- `body` - Issue description
- `state` - `open` or `closed`
- `labels` - Array of labels
- `created_at`, `closed_at` - Timestamps
- `comments` - Comment count

**Skip if:** No linked issues found in step 3.

---

### Step 5: Get Linked Issue Comments

```bash
GET /repos/{owner}/{repo}/issues/{issue_number}/comments?per_page=100&page=1
```

**Returns:** Array of comment objects (same format as PR comments)

**Pagination:** May be needed for issues with many comments (>100).

**Skip if:** No linked issues or issue has 0 comments.

---

## Pagination

GitHub REST API uses **page numbers** for pagination. For bulk fetching (where missing a few items is OK), just increment the page number until you get an empty response.

### Simple Pagination

```python
def fetch_prs_bulk(owner, repo, headers, max_pages=10):
    """
    Fetch PRs in bulk. Simple pagination - doesn't handle edge cases.
    Perfect for bulk analysis where missing a few PRs is acceptable.
    """
    all_prs = []
    
    for page in range(1, max_pages + 1):
        params = {
            'state': 'closed',
            'sort': 'created',
            'direction': 'desc',
            'per_page': 100,
            'page': page
        }
        
        response = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers=headers,
            params=params
        )
        prs = response.json()
        
        if not prs:  # No more PRs
            break
            
        all_prs.extend(prs)
    
    # Filter for merged PRs
    merged_prs = [pr for pr in all_prs if pr['merged_at'] is not None]
    return merged_prs
```

**Usage:**
```python
# Fetch up to 1,000 PRs (10 pages × 100 per page)
prs = fetch_prs_bulk("owner", "repo", headers, max_pages=10)
print(f"Fetched {len(prs)} merged PRs")
```

### Pagination Limits

| Parameter | Value | Notes |
|-----------|-------|-------|
| `per_page` | Max 100 | Always use 100 for efficiency |
| `page` | Starts at 1 | Increment until empty response |

**Pro tip:** Set `max_pages` based on how many PRs you need:
- 500 PRs → `max_pages=5`
- 1,000 PRs → `max_pages=10`
- 5,000 PRs → `max_pages=50`

---

## Rate Limits

### Authenticated Requests
- **5,000 requests per hour**
- Check remaining: `X-RateLimit-Remaining` header
- Resets at: `X-RateLimit-Reset` header (Unix timestamp)

### Rate Limit Headers in Response

```
X-RateLimit-Limit: 5000
X-RateLimit-Remaining: 4999
X-RateLimit-Reset: 1633024800
X-RateLimit-Used: 1
```

### Estimate: 100 PRs

**Recommended workflow:**
- 1 request: List PRs (initial)
- 100 requests: PR files/diffs
- 50 requests: Linked issues (assume 50% have linked issues)
- 50 requests: Linked issue comments
- **Total: ~201 requests**

**Minimal workflow (no linked issues):**
- 1 request: List PRs (initial)
- 100 requests: PR files/diffs
- **Total: ~101 requests**

**Time to rate limit:** 
- Recommended: ~24 batches of 100 PRs = **2,400 PRs per hour**
- Minimal: ~49 batches of 100 PRs = **4,900 PRs per hour**

---

## API Endpoint Summary

| Purpose | Endpoint | Pagination | Notes |
|---------|----------|------------|-------|
| List PRs | `GET /repos/{owner}/{repo}/pulls` | ✅ Yes | Index endpoint |
| PR files | `GET /repos/{owner}/{repo}/pulls/{number}/files` | ✅ Yes | Gets diffs |
| Issue details | `GET /repos/{owner}/{repo}/issues/{number}` | ❌ No | Linked issues |
| Issue comments | `GET /repos/{owner}/{repo}/issues/{number}/comments` | ✅ Yes | Discussion on issues |

---

## Best Practices

### 1. Always Set Headers

```python
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28"
}
```

### 2. Handle Rate Limits

```python
def make_request_with_retry(url, headers):
    response = requests.get(url, headers=headers)
    
    if response.status_code == 403:
        reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
        wait_seconds = reset_time - time.time() + 1
        
        if wait_seconds > 0:
            print(f"Rate limited. Waiting {wait_seconds}s...")
            time.sleep(wait_seconds)
            return make_request_with_retry(url, headers)
    
    response.raise_for_status()
    return response.json()
```

### 3. Filter Early

```python
# Filter for merged PRs immediately
merged_prs = [pr for pr in prs if pr['merged_at'] is not None]

# Skip PRs with no body (unlikely to have linked issues)
if not pr['body']:
    skip_linked_issue_fetch()
```

### 4. Batch When Possible

```python
# Fetch list with max per_page
params = {'per_page': 100}  # Not 30

# This reduces pagination requests
```

### 5. Cache Results

```python
# Store fetched data to avoid re-fetching
# Use PR number as key
cache = {}
cache[pr_number] = pr_data
```

---

## Error Handling

### Common HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process data |
| 304 | Not Modified | Use cached data |
| 401 | Unauthorized | Check token |
| 403 | Forbidden | Check rate limit or permissions |
| 404 | Not Found | PR/issue doesn't exist |
| 422 | Validation Error | Check parameters |

### Example Error Handler

```python
def fetch_pr_safely(owner, repo, pr_number, headers):
    """Fetch PR with error handling."""
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 404:
            print(f"PR #{pr_number} not found")
            return None
        
        if response.status_code == 403:
            remaining = response.headers.get('X-RateLimit-Remaining')
            if remaining == '0':
                raise Exception("Rate limit exceeded")
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching PR #{pr_number}: {e}")
        return None
```

---

## Example: Complete Fetch Function

```python
import os
import re
import requests
from typing import Dict, List, Optional

def fetch_pr_complete_data(owner: str, repo: str, pr_number: int, pr_from_list: Dict) -> Dict:
    """
    Fetch complete PR data including linked issues.
    
    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        pr_from_list: PR object from the list endpoint (has title, body, labels, etc.)
    
    Returns dict with:
        - pr: PR data from list endpoint (title, body, labels, etc.)
        - files: Changed files with diffs
        - linked_issue: Linked issue details (if exists)
        - issue_comments: Linked issue comments (if exists)
    """
    token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    
    result = {
        "pr": pr_from_list,  # Use data from list endpoint
        "files": [],
        "linked_issue": None,
        "issue_comments": []
    }
    
    # Step 1: Get changed files with diffs
    files_url = f"{base_url}/pulls/{pr_number}/files"
    files = requests.get(files_url, headers=headers).json()
    result["files"] = files
    
    # Step 2: Parse for linked issues
    body = pr_from_list.get('body', '')
    pattern = r'(?:fix|fixes|close|closes|resolve|resolves)\s+#(\d+)'
    issue_numbers = re.findall(pattern, body, re.IGNORECASE)
    
    if issue_numbers:
        issue_number = int(issue_numbers[0])  # Take first linked issue
        
        # Step 3: Get linked issue
        issue_url = f"{base_url}/issues/{issue_number}"
        issue = requests.get(issue_url, headers=headers).json()
        result["linked_issue"] = issue
        
        # Step 4: Get linked issue comments
        issue_comments_url = f"{base_url}/issues/{issue_number}/comments"
        issue_comments = requests.get(issue_comments_url, headers=headers).json()
        result["issue_comments"] = issue_comments
    
    return result
```

---

## Quick Reference Card

```bash
# Environment
export GITHUB_TOKEN="your_token_here"

# List PRs (has title, body, labels, merged_at, etc.)
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github+json" \
     "https://api.github.com/repos/owner/repo/pulls?state=closed&per_page=100"

# Get PR files/diffs
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github+json" \
     "https://api.github.com/repos/owner/repo/pulls/123/files"

# Get linked issue (parse issue number from PR body first)
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github+json" \
     "https://api.github.com/repos/owner/repo/issues/456"

# Get linked issue comments
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github+json" \
     "https://api.github.com/repos/owner/repo/issues/456/comments"
```

---

## Supabase Schema

The database uses a **two-phase design** to support resumable enrichment:

```sql
CREATE TABLE pull_requests (
    -- Primary Key
    id BIGSERIAL PRIMARY KEY,
    
    -- Basic Info (from index phase - Phase 1)
    repo TEXT NOT NULL,              -- e.g., "facebook/react"
    pr_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT,                        -- PR description (may contain linked issue refs)
    merged_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL,
    
    -- Enriched Data (from enrichment phase - Phase 2) - NULLABLE
    files JSONB,                      -- Changed files with diffs [{filename, status, additions, deletions, patch}, ...]
    linked_issue JSONB,               -- Issue details {number, title, body, state, created_at, closed_at, ...}
    issue_comments JSONB,             -- Issue comments [{body, created_at, user}, ...]
    
    -- Enrichment Status Tracking
    enrichment_status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'success' | 'failed'
    enrichment_attempted_at TIMESTAMP,
    enrichment_error TEXT,            -- Error message if enrichment failed
    
    -- Classification (from LLM - Phase 3)
    classification JSONB,             -- {difficulty, categories, learning_value, estimated_time, concepts, ...}
    classified_at TIMESTAMP,
    
    -- Constraints
    UNIQUE(repo, pr_number)
);

-- Indexes for query performance
CREATE INDEX idx_enrichment_status ON pull_requests(enrichment_status);
CREATE INDEX idx_repo ON pull_requests(repo);
CREATE INDEX idx_merged_at ON pull_requests(merged_at DESC);
```

### Field Explanations

**Basic fields (Phase 1 - Index):**
- Fetched from `GET /repos/{owner}/{repo}/pulls?state=closed` endpoint
- Cheap: 1 API call for 100 PRs
- Rarely fails
- Stored immediately after index phase

**Enriched fields (Phase 2 - Enrichment):**
- `files`: From `GET /repos/{owner}/{repo}/pulls/{number}/files`
- `linked_issue`: From `GET /repos/{owner}/{repo}/issues/{issue_number}` (parsed from PR body)
- `issue_comments`: From `GET /repos/{owner}/{repo}/issues/{issue_number}/comments`
- All nullable - may be absent if PR has no linked issue
- Expensive: 1-3 API calls per PR

**Status tracking:**
- `enrichment_status`: Track which PRs need enrichment/re-enrichment
- Query for `WHERE enrichment_status IN ('pending', 'failed')` to find work to do
- Enables resumable workflow - don't lose progress on crashes

**Classification:**
- Added after enrichment succeeds
- Only classify PRs where `enrichment_status = 'success'`

### Query Examples

```sql
-- Get PRs needing enrichment
SELECT id, repo, pr_number, body
FROM pull_requests
WHERE enrichment_status IN ('pending', 'failed')
ORDER BY merged_at DESC
LIMIT 100;

-- Get successfully enriched PRs ready for classification
SELECT id, repo, pr_number, files, linked_issue
FROM pull_requests
WHERE enrichment_status = 'success'
  AND classification IS NULL
LIMIT 50;

-- Get enrichment failure stats
SELECT enrichment_error, COUNT(*)
FROM pull_requests
WHERE enrichment_status = 'failed'
GROUP BY enrichment_error;
```

---

## Additional Resources

- [GitHub REST API Documentation](https://docs.github.com/en/rest)
- [Rate Limiting](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting)
- [Pagination](https://docs.github.com/en/rest/guides/using-pagination-in-the-rest-api)
- [Pull Requests API](https://docs.github.com/en/rest/pulls/pulls)
- [Issues API](https://docs.github.com/en/rest/issues/issues)
