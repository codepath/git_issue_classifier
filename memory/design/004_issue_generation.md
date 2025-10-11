# Issue Generation - Design Document

**Date:** October 11, 2025  
**Status:** Design Phase  
**Purpose:** Generate student-facing issues from selected PRs for onboarding exercises

## Problem Statement

Open Bootstrap helps onboard developers by having them implement historical PRs as training exercises. However, most PRs don't have originating issues, or the issues are too sparse/technical for effective training.

**Current State:**
- PRs are fetched, enriched, and classified
- Users can browse and favorite promising training candidates
- But there's no student-facing issue to give to learners

**What's Needed:**
A system to generate clear, pedagogical issue descriptions from PR context that include:
- **Motivation**: Why this change is needed
- **Current behavior**: How to reproduce the problem/situation
- **Expected behavior**: What should happen after the fix
- **Verification**: How to test that the fix works

## Requirements

### Must Have
1. **On-demand generation**: Generate issue via button click on PR detail page
2. **Markdown format**: Issue content in markdown (easy to copy-paste to GitHub)
3. **Storage persistence**: Store generated issue with PR (2 new columns)
4. **Clear structure**: Issue should include:
   - Title
   - Motivation/context
   - Current behavior with reproduction steps
   - Expected behavior with acceptance criteria
   - Verification instructions
5. **Quality standards**: Follow engineering best practices for issue quality
   - Not overly detailed or elaborate
   - Appropriate level of detail for the difficulty
   - Professional tone
6. **Regeneration**: Ability to regenerate if not satisfactory
7. **UI display**: Show generated issue on PR detail page with copy functionality
8. **Prompt editing**: Allow per-generation prompt template customization for iteration

### Out of Scope
- Version history of generated issues (user can regenerate if needed)
- Automatic hints or solution guidance (students should discover on their own)
- Batch generation (do one-at-a-time for now)
- Manual editing of generated markdown in UI (user can copy and edit externally)
- Global prompt template saving (manual file edits preferred)

## UI Workflow

### Generation Modal Approach

**Rationale:** A modal provides the flexibility to inspect and edit the prompt template before generation, which is essential for iterating on prompt quality.

**User Flow:**

1. **Initial State (PR Detail Page)**:
   - If no issue exists: Show card with "Generate Issue..." button
   - If issue exists: Show rendered markdown with "Copy Issue" and "Regenerate..." buttons

2. **Opening Modal**: Click "Generate Issue..." or "Regenerate..."
   - Opens large centered modal (80% viewport)
   - Shows 3 tabs: PR Context, Prompt Template, Preview

3. **Modal Tabs**:
   - **PR Context**: Read-only textarea showing formatted PR data sent to LLM
   - **Prompt Template**: Editable textarea (starts with default, can customize)
   - **Preview**: Read-only textarea showing complete prompt (template + context filled in)

4. **Generation**: Click "Generate" button in modal footer
   - Shows loading spinner in modal
   - Calls API with custom prompt template (if edited)
   - On success: Switches to result view showing rendered markdown
   - On error: Shows error message, keeps tabs visible

5. **Result View**: After generation
   - Modal shows rendered markdown (no tabs)
   - Footer shows: "Generate Again" | "Copy Issue" | "Save & Close"
   - "Generate Again" → return to tabs (keeps edited prompt)
   - "Save" → close modal, update main page

6. **After Closing**: Back on PR detail page
   - Issue card now shows the generated markdown
   - Automatically saved to database
   - Can copy or regenerate anytime

**Key Decisions:**
- ✅ Prompt edits are per-generation only (not saved globally)
- ✅ PR Context is read-only (for inspection, not editing)
- ✅ Modal is large centered (max-w-5xl, 90vh)
- ✅ Generation happens in modal, saved to DB automatically
- ✅ No token counters (keep UI simple)

### Visual Layout

**PR Detail Page (Before Generation):**
```
┌─────────────────────────────────────────────────┐
│ 📝 Generated Student Issue                     │
│                                                 │
│   No issue has been generated for this PR yet. │
│                                                 │
│   [Generate Issue...]  ← Opens modal           │
└─────────────────────────────────────────────────┘
```

