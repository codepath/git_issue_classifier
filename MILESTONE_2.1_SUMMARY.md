# Milestone 2.1: LLM Client Extension - Implementation Summary

**Status:** ✅ Complete  
**Date:** October 11, 2025

## What Was Implemented

### 1. New Method: `LLMClient.generate_issue()`

**Location:** `classifier/llm_client.py` (lines 128-178)

**Signature:**
```python
def generate_issue(self, prompt: str) -> str
```

**Behavior:**
- Takes a complete prompt string (including PR context and template)
- Sends it to LLM using OpenAI SDK (same as `send_prompt()`)
- Returns plain markdown text (no JSON parsing)
- Returns empty string if LLM returns empty response
- Raises exceptions on API failures
- Logs token usage for monitoring
- **No retry logic** (per requirements)
- Sync implementation (consistent with existing codebase)

### 2. Test Coverage

**Location:** `tests/test_classifier.py` (lines 144-231)

Added 3 simple tests to `TestLLMClient` class:

1. **`test_generate_issue_success`** - Happy path with valid markdown response
2. **`test_generate_issue_empty_response`** - LLM returns empty string (handled gracefully)
3. **`test_generate_issue_api_error`** - API failure raises exception

**Test Results:**
```
tests/test_classifier.py::TestLLMClient::test_generate_issue_success PASSED
tests/test_classifier.py::TestLLMClient::test_generate_issue_empty_response PASSED
tests/test_classifier.py::TestLLMClient::test_generate_issue_api_error PASSED
```

All 3 tests pass ✅

## Design Decisions Made

### 1. No Retry Logic
**Decision:** No retry logic in `generate_issue()`  
**Reason:** Per user requirements - keep it simple, let API endpoint handle retries if needed

### 2. Sync vs Async
**Decision:** Keep method synchronous (`def`, not `async def`)  
**Reason:**
- Consistent with existing codebase (all routes are sync)
- FastAPI handles sync functions in threadpool (no event loop blocking)
- No need for async HTTP client changes
- Sufficient for typical usage patterns

### 3. Empty Response Handling
**Decision:** Return empty string without error  
**Reason:** Let caller decide what to do with empty responses

### 4. Error Handling
**Decision:** Raise exceptions on API failures  
**Reason:** Let API endpoint translate to HTTP errors with proper status codes

## Usage Example

```python
from classifier.llm_client import LLMClient
from utils.config_loader import load_config

config = load_config()

# Initialize client
client = LLMClient(
    provider=config.credentials.llm_provider,
    model=config.credentials.llm_model,
    api_key=config.credentials.anthropic_api_key  # or openai_api_key
)

# Build prompt (will come from prompt_template.py in Milestone 1.2)
prompt = """You are helping create training exercises...

PR Context:
{pr_context}

Classification Info:
{classification_info}

Generate the issue in markdown format:"""

# Generate issue
try:
    markdown = client.generate_issue(prompt)
    print(f"Generated {len(markdown)} chars of markdown")
except Exception as e:
    print(f"Failed to generate issue: {e}")
```

## Integration Points

### Milestone 1.2: Issue Generation Prompt Template
- Will provide `ISSUE_GENERATION_PROMPT` constant
- Template will have `{pr_context}` and `{classification_info}` placeholders
- Caller will format template before passing to `generate_issue()`

### Milestone 3.2: Generate Issue Endpoint
- Will call `generate_issue()` with filled prompt
- Will handle exceptions and return appropriate HTTP status codes
- Will save markdown to database

## Manual Integration Test Instructions

Once Milestone 1.2 (prompt template) is complete:

1. Ensure API key is set in `.env`:
   ```bash
   ANTHROPIC_API_KEY=your_key_here
   # or
   OPENAI_API_KEY=your_key_here
   ```

2. Test with a real PR:
   ```python
   from classifier.llm_client import LLMClient
   from classifier.context_builder import build_pr_context
   from classifier.prompt_template import ISSUE_GENERATION_PROMPT
   from storage.supabase_client import SupabaseClient
   from utils.config_loader import load_config
   
   config = load_config()
   
   # Fetch a PR
   supabase = SupabaseClient(config.credentials.supabase_url, config.credentials.supabase_key)
   pr = supabase.get_pr_by_number("facebook/react", 12345)
   
   # Build context
   pr_context = build_pr_context(pr)
   classification_info = "Difficulty: easy\n..."  # Format from PR classification
   
   # Fill template
   prompt = ISSUE_GENERATION_PROMPT.format(
       pr_context=pr_context,
       classification_info=classification_info
   )
   
   # Generate issue
   client = LLMClient(
       provider=config.credentials.llm_provider,
       model=config.credentials.llm_model,
       api_key=config.credentials.anthropic_api_key
   )
   
   markdown = client.generate_issue(prompt)
   print(markdown)
   ```

3. Verify output:
   - Should be valid markdown
   - Should include sections: Motivation, Current Behavior, Expected Behavior, Verification
   - Should be appropriate length (not too short, not too long)

## Checklist

- [x] Add `generate_issue()` method to `classifier/llm_client.py`
- [x] Accept prompt string, return plain markdown text (no JSON parsing)
- [x] Reuse existing error handling pattern from `send_prompt()`
- [x] Handle empty responses gracefully (return empty string)
- [x] Handle LLM errors with descriptive exceptions
- [x] Add 3 basic tests covering success, empty response, and API errors
- [x] Verify tests pass
- [x] No linting errors

## Next Milestone

**Milestone 2.2: PR Context Endpoint**  
Create `GET /api/prs/{repo}/{pr_number}/context` endpoint to fetch PR context for modal display.

