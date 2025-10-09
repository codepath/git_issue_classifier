"""
Classification prompt template for LLM.

This is a flexible template that will evolve as we develop the prompt.
Keeping it as a separate configuration file makes iteration easy.
"""

CLASSIFICATION_PROMPT = """You are helping identify pull requests that are good learning opportunities for developers new to a codebase.

Your task is to analyze the PR and classify it based on technical complexity and onboarding suitability.

CLASSIFICATION FIELDS:

1. **difficulty**: Technical complexity level
   - "trivial": Very simple changes (typos, comments, formatting)
   - "easy": Simple bug fixes or small features requiring basic understanding
   - "medium": Moderate complexity requiring understanding of multiple components
   - "hard": Complex changes requiring deep system knowledge or architectural changes

2. **task_clarity**: Could you write a GitHub issue with enough context for someone else to solve this?
   
   **"clear"** - Yes, enough information to delegate:
   - Problem is documented with context
   - Steps to reproduce the issue are provided or obvious
   - Success criteria are clear
   - Example: "Users report 401 errors on CORS preflight requests to /user-protected. Reproduce: make OPTIONS request to protected endpoint, observe 401. Expected: should return 200 without auth check."
   - Example: "Button text overflows container in Japanese locale. Reproduce: switch to Japanese language, navigate to settings, see 'Save Settings' button overflow. Expected: button should fit container."
   - Example: "Add pagination to Maven upstreams table. When 20+ items exist, table becomes unwieldy. Add pagination component with 10 items per page."
   
   **"partial"** - Some context but missing key information:
   - General problem described but lacks specifics
   - Reproduction steps incomplete or unclear
   - Would need to ask clarifying questions
   - Example: "Fix flaky test in user_spec.rb" (which test? how does it flake? how to reproduce?)
   - Example: "Refactor old authentication pattern" (which pattern? where to find instances? what's wrong with it?)
   - Example: "Update API to be more consistent" (which endpoints? what inconsistency? what should it be?)
   
   **"poor"** - Relies on undocumented author knowledge:
   - Cannot write a task others could complete
   - Missing critical context about what needs to be done
   - Requires intimate knowledge of recent changes or migrations
   - Example: "Remove unused epic code" (which code is unused? how to verify? why is it unused?)
   - Example: "Clean up after work item migration" (what needs cleaning? how to identify leftovers?)
   - Example: "Fix the thing we discussed" (what thing? no written context exists)

3. **is_reproducible**: Can someone reproduce the ORIGINAL PROBLEM that this PR fixes? Choose one:
   
   **"highly likely"** - The problem is clear and reproducible:
   - Explicit reproduction steps in PR/issue ("Steps to reproduce: 1, 2, 3...")
   - Clear error message or bug report included
   - Obvious visual/UX issue shown (broken UI, wrong behavior)
   - Example: "Users report 401 errors on CORS preflight requests" with error logs
   - Example: "Clicking logout doesn't clear cache, causing data leakage between users"
   
   **"maybe"** - Can infer the problem but not explicitly stated:
   - No direct steps, but problem is implied by code/tests
   - Partially documented or requires some context
   - Example: Adding backward compatibility without explaining what broke
   - Example: "Fix bug in validation" without showing the buggy behavior
   
   **"unclear"** - Cannot understand what problem this solves:
   - No problem statement, just code changes
   - One-off administrative tasks (version bumps, adding users to lists)
   - Translation changes (can see missing translations but can't verify correctness)
   - "Refactor" without explaining what was wrong
   - Requires deep system knowledge to understand the issue
   - Example: Version number changes with no context
   - Example: "Update config" without explaining why
   - Example: Adding Vietnamese translations (can't verify they're correct without fluency)

4. **onboarding_suitability**: How good is this for onboarding? Choose one:
   
   **"excellent"** - Must have ALL of these:
   ✓ Problem is reproducible (is_reproducible should be "highly likely")
   ✓ Verifiable for the given difficulty level:
     - Easy/trivial: Can test without system knowledge
     - Medium/hard: Clear verification approach even if requires understanding one subsystem
   ✓ NOT release management, deployment, or pure infrastructure work
   ✓ Teaches transferable patterns (not one-off hacks or project-specific quirks)
   ✓ Clear motivation - understandable WHY this change is needed
   
   Note: Medium/hard PRs CAN be excellent if they teach valuable concepts with clear reproduction!
   Examples: implementing caching, refactoring for testability, API design patterns
   
   **"poor"** - Has ANY of these:
   ✗ Cannot reproduce or verify without extensive system knowledge
   ✗ Infrastructure, release management, deployment, or admin tasks
   ✗ Translation-only changes (cannot verify correctness without language fluency)
   ✗ Unclear motivation even after reading PR and code
   ✗ One-off administrative changes (adding users to whitelists, updating version numbers)
   ✗ Requires understanding entire codebase architecture
   ✗ Hard to test or verify the fix actually works

5. **categories**: List of relevant categories (flexible - choose what fits best)
   Examples: bug-fix, feature, refactor, performance, documentation, testing, security, ui/ux, api, database, etc.

6. **concepts_taught**: What technical concepts would a developer learn from studying this PR?
   Be specific - e.g., "React hooks lifecycle", "SQL injection prevention", "event delegation", etc.

7. **prerequisites**: What knowledge should someone have before studying this PR?
   Be specific - e.g., "Basic React understanding", "Familiarity with async/await", etc.

8. **reasoning**: Brief explanation (2-4 sentences) of your classification decisions.
   Why this difficulty level? Is the task clear enough to delegate? Is it reproducible? Why this onboarding suitability?

OUTPUT FORMAT:

Return ONLY a valid JSON object with this exact structure:

{{
  "difficulty": "trivial" | "easy" | "medium" | "hard",
  "task_clarity": "clear" | "partial" | "poor",
  "is_reproducible": "highly likely" | "maybe" | "unclear",
  "onboarding_suitability": "excellent" | "poor",
  "categories": ["category1", "category2", ...],
  "concepts_taught": ["concept1", "concept2", ...],
  "prerequisites": ["prerequisite1", "prerequisite2", ...],
  "reasoning": "Your explanation here"
}}

IMPORTANT:
- Return ONLY valid JSON, no other text
- All fields are required
- categories, concepts_taught, and prerequisites should be non-empty arrays
- Be specific and educational in your classifications

Now, analyze the following pull request:

---

{pr_context}

---

Return your classification as JSON:"""