**Modal View - Tabs (Before Generation):**
```
╔═══════════════════════════════════════════════════════════╗
║ Generate Student Issue - PR #123                      [×] ║
╠═══════════════════════════════════════════════════════════╣
║  [PR Context] [Prompt Template] [Preview]  ← Tabs        ║
║  ─────────────────────────────────────────────────────   ║
║                                                           ║
║  ┌─────────────────────────────────────────────────┐    ║
║  │ You are helping create training exercises...    │    ║
║  │                                                  │    ║
║  │ [Large editable textarea for prompt]            │    ║
║  │                                                  │    ║
║  │ {pr_context}                                     │    ║
║  │ {classification_info}                            │    ║
║  └─────────────────────────────────────────────────┘    ║
║                                                           ║
║  [Restore Default Template]                              ║
║                                                           ║
╠═══════════════════════════════════════════════════════════╣
║                                     [Cancel] [Generate]   ║
╚═══════════════════════════════════════════════════════════╝
```

**Modal View - Result (After Generation):**
```
╔═══════════════════════════════════════════════════════════╗
║ Generate Student Issue - PR #123                      [×] ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  ┌─────────────────────────────────────────────────┐    ║
║  │ # Button text overflows container               │    ║
║  │                                                  │    ║
║  │ ## Motivation                                    │    ║
║  │ Users in Japan report that...                    │    ║
║  │                                                  │    ║
║  │ [Rendered markdown with full issue]             │    ║
║  │                                                  │    ║
║  └─────────────────────────────────────────────────┘    ║
║                                                           ║
╠═══════════════════════════════════════════════════════════╣
║      [Generate Again] [Save]        ║
╚═══════════════════════════════════════════════════════════╝
```

**PR Detail Page (After Closing Modal):**
```
┌─────────────────────────────────────────────────────────┐
│ 📝 Generated Student Issue    [Copy] [Regenerate...]   │
│                                                         │
│ ┌───────────────────────────────────────────────────┐  │
│ │ # Button text overflows container                 │  │
│ │                                                    │  │
│ │ ## Motivation                                      │  │
│ │ Users in Japan report that the 'Save Settings'   │  │
│ │ button text is cut off when using the Japanese   │  │
│ │ locale...                                          │  │
│ │                                                    │  │
│ │ [Full rendered markdown]                           │  │
│ └───────────────────────────────────────────────────┘  │
│                                                         │
│ Generated 5 minutes ago                                │
└─────────────────────────────────────────────────────────┘
```

## Technical Design

### Database Schema

Add two columns to the `pull_requests` table:

```sql
-- Add issue generation columns
ALTER TABLE pull_requests 
ADD COLUMN generated_issue TEXT,           -- Markdown text
ADD COLUMN issue_generated_at TIMESTAMP;   -- When it was generated

-- Index for querying PRs with generated issues
CREATE INDEX idx_pr_has_generated_issue 
ON pull_requests(id) 
WHERE generated_issue IS NOT NULL;
```

**Why 2 columns instead of a separate table:**
- No need for version history (user acceptance)
- Simpler queries (no JOINs needed)
- Generated issue is 1:1 with PR
- User can regenerate if prompt improves later

**Migration Strategy:** Run via `setup/setup_database.py` or manual SQL script.

### Issue Structure

Generated markdown follows this structure:

```markdown
# {Issue Title}

## Motivation

{1-2 paragraphs explaining why this change is needed. What problem does it solve? What value does it provide?}

## Current Behavior

{Description of the current state or problem}

**Reproduction Steps:**
1. {Step 1}
2. {Step 2}
3. {Step 3}
4. Observe: {What you see}

{For refactors: describe current implementation and why it needs improvement}

## Expected Behavior

{Description of desired state after the fix}

**Acceptance Criteria:**
- [ ] {Criterion 1}
- [ ] {Criterion 2}
- [ ] {Criterion 3}

## Verification

{How to verify the fix works - manual steps or test commands}

**Manual Testing:**
1. {Test step 1}
2. {Test step 2}
3. Expected result: {What should happen}

{Or for unit test coverage:}

**Automated Testing:**
- Run `{test command}` and ensure tests pass
- Verify test coverage includes {specific scenarios}
```

### LLM Prompt Design

Create a new prompt template in `classifier/prompt_template.py`:

