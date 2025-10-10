import type { PullRequest, PRListResponse, ReposResponse } from "@/types/pr";

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
