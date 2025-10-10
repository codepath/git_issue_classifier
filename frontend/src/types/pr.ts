export interface PullRequest {
  id: number;
  repo: string;
  repo_url: string;
  pr_number: number;
  title: string;
  body: string | null;
  merged_at: string;
  created_at: string;
  linked_issue_number: number | null;
  platform: string;
  files: {
    files: Array<{
      filename: string;
      status: string;
      additions: number;
      deletions: number;
      changes: number;
      patch?: string;
    }>;
    summary: {
      total_files: number;
      total_additions: number;
      total_deletions: number;
      truncated: boolean;
    };
  } | null;
  linked_issue: {
    number: number;
    title: string;
    body: string | null;
    state: string;
  } | null;
  issue_comments: Array<{
    id: number;
    body: string;
    created_at: string;
    user: {
      login: string;
    };
  }> | null;
  enrichment_status: string;
  enrichment_attempted_at: string | null;
  enrichment_error: string | null;
  
  // Classification fields (nullable until classified)
  difficulty?: string | null;
  task_clarity?: string | null;
  is_reproducible?: string | null;
  onboarding_suitability?: string | null;
  categories?: string[] | null;
  concepts_taught?: string[] | null;
  prerequisites?: string[] | null;
  reasoning?: string | null;
  classified_at?: string | null;
  
  llm_payload?: string | null;
  
  // Favorite field
  is_favorite?: boolean;
}

export interface PRListResponse {
  prs: PullRequest[];
  total: number;
  page: number;
  per_page: number;
}

export interface ReposResponse {
  repos: string[];
}