```python
ISSUE_GENERATION_PROMPT = """You are helping create training exercises for developers learning a new codebase.

Your task is to analyze a pull request and generate a clear, actionable GitHub issue that a student could use to implement the same change independently.

CONTEXT:
You will receive:
- The pull request title, description, and code changes
- Any linked issue and discussion (if available)
- Classification information (difficulty, concepts, etc.)

YOUR TASK:
Generate a markdown-formatted issue that includes:

1. **Issue Title**: Clear, specific title describing the problem/task
   - For bugs: "Description of broken behavior"
   - For features: "Add [feature description]"
   - For refactors: "Refactor [component] to [improvement]"

2. **Motivation**: 1-2 paragraphs explaining WHY this change matters
   - What problem does it solve?
   - What value does it provide to users/developers?
   - What's the business/technical context?

3. **Current Behavior**: Description of the existing state
   - For bugs: Explain the broken behavior with reproduction steps
   - For features: Explain what's missing or inadequate
   - For refactors: Describe current implementation and its limitations
   
   Always include **Reproduction Steps** (numbered list):
   - Specific, actionable steps anyone can follow
   - Include expected vs actual results for bugs
   - For refactors: steps to observe current behavior/limitations

4. **Expected Behavior**: Description of desired state after implementation
   - What should happen after the fix?
   - How should the system behave?
   
   Include **Acceptance Criteria** (checkbox list):
   - Specific, testable criteria
   - 3-5 clear checkpoints

5. **Verification**: How to test that the implementation works
   - Manual testing steps (if applicable)
   - Automated test commands (if applicable)
   - What to look for to confirm success
   
   ALL changes must be testable:
   - Bugs: Show the bug is fixed
   - Features: Show the feature works as intended
   - Refactors: Show tests still pass and behavior unchanged

GUIDELINES:
- Write as if you're a senior engineer creating a ticket for a junior developer
- Be clear and specific, but not overly detailed or hand-holding
- Follow engineering best practices for issue quality
- Professional tone, appropriate technical level for the difficulty
- Don't include hints or solution guidance - students should discover approach
- Even refactors must be reproducible and testable
- Extract the PROBLEM from the PR, not just describe the code changes
- Make it pedagogical - a learning opportunity, not just a task

DIFFICULTY CONSIDERATIONS:
- **Trivial**: Very straightforward, minimal context needed
- **Easy**: Clear steps, basic concepts, well-bounded
- **Medium**: More context, multiple components, some investigation needed
- **Hard**: Complex problem, requires system understanding, less prescriptive

OUTPUT FORMAT:

Return ONLY the markdown-formatted issue. Do not wrap it in JSON or code blocks.

Follow this exact structure:
# {Issue Title}

## Motivation
...

## Current Behavior
...

## Expected Behavior
...

## Verification
...

IMPORTANT:
- Return ONLY markdown text, no JSON wrapper, no code blocks
- Use proper markdown formatting with headers, lists, checkboxes
- Include all sections: Motivation, Current Behavior, Expected Behavior, Verification
- Make reproduction steps specific and actionable
- Make acceptance criteria testable
- All PRs are reproducible and testable, even refactors

Now, analyze the following pull request:

---

{pr_context}

---

CLASSIFICATION INFO:
{classification_info}

---

Generate the issue in markdown format:"""
```

### Backend Implementation

#### New API Endpoints

**1. Generate Issue Endpoint**

```python
from pydantic import BaseModel

class GenerateIssueRequest(BaseModel):
    """Request body for issue generation."""
    custom_prompt_template: Optional[str] = None  # If None, use default

@router.post("/api/prs/{repo:path}/{pr_number}/generate-issue")
async def generate_issue(
    repo: str, 
    pr_number: int,
    request: GenerateIssueRequest = None
):
    """
    Generate a student-facing issue from a PR.
    
    This uses LLM to create a clear, actionable issue description
    that includes motivation, reproduction steps, expected behavior,
    and verification instructions.
    
    Args:
        repo: Repository name
        pr_number: PR number
        request: Optional request body with custom_prompt_template
    
    Returns:
        {
            "issue_markdown": "# Title\n\n## Motivation...",
            "generated_at": "2025-10-11T10:30:00Z"
        }
    """
    # 1. Fetch PR with classification
    pr = supabase.get_pr_by_number(repo, pr_number)
    if not pr:
        raise HTTPException(404, "PR not found")
    
    # 2. Check if PR is classified (recommended but not required)
    if not pr.get("classification"):
        logger.warning(f"Generating issue for unclassified PR {repo}#{pr_number}")
    
    # 3. Build context using existing context_builder
    from classifier.context_builder import build_pr_context
    from classifier.prompt_template import ISSUE_GENERATION_PROMPT
    from classifier.llm_client import LLMClient
    from utils.config_loader import load_config
    
    config = load_config()
    pr_context = build_pr_context(pr)
    
    # Format classification info
    classification_info = ""
    if pr.get("classification"):
        classification = pr["classification"]
        classification_info = f"""
Difficulty: {classification.get('difficulty', 'Unknown')}
Task Clarity: {classification.get('task_clarity', 'Unknown')}
Onboarding Suitability: {classification.get('onboarding_suitability', 'Unknown')}
Categories: {', '.join(classification.get('categories', []))}
Concepts Taught: {', '.join(classification.get('concepts_taught', []))}
Prerequisites: {', '.join(classification.get('prerequisites', []))}
Reasoning: {classification.get('reasoning', 'N/A')}
"""
    else:
        classification_info = "No classification available"
    
    # 4. Use custom prompt template if provided, otherwise use default
    prompt_template = (
        request.custom_prompt_template 
        if request and request.custom_prompt_template 
        else ISSUE_GENERATION_PROMPT
    )
    
    # 5. Generate issue using LLM
    prompt = prompt_template.format(
        pr_context=pr_context,
        classification_info=classification_info
    )
    
    llm_client = LLMClient(config)
    issue_markdown = await llm_client.generate_issue(prompt)  # Returns plain markdown
    
    # 6. Save to database
    supabase.client.table("pull_requests").update({
        "generated_issue": issue_markdown,
        "issue_generated_at": "now()"
    }).eq("id", pr["id"]).execute()
    
    # 7. Return generated issue
    return {
        "issue_markdown": issue_markdown,
        "generated_at": datetime.now().isoformat()
    }
```

