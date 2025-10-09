export interface PullRequest {
  id: number;
  repo: string;
  pr_number: number;
  title: string;
  body: string | null;
  merged_at: string;
  created_at: string;
  linked_issue_number: number | null;
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
