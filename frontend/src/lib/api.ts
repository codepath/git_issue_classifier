import type { 
  PullRequest, 
  PRListResponse, 
  ReposResponse, 
  GeneratedIssue, 
  PRContext, 
  IssuePromptTemplate 
} from "@/types/pr";

// In production, VITE_API_URL will be set by Render
// In development, it falls back to the local API proxy
const API_BASE_URL = import.meta.env.VITE_API_URL 
  ? `${import.meta.env.VITE_API_URL}/api`
  : "/api";

export interface PRFilters {
  repo?: string;
  page?: number;
  perPage?: number;
  cutoffDate?: string;
  sortOrder?: "asc" | "desc";
  onboardingSuitability?: string;
  difficulty?: string;
  taskClarity?: string;
  isReproducible?: string;
  isFavorite?: boolean;
}

export async function fetchPRs(
  repo?: string,
  page: number = 1,
  perPage: number = 50,
  cutoffDate?: string,
  sortOrder?: "asc" | "desc",
  onboardingSuitability?: string,
  difficulty?: string,
  taskClarity?: string,
  isReproducible?: string,
  isFavorite?: boolean
): Promise<PRListResponse> {
  const params = new URLSearchParams({
    page: page.toString(),
    per_page: perPage.toString(),
  });

  if (repo) {
    params.append("repo", repo);
  }

  if (cutoffDate) {
    params.append("cutoff_date", cutoffDate);
  }

  if (sortOrder) {
    params.append("sort_order", sortOrder);
  }

  if (onboardingSuitability) {
    params.append("onboarding_suitability", onboardingSuitability);
  }

  if (difficulty) {
    params.append("difficulty", difficulty);
  }

  if (taskClarity) {
    params.append("task_clarity", taskClarity);
  }

  if (isReproducible) {
    params.append("is_reproducible", isReproducible);
  }

  if (isFavorite !== undefined) {
    params.append("is_favorite", isFavorite.toString());
  }

  const response = await fetch(`${API_BASE_URL}/prs?${params}`);

  if (!response.ok) {
    throw new Error(`Failed to fetch PRs: ${response.statusText}`);
  }

  return response.json();
}

export async function fetchPR(
  repo: string,
  prNumber: number
): Promise<PullRequest> {
  const response = await fetch(`${API_BASE_URL}/prs/${repo}/${prNumber}`);

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`PR not found: ${repo}#${prNumber}`);
    }
    throw new Error(`Failed to fetch PR: ${response.statusText}`);
  }

  return response.json();
}

export async function fetchRepos(): Promise<ReposResponse> {
  const response = await fetch(`${API_BASE_URL}/repos`);

  if (!response.ok) {
    throw new Error(`Failed to fetch repos: ${response.statusText}`);
  }

  return response.json();
}

export async function toggleFavorite(
  repo: string,
  prNumber: number
): Promise<PullRequest> {
  const response = await fetch(`${API_BASE_URL}/prs/${repo}/${prNumber}/favorite`, {
    method: "POST",
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`PR not found: ${repo}#${prNumber}`);
    }
    throw new Error(`Failed to toggle favorite: ${response.statusText}`);
  }

  return response.json();
}

// ============================================================================
// Issue Generation API Methods
// NOTE: These are implemented for Phase 5 (UI), awaiting Phase 3 (backend)
// ============================================================================

/**
 * Generate a student-facing issue from a PR.
 * 
 * @param repo - Repository name (e.g., "facebook/react")
 * @param prNumber - PR number
 * @param customPromptTemplate - Optional custom prompt template to use instead of default
 * @returns Generated issue markdown and timestamp
 */
export async function generateIssue(
  repo: string,
  prNumber: number,
  customPromptTemplate?: string
): Promise<GeneratedIssue> {
  const response = await fetch(
    `${API_BASE_URL}/prs/${encodeURIComponent(repo)}/${prNumber}/generate-issue`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        custom_prompt_template: customPromptTemplate || null,
      }),
    }
  );

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`PR not found: ${repo}#${prNumber}`);
    }
    const errorText = await response.text();
    throw new Error(`Failed to generate issue: ${errorText || response.statusText}`);
  }

  return response.json();
}

/**
 * Get the generated issue for a PR (if it exists).
 * 
 * @param repo - Repository name (e.g., "facebook/react")
 * @param prNumber - PR number
 * @returns Generated issue data or null if no issue has been generated
 */
export async function fetchGeneratedIssue(
  repo: string,
  prNumber: number
): Promise<GeneratedIssue | null> {
  const response = await fetch(
    `${API_BASE_URL}/prs/${encodeURIComponent(repo)}/${prNumber}/generated-issue`
  );

  if (response.status === 404) {
    return null; // No issue generated yet
  }

  if (!response.ok) {
    throw new Error(`Failed to fetch generated issue: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get the default issue generation prompt template.
 * 
 * @returns Default prompt template string
 */
export async function fetchDefaultIssuePrompt(): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/prompts/issue-generation`);

  if (!response.ok) {
    throw new Error(`Failed to fetch prompt template: ${response.statusText}`);
  }

  const data: IssuePromptTemplate = await response.json();
  return data.prompt_template;
}

/**
 * Get the formatted PR context that will be sent to the LLM.
 * 
 * This is useful for displaying in the modal's "PR Context" tab.
 * 
 * @param repo - Repository name (e.g., "facebook/react")
 * @param prNumber - PR number
 * @returns PR context and classification info
 */
export async function fetchPRContext(
  repo: string,
  prNumber: number
): Promise<PRContext> {
  const response = await fetch(
    `${API_BASE_URL}/prs/${encodeURIComponent(repo)}/${prNumber}/context`
  );

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`PR not found: ${repo}#${prNumber}`);
    }
    throw new Error(`Failed to fetch PR context: ${response.statusText}`);
  }

  return response.json();
}