**2. Get Generated Issue Endpoint**

```python
@router.get("/api/prs/{repo:path}/{pr_number}/generated-issue")
def get_generated_issue(repo: str, pr_number: int):
    """
    Get the generated issue for a PR (if it exists).
    
    Returns:
        {
            "issue_markdown": "...",
            "generated_at": "2025-10-11T10:30:00Z"
        }
        
    Or 404 if no issue has been generated yet.
    """
    pr = supabase.get_pr_by_number(repo, pr_number)
    if not pr:
        raise HTTPException(404, "PR not found")
    
    if not pr.get("generated_issue"):
        raise HTTPException(404, "No issue generated for this PR yet")
    
    return {
        "issue_markdown": pr["generated_issue"],
        "generated_at": pr.get("issue_generated_at")
    }
```

**3. Get Default Issue Prompt Template**

```python
@router.get("/api/prompts/issue-generation")
def get_default_issue_prompt():
    """
    Get the default issue generation prompt template.
    
    This allows the frontend to display and edit the prompt template
    in the generation modal.
    
    Returns:
        {
            "prompt_template": "You are helping create training exercises..."
        }
    """
    from classifier.prompt_template import ISSUE_GENERATION_PROMPT
    
    return {
        "prompt_template": ISSUE_GENERATION_PROMPT
    }
```

**4. Get PR Context for Modal**

```python
@router.get("/api/prs/{repo:path}/{pr_number}/context")
def get_pr_context(repo: str, pr_number: int):
    """
    Get the formatted PR context that will be sent to the LLM.
    
    This is the same context used in classification and issue generation.
    Useful for displaying in the modal's "PR Context" tab.
    
    Returns:
        {
            "pr_context": "====...PULL REQUEST METADATA...",
            "classification_info": "Difficulty: easy..."
        }
    """
    from classifier.context_builder import build_pr_context
    
    # Fetch PR
    pr = supabase.get_pr_by_number(repo, pr_number)
    if not pr:
        raise HTTPException(404, "PR not found")
    
    # Build context
    pr_context = build_pr_context(pr)
    
    # Format classification info
    classification_info = ""
    if pr.get("classification"):
        classification = pr["classification"]
        classification_info = f"""
Difficulty: {classification.get('difficulty', 'Unknown')}
Task Clarity: {classification.get('task_clarity', 'Unknown')}
Onboarding Suitability: {classification.get('onboarding_suitability', 'Unknown')}
Categories: {', '.join(classification.get('categories', []))}
Concepts Taught: {', '.join(classification.get('concepts_taught', []))}
Prerequisites: {', '.join(classification.get('prerequisites', []))}
Reasoning: {classification.get('reasoning', 'N/A')}
"""
    else:
        classification_info = "No classification available"
    
    return {
        "pr_context": pr_context,
        "classification_info": classification_info
    }
```

#### LLM Client Extension

Extend `classifier/llm_client.py` with issue generation:

