# Milestone 2.3: Default Prompt Endpoint - Implementation Summary

**Status:** ✅ Complete  
**Date:** October 11, 2025

## What Was Implemented

### 1. New API Endpoint: `GET /api/prompts/issue-generation`

**Location:** `backend/routes.py` (lines 352-377)

**Endpoint:**
```
GET /api/prompts/issue-generation
```

**Purpose:** Provides the default issue generation prompt template for the frontend modal.

**Response Format:**
```json
{
  "prompt_template": "You are helping create training exercises..."
}
```

**Behavior:**
- Returns the `ISSUE_GENERATION_PROMPT` constant from `classifier/prompt_template.py`
- No parameters required (simple GET request)
- Template contains `{pr_context}` and `{classification_info}` placeholders
- Used by frontend to populate the editable prompt template textarea in the modal

### 2. Import Update

**Location:** `backend/routes.py` (line 16)

Added import:
```python
from classifier.prompt_template import CLASSIFICATION_PROMPT, ISSUE_GENERATION_PROMPT
```

### 3. Test Coverage

**Location:** `tests/test_explorer_api.py` (lines 1010-1057)

Added 2 tests to `TestIssueGenerationPrompt` class:

1. **`test_get_issue_generation_prompt_success`** - Returns prompt template with all required sections
2. **`test_get_issue_generation_prompt_structure`** - Validates prompt structure and key elements

**Test Results:**
```bash
tests/test_explorer_api.py::TestIssueGenerationPrompt::test_get_issue_generation_prompt_success PASSED
tests/test_explorer_api.py::TestIssueGenerationPrompt::test_get_issue_generation_prompt_structure PASSED
```

Both tests pass ✅

## Implementation Details

### Endpoint Signature

```python
@router.get("/prompts/issue-generation")
def get_issue_generation_prompt():
```

### Response Schema

**Success (200):**
```json
{
  "prompt_template": "string (complete issue generation prompt template)"
}
```

**Error (500):**
```json
{
  "detail": "Failed to retrieve prompt template: {error_message}"
}
```

Note: 500 errors are unlikely for this endpoint since it just returns a constant.

### Example Response

```json
{
  "prompt_template": "You are helping create training exercises for developers learning a new codebase.\n\nYour task is to analyze a pull request and generate a clear, actionable GitHub issue that a student could use to implement the same change independently.\n\nCONTEXT:\nYou will receive:\n- The pull request title, description, and code changes\n- Any linked issue and discussion (if available)\n- Classification information (difficulty, concepts, etc.)\n\nYOUR TASK:\nGenerate a markdown-formatted issue that includes:\n\n1. **Issue Title**: Clear, specific title describing the problem/task\n   - For bugs: \"Description of broken behavior\"\n   - For features: \"Add [feature description]\"\n   - For refactors: \"Refactor [component] to [improvement]\"\n\n2. **Motivation**: 1-2 paragraphs explaining WHY this change matters\n   ...\n\n[Full prompt continues with all sections]\n\n{pr_context}\n\n---\n\nCLASSIFICATION INFO:\n{classification_info}\n\n---\n\nGenerate the issue in markdown format:"
}
```

## Design Decisions

### 1. Why a Separate Endpoint?

**Decision:** Create dedicated endpoint instead of embedding in PR detail  
**Reason:**
- Cleaner separation of concerns
- Can be cached/loaded independently
- Easier to test
- Follows REST principles (resource-oriented)

### 2. Error Handling

**Decision:** Wrap in try-except even though it's simple  
**Reason:** 
- Consistency with other endpoints
- Graceful handling if prompt constant doesn't exist
- Proper logging

### 3. No Caching Headers

**Decision:** No cache control headers added  
**Reason:**
- Prompt template rarely changes
- HTTP caching handled by FastAPI/browser defaults
- Can add later if needed

## Integration Points

### Used By (Future Milestones):
- **Milestone 5.8: IssueGenerationModal (Prompt Template Tab)**
  - Fetches default prompt on modal open
  - Populates editable textarea
  - User can customize before generation

### Uses:
- **`classifier.prompt_template.ISSUE_GENERATION_PROMPT`** - The prompt constant

## Manual Verification Instructions

### Simple curl Test

```bash
# Start server
cd /Users/tim/w/git_issue_classifier
uv run uvicorn backend.server:app --reload

# In another terminal:
curl http://localhost:8000/api/prompts/issue-generation | jq

# Expected: JSON with "prompt_template" key containing long string
```

### Verify Prompt Content

```bash
# Extract just the prompt template
curl -s http://localhost:8000/api/prompts/issue-generation | jq -r '.prompt_template'

# Should show the full prompt with:
# - Section headers (Motivation, Current Behavior, etc.)
# - Placeholders: {pr_context} and {classification_info}
# - Guidelines for different difficulty levels
```

### Check Placeholders

```bash
# Verify placeholders exist
curl -s http://localhost:8000/api/prompts/issue-generation | jq -r '.prompt_template' | grep -o '{[^}]*}'

# Should output:
# {pr_context}
# {classification_info}
```

## Checklist

- [x] Add import for `ISSUE_GENERATION_PROMPT`
- [x] Create `GET /api/prompts/issue-generation` endpoint
- [x] Import and return `ISSUE_GENERATION_PROMPT` from `prompt_template`
- [x] Return JSON with `prompt_template` field
- [x] Add comprehensive docstring to endpoint
- [x] Add 2 simple tests covering success and structure validation
- [x] Verify tests pass
- [x] No linting errors

## Files Modified

- ✅ `backend/routes.py` - Added endpoint and import
- ✅ `tests/test_explorer_api.py` - Added 2 test cases
- ✅ `MILESTONE_2.3_SUMMARY.md` - This documentation

**No linting errors** ✅

## Next Milestone

**Phase 3: Backend - Issue Generation**

Next up are the core issue generation endpoints:

- **Milestone 3.1: Generate Issue Endpoint (Core Logic)**
- **Milestone 3.2: Generate Issue Endpoint (LLM Integration)**
- **Milestone 3.3: Generate Issue Endpoint (Database Persistence)**
- **Milestone 3.4: Get Generated Issue Endpoint**

These will tie together the LLM client (2.1), PR context (2.2), and prompt template (2.3) to actually generate issues!

---

## Notes

- Endpoint is **stateless** and **cacheable** (returns constant)
- No authentication/authorization (consistent with other read endpoints)
- Prompt template is **read-only** on backend (edited per-generation on frontend)
- Very simple implementation - just returns a constant, but properly structured for REST API