```python
class LLMClient:
    # ... existing methods ...
    
    async def generate_issue(self, prompt: str) -> str:
        """
        Generate a student-facing issue from a PR using LLM.
        
        Similar to classify() but expects plain markdown output (no JSON).
        
        Returns:
            str: The generated issue in markdown format
        """
        # Same error handling and retry logic as classify()
        # Returns the LLM response directly as markdown text
        pass
```

### Frontend Implementation

#### New Component: GeneratedIssueCard

Add to PR detail page after Classification Card. This component shows the generated issue if it exists, or a button to open the generation modal.

```tsx
function GeneratedIssueCard({ repo, prNumber, initialIssue }: {
  repo: string;
  prNumber: number;
  initialIssue?: { markdown: string; generatedAt: string };
}) {
  const [showModal, setShowModal] = useState(false);
  const [issue, setIssue] = useState(initialIssue);
  
  const copyToClipboard = async () => {
    if (!issue) return;
    
    try {
      await navigator.clipboard.writeText(issue.markdown);
      toast.success("Issue copied to clipboard!");
    } catch (err) {
      toast.error("Failed to copy to clipboard");
    }
  };
  
  return (
    <>
      <div className="bg-white rounded-lg shadow mb-6">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold">📝 Generated Student Issue</h2>
            
            {issue && (
              <div className="flex gap-2">
                <button
                  onClick={copyToClipboard}
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  Copy Issue
                </button>
                <button
                  onClick={() => setShowModal(true)}
                  className="px-3 py-1 text-sm bg-gray-600 text-white rounded hover:bg-gray-700"
                >
                  Regenerate...
                </button>
              </div>
            )}
          </div>
          
          {!issue ? (
            <div className="text-center py-8">
              <p className="text-gray-600 mb-4">
                No issue has been generated for this PR yet.
              </p>
              <button
                onClick={() => setShowModal(true)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Generate Issue...
              </button>
            </div>
          ) : (
            <div>
              <div className="bg-gray-50 rounded-lg border border-gray-200 p-6">
                {/* Render markdown */}
                <ReactMarkdown
                  className="prose prose-sm max-w-none"
                  remarkPlugins={[remarkGfm]}
                  components={{
                    // Custom rendering for checkboxes
                    input: ({ node, ...props }) => {
                      if (props.type === 'checkbox') {
                        return <input {...props} className="mr-2" />;
                      }
                      return <input {...props} />;
                    }
                  }}
                >
                  {issue.markdown}
                </ReactMarkdown>
              </div>
              
              <div className="mt-4 text-sm text-gray-500">
                Generated {formatDistanceToNow(new Date(issue.generatedAt))} ago
              </div>
            </div>
          )}
        </div>
      </div>
      
      {/* Issue Generation Modal */}
      {showModal && (
        <IssueGenerationModal
          repo={repo}
          prNumber={prNumber}
          onClose={() => setShowModal(false)}
          onIssueGenerated={(newIssue) => {
            setIssue(newIssue);
            setShowModal(false);
          }}
        />
      )}
    </>
  );
}
```

#### New Component: IssueGenerationModal

This modal provides a 3-tab interface for inspecting context, editing the prompt, and previewing before generation.

```tsx
type Tab = 'context' | 'prompt' | 'preview';

function IssueGenerationModal({ repo, prNumber, onClose, onIssueGenerated }: {
  repo: string;
  prNumber: number;
  onClose: () => void;
  onIssueGenerated: (issue: { markdown: string; generatedAt: string }) => void;
}) {
  const [activeTab, setActiveTab] = useState<Tab>('prompt');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedIssue, setGeneratedIssue] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Fetch PR data and default prompt template
  const { data: prData } = useQuery({
    queryKey: ["pr", repo, prNumber],
    queryFn: () => api.fetchPR(repo, prNumber),
  });
  
  const { data: defaultPrompt } = useQuery({
    queryKey: ["default-issue-prompt"],
    queryFn: () => api.fetchDefaultIssuePrompt(),
  });
  
  const { data: prContext } = useQuery({
    queryKey: ["pr-context", repo, prNumber],
    queryFn: () => api.fetchPRContext(repo, prNumber),
  });
  
  // Local state for editable prompt (starts with default)
  const [promptTemplate, setPromptTemplate] = useState(defaultPrompt || '');
  
  useEffect(() => {
    if (defaultPrompt) setPromptTemplate(defaultPrompt);
  }, [defaultPrompt]);
  
  // Build preview (template + context)
  const previewPrompt = useMemo(() => {
    if (!prContext || !prData?.classification) return '';
    
    const classificationInfo = formatClassificationInfo(prData.classification);
    
    return promptTemplate
      .replace('{pr_context}', prContext)
      .replace('{classification_info}', classificationInfo);
  }, [promptTemplate, prContext, prData]);
  
  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);
    
    try {
      // Send custom prompt template to backend
      const result = await api.generateIssue(repo, prNumber, promptTemplate);
      setGeneratedIssue(result.markdown);
      toast.success("Issue generated successfully!");
    } catch (err) {
      setError(err.message);
      toast.error("Failed to generate issue");
    } finally {
      setIsGenerating(false);
    }
  };
  
  const handleGenerateAgain = () => {
    setGeneratedIssue(null);
    setError(null);
    setActiveTab('prompt');
  };
  
  const handleClose = () => {
    if (generatedIssue) {
      onIssueGenerated({
        markdown: generatedIssue,
        generatedAt: new Date().toISOString(),
      });
    } else {
      onClose();
    }
  };
  
  const copyToClipboard = async () => {
    if (!generatedIssue) return;
    
    try {
      await navigator.clipboard.writeText(generatedIssue);
      toast.success("Issue copied to clipboard!");
    } catch (err) {
      toast.error("Failed to copy to clipboard");
    }
  };
  
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-5xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-bold">
            Generate Student Issue - PR #{prNumber}
          </h2>
          <button
            onClick={handleClose}
            className="text-gray-500 hover:text-gray-700"
          >
            ✕
          </button>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {!generatedIssue ? (
            <>
              {/* Tabs */}
              <div className="border-b px-6">
                <div className="flex gap-4">
                  <button
                    onClick={() => setActiveTab('context')}
                    className={`py-3 px-4 border-b-2 font-medium ${
                      activeTab === 'context'
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    PR Context
                  </button>
                  <button
                    onClick={() => setActiveTab('prompt')}
                    className={`py-3 px-4 border-b-2 font-medium ${
                      activeTab === 'prompt'
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    Prompt Template
                  </button>
                  <button
                    onClick={() => setActiveTab('preview')}
                    className={`py-3 px-4 border-b-2 font-medium ${
                      activeTab === 'preview'
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    Preview
                  </button>
                </div>
              </div>
              
              {/* Tab Content */}
              <div className="flex-1 overflow-auto p-6">
                {activeTab === 'context' && (
                  <div>
                    <p className="text-sm text-gray-600 mb-4">
                      This is the PR context that will be sent to the LLM.
                      Review it to ensure all necessary information is included.
                    </p>
                    <textarea
                      value={prContext || 'Loading...'}
                      readOnly
                      className="w-full h-96 font-mono text-xs p-4 border rounded bg-gray-50"
                    />
                  </div>
                )}
                
                {activeTab === 'prompt' && (
                  <div>
                    <p className="text-sm text-gray-600 mb-4">
                      Edit the prompt template. Changes only apply to this generation.
                      The template uses <code>{'{{pr_context}}'}</code> and <code>{'{{classification_info}}'}</code> placeholders.
                    </p>
                    <textarea
                      value={promptTemplate}
                      onChange={(e) => setPromptTemplate(e.target.value)}
                      className="w-full h-96 font-mono text-xs p-4 border rounded"
                      placeholder="Loading prompt template..."
                    />
                    <button
                      onClick={() => setPromptTemplate(defaultPrompt || '')}
                      className="mt-2 text-sm text-blue-600 hover:underline"
                    >
                      Restore Default Template
                    </button>
                  </div>
                )}
                
                {activeTab === 'preview' && (
                  <div>
                    <p className="text-sm text-gray-600 mb-4">
                      Preview of the complete prompt that will be sent to the LLM
                      (template with placeholders filled in).
                    </p>
                    <textarea
                      value={previewPrompt}
                      readOnly
                      className="w-full h-96 font-mono text-xs p-4 border rounded bg-gray-50"
                    />
                  </div>
                )}
              </div>
            </>
          ) : (
            /* Generated Issue View */
            <div className="flex-1 overflow-auto p-6">
              <div className="bg-gray-50 rounded-lg border border-gray-200 p-6">
                <ReactMarkdown
                  className="prose prose-sm max-w-none"
                  remarkPlugins={[remarkGfm]}
                >
                  {generatedIssue}
                </ReactMarkdown>
              </div>
            </div>
          )}
          
          {/* Error Display */}
          {error && (
            <div className="mx-6 mb-4 bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-800 text-sm">{error}</p>
            </div>
          )}
        </div>
        
        {/* Footer */}
        <div className="border-t p-6 flex justify-end gap-3">
          {!generatedIssue ? (
            <>
              <button
                onClick={onClose}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded"
              >
                Cancel
              </button>
              <button
                onClick={handleGenerate}
                disabled={isGenerating || !promptTemplate}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isGenerating ? (
                  <>
                    <span className="inline-block animate-spin mr-2">⏳</span>
                    Generating...
                  </>
                ) : (
                  'Generate'
                )}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={handleGenerateAgain}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded"
              >
                Generate Again
              </button>
              <button
                onClick={copyToClipboard}
                className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
              >
                Copy Issue
              </button>
              <button
                onClick={handleClose}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Save & Close
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
```

#### Updated PRDetail Layout

```tsx
function PRDetail({ repo, prNumber }: Props) {
  const { data: pr, isLoading } = useQuery({
    queryKey: ["pr", repo, prNumber],
    queryFn: () => api.fetchPR(repo, prNumber),
  });
  
  // Fetch generated issue if it exists
  const { data: generatedIssue } = useQuery({
    queryKey: ["generated-issue", repo, prNumber],
    queryFn: () => api.fetchGeneratedIssue(repo, prNumber),
    retry: false, // Don't retry 404s
  });
  
  if (isLoading) return <LoadingSpinner />;
  if (!pr) return <NotFound />;
  
  return (
    <div className="container mx-auto p-6">
      {/* 1. PR Header - title, body, metadata */}
      <PRHeader pr={pr} />
      
      {/* 2. Classification Card */}
      {pr.classification && (
        <ClassificationCard classification={pr.classification} />
      )}
      
      {/* 3. Generated Issue Card - NEW */}
      <GeneratedIssueCard
        repo={repo}
        prNumber={prNumber}
        initialIssue={generatedIssue}
      />
      
      {/* 4. LLM Payload (Debug) */}
      <LLMPayloadCard repo={repo} prNumber={prNumber} />
      
      {/* 5. Files Changed */}
      <FilesChangedCard files={pr.files} />
      
      {/* 6. Linked Issue (original) */}
      {pr.linked_issue && <LinkedIssueCard issue={pr.linked_issue} />}
      
      {/* 7. Issue Comments */}
      {pr.issue_comments && <IssueCommentsCard comments={pr.issue_comments} />}
    </div>
  );
}
```

#### API Client Updates

Add to `frontend/src/lib/api.ts`:

```typescript
export async function generateIssue(
  repo: string,
  prNumber: number,
  customPromptTemplate?: string
): Promise<{ markdown: string; generatedAt: string }> {
  const response = await fetch(
    `${API_BASE}/api/prs/${encodeURIComponent(repo)}/${prNumber}/generate-issue`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        custom_prompt_template: customPromptTemplate || null,
      }),
    }
  );
  
  if (!response.ok) {
    throw new Error(`Failed to generate issue: ${response.statusText}`);
  }
  
  const data = await response.json();
  return {
    markdown: data.issue_markdown,
    generatedAt: data.generated_at,
  };
}

export async function fetchGeneratedIssue(
  repo: string,
  prNumber: number
): Promise<{ markdown: string; generatedAt: string } | null> {
  const response = await fetch(
    `${API_BASE}/api/prs/${encodeURIComponent(repo)}/${prNumber}/generated-issue`
  );
  
  if (response.status === 404) {
    return null; // No issue generated yet
  }
  
  if (!response.ok) {
    throw new Error(`Failed to fetch generated issue: ${response.statusText}`);
  }
  
  const data = await response.json();
  return {
    markdown: data.issue_markdown,
    generatedAt: data.generated_at,
  };
}

export async function fetchDefaultIssuePrompt(): Promise<string> {
  const response = await fetch(`${API_BASE}/api/prompts/issue-generation`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch prompt template: ${response.statusText}`);
  }
  
  const data = await response.json();
  return data.prompt_template;
}

export async function fetchPRContext(
  repo: string,
  prNumber: number
): Promise<{ prContext: string; classificationInfo: string }> {
  const response = await fetch(
    `${API_BASE}/api/prs/${encodeURIComponent(repo)}/${prNumber}/context`
  );
  
  if (!response.ok) {
    throw new Error(`Failed to fetch PR context: ${response.statusText}`);
  }
  
  const data = await response.json();
  return {
    prContext: data.pr_context,
    classificationInfo: data.classification_info,
  };
}
```

## Data Flow

```
User views PR detail page
    ↓
Frontend checks if generated_issue exists
    ↓
    ├─ YES → Display issue card with rendered markdown
    │        [Copy Issue] [Regenerate...] buttons
    │
    └─ NO → Show empty card with [Generate Issue...] button
            ↓
        User clicks "Generate Issue..." or "Regenerate..."
            ↓
        Modal opens with 3 tabs
            ↓
        Modal loads data in parallel:
        - GET /api/prs/{repo}/{pr}/context → PR Context tab
        - GET /api/prompts/issue-generation → Prompt Template tab
        - Compute preview (template + context) → Preview tab
            ↓
        User reviews/edits prompt template (optional)
            ↓
        User clicks "Generate" button in modal
            ↓
        POST /api/prs/{repo}/{pr}/generate-issue
        Body: { custom_prompt_template: "..." } (if edited)
            ↓
        Backend:
        1. Fetch PR data (with classification)
        2. Build PR context using build_pr_context()
        3. Format classification info
        4. Use custom prompt template (if provided) or default
        5. Fill template with context and classification
        6. Send to LLM with filled prompt
        7. Receive plain markdown response (no JSON parsing needed)
        8. Save markdown to generated_issue column
        9. Update issue_generated_at timestamp
        10. Return generated issue
            ↓
        Modal:
        1. Shows loading spinner ("Generating...")
        2. Receives generated markdown
        3. Switches to result view (rendered markdown)
        4. Shows [Generate Again] [Copy Issue] [Save & Close]
            ↓
        User actions:
        - "Generate Again" → return to tabs, keep edited prompt
        - "Copy Issue" → copy markdown to clipboard
        - "Save & Close" → close modal
            ↓
        Modal closes
            ↓
        PR detail page updates:
        - Generated issue now visible in card
        - Rendered markdown displayed
        - [Copy Issue] [Regenerate...] buttons available
```

## Prompt Engineering Strategy

The issue generation prompt should:

1. **Extract the problem, not describe the solution**
   - Bad: "This PR adds a new validation check"
   - Good: "Users can submit invalid email addresses, causing downstream errors"

2. **Make it reproducible even when PR doesn't explain**
   - Use code changes to infer reproduction steps
   - For refactors: explain current limitations as "current behavior"

3. **Adapt to difficulty level**
   - Trivial: Very brief, obvious steps
   - Easy: Clear steps, bounded scope
   - Medium: More context, some investigation needed
   - Hard: High-level problem, less prescriptive steps

4. **Always include verification**
   - Manual testing steps when appropriate
   - Test commands for code changes
   - Clear success criteria

5. **Handle edge cases gracefully**
   - Refactors: "Current implementation has X limitation, refactor to Y"
   - Infrastructure: "Current deployment process requires manual step X"
   - Tests: "Test suite is missing coverage for scenario X"


## Quality Evaluation Criteria

A good generated issue should:

- **Clear motivation**: Explains WHY in 1-2 paragraphs
- **Reproducible**: Steps anyone can follow to see current behavior
- **Specific acceptance criteria**: Testable, checkbox-style criteria
- **Verifiable**: Clear instructions to test the fix
- **Appropriate detail**: Not too sparse, not too elaborate
- **Professional tone**: Engineering quality, pedagogical approach
- **Self-contained**: Student can understand without reading PR

A bad generated issue would:

- Just describe code changes without explaining problem
- Have vague or generic reproduction steps
- Lack clear acceptance criteria
- Have no verification instructions
- Be overly detailed or include solution hints
- Require reading the PR to understand

## Open Questions & Future Work

### Near-term Questions

1. **Markdown library**: Use `react-markdown` or another library?
   - Recommendation: `react-markdown` (popular, well-maintained)

2. **Issue length limits**: Should we limit markdown length?
   - Monitor in practice, add if issues become too long

3. **Classification requirement**: Should we require classification before generating issue?
   - Recommendation: No (warn but allow) - classification helps but isn't required

## Technical Notes

### Markdown Rendering

Use `react-markdown` with custom components:

```bash
npm install react-markdown remark-gfm
```

```tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm'; // GitHub Flavored Markdown

<ReactMarkdown
  remarkPlugins={[remarkGfm]}
  className="prose prose-sm max-w-none"
>
  {issueMarkdown}
</ReactMarkdown>
```
