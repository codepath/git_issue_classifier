import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchPRs, fetchRepos, toggleFavorite } from "@/lib/api";
import type { PullRequest, PRListResponse } from "@/types/pr";
import { Badge } from "@/components/ui/badge";

// Helper function to calculate date N months ago
function getDateMonthsAgo(months: number): string {
  const date = new Date();
  date.setMonth(date.getMonth() - months);
  return date.toISOString().split("T")[0]; // Format as YYYY-MM-DD
}

function PRList() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedRepo, setSelectedRepo] = useState<string>("");
  const [page, setPage] = useState(1);
  const perPage = 50;
  
  // Date cutoff and sort order state
  const [cutoffDate, setCutoffDate] = useState<string>(getDateMonthsAgo(3)); // Default: 3 months ago
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc"); // Default: oldest first (chronological)
  
  // Classification filter state
  const [onboardingSuitability, setOnboardingSuitability] = useState<string>("");
  const [difficulty, setDifficulty] = useState<string>("");
  
  // Favorite filter state
  const [showOnlyFavorites, setShowOnlyFavorites] = useState<boolean>(false);

  // Fetch repositories for filter dropdown
  const { data: reposData } = useQuery({
    queryKey: ["repos"],
    queryFn: fetchRepos,
  });

  // Fetch PRs with pagination and filtering
  const { data, isLoading, error } = useQuery({
    queryKey: ["prs", selectedRepo, page, cutoffDate, sortOrder, onboardingSuitability, difficulty, showOnlyFavorites],
    queryFn: () => fetchPRs(
      selectedRepo || undefined, 
      page, 
      perPage, 
      cutoffDate, 
      sortOrder,
      onboardingSuitability || undefined,
      difficulty || undefined,
      undefined, // taskClarity - not used
      undefined, // isReproducible - not used
      showOnlyFavorites ? true : undefined
    ),
  });

  // Mutation for toggling favorites with optimistic updates
  const favoriteMutation = useMutation({
    mutationFn: ({ repo, prNumber }: { repo: string; prNumber: number }) =>
      toggleFavorite(repo, prNumber),
    onMutate: async ({ repo, prNumber }) => {
      // Cancel outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: ["prs"] });

      // Snapshot the previous value
      const previousData = queryClient.getQueryData(["prs", selectedRepo, page, cutoffDate, sortOrder, onboardingSuitability, difficulty, showOnlyFavorites]);

      // Optimistically update the UI
      queryClient.setQueryData(
        ["prs", selectedRepo, page, cutoffDate, sortOrder, onboardingSuitability, difficulty, showOnlyFavorites],
        (old: PRListResponse | undefined) => {
          if (!old) return old;
          return {
            ...old,
            prs: old.prs.map((pr: PullRequest) =>
              pr.repo === repo && pr.pr_number === prNumber
                ? { ...pr, is_favorite: !pr.is_favorite }
                : pr
            ),
          };
        }
      );

      return { previousData };
    },
    onError: (err, _variables, context) => {
      // Rollback on error
      if (context?.previousData) {
        queryClient.setQueryData(
          ["prs", selectedRepo, page, cutoffDate, sortOrder, onboardingSuitability, difficulty, showOnlyFavorites],
          context.previousData
        );
      }
      console.error("Failed to toggle favorite:", err);
    },
    onSettled: () => {
      // Refetch to ensure data consistency
      queryClient.invalidateQueries({ queryKey: ["prs"] });
    },
  });

  const handleFavoriteClick = (e: React.MouseEvent, pr: PullRequest) => {
    e.stopPropagation(); // Don't trigger row click
    favoriteMutation.mutate({ repo: pr.repo, prNumber: pr.pr_number });
  };

  const handleRowClick = (pr: PullRequest) => {
    // Navigate to PR detail page
    // repo format is "owner/repo", so we split it
    const [owner, repo] = pr.repo.split("/");
    navigate(`/pr/${owner}/${repo}/${pr.pr_number}`);
  };

  const totalPages = data ? Math.ceil(data.total / perPage) : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="w-[1400px] mx-auto px-5 py-4">
        {/* Header */}
        <div className="mb-4">
          <h1 className="text-2xl font-bold text-gray-900 mb-1">
            Pull Request Explorer
          </h1>
          <p className="text-sm text-gray-600">
            Browse {data?.total.toLocaleString() || "..."} pull requests across repositories
          </p>
        </div>

        {/* How to Use Section */}
        <div className="bg-gray-50 border border-gray-300 rounded-lg p-4 mb-4 max-w-3xl">
          <h2 className="text-base font-semibold text-gray-900 mb-2">
            How to Use This Tool
          </h2>
          
          <p className="text-sm text-gray-700 mb-3 leading-relaxed">
            The purpose of this tool is to help you select onboarding issues for a repository hosted on GitHub or GitLab. 
            A group of developers are joining the project, and they'll familiarize themselves with the project by implementing 
            past merged pull requests.
          </p>

          <ul className="text-sm text-gray-700 mb-3 space-y-1.5 ml-4">
            <li className="flex gap-2">
              <span className="text-gray-600 font-bold">•</span>
              <span>Onboarding developers will use a fork of the project that has been rewound in time (e.g., 3-6 months).</span>
            </li>
            <li className="flex gap-2">
              <span className="text-gray-600 font-bold">•</span>
              <span>Onboarding developers will choose a selection of easy, medium, and hard issues to tackle.</span>
            </li>
          </ul>

          <div className="text-sm text-gray-700">
            <p className="font-medium mb-2">To use this tool, follow the steps below:</p>
            <ol className="space-y-1.5 ml-5 list-decimal">
              <li>Choose your repository and past date.</li>
              <li>Start exploring past pull requests, which have been categorized by AI as a good onboarding issue, and assigned a difficulty level.</li>
              <li>When you find an issue that you like, favorite it.</li>
            </ol>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-3 mb-4">
          {/* Row 1: Repository Filter */}
          <div className="flex gap-3 items-center mb-3">
            <label className="text-sm font-medium text-gray-700">
              Repository:
            </label>
            <select
              value={selectedRepo}
              onChange={(e) => {
                setSelectedRepo(e.target.value);
                setPage(1); // Reset to first page when filter changes
              }}
              className="px-2.5 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Repositories</option>
              {reposData?.repos.map((repo) => (
                <option key={repo} value={repo}>
                  {repo}
                </option>
              ))}
            </select>
          </div>

          {/* Row 2: Date and Sort Controls */}
          <div className="flex gap-5 items-center flex-wrap">
            {/* Date Picker */}
            <div className="flex gap-2 items-center">
              <label className="text-sm font-medium text-gray-700">
                Show PRs merged after:
              </label>
              <input
                type="date"
                value={cutoffDate}
                onChange={(e) => {
                  setCutoffDate(e.target.value);
                  setPage(1); // Reset to first page when filter changes
                }}
                className="px-2.5 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Sort Order */}
            <div className="flex gap-2 items-center">
              <label className="text-sm font-medium text-gray-700">
                Sort order:
              </label>
              <select
                value={sortOrder}
                onChange={(e) => {
                  setSortOrder(e.target.value as "asc" | "desc");
                  setPage(1); // Reset to first page when sort changes
                }}
                className="px-2.5 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="asc">Oldest First (Chronological)</option>
                <option value="desc">Newest First</option>
              </select>
            </div>
          </div>

          {/* Row 3: Classification Filters */}
          <div className="flex gap-5 items-center flex-wrap mt-3 pt-3 border-t">
            <div className="text-sm font-medium text-gray-700">
              Classification Filters:
            </div>

            {/* Onboarding Suitability */}
            <div className="flex gap-2 items-center">
              <label className="text-sm text-gray-600">
                Onboarding Suitability: 
              </label>
              <select
                value={onboardingSuitability}
                onChange={(e) => {
                  setOnboardingSuitability(e.target.value);
                  setPage(1);
                }}
                className="px-2.5 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All</option>
                <option value="excellent">Excellent</option>
                <option value="poor">Poor</option>
              </select>
            </div>

            {/* Difficulty */}
            <div className="flex gap-2 items-center">
              <label className="text-sm text-gray-600">
                Difficulty:
              </label>
              <select
                value={difficulty}
                onChange={(e) => {
                  setDifficulty(e.target.value);
                  setPage(1);
                }}
                className="px-2.5 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All</option>
                <option value="trivial">Trivial</option>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </div>

            {/* Favorites Only Checkbox */}
            <div className="flex gap-2 items-center">
              <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showOnlyFavorites}
                  onChange={(e) => {
                    setShowOnlyFavorites(e.target.checked);
                    setPage(1);
                  }}
                  className="w-3.5 h-3.5 text-blue-600 border-gray-300 rounded focus:ring-2 focus:ring-blue-500"
                />
                <span>Favorites Only</span>
              </label>
            </div>

            {/* Clear Filters Button */}
            {(onboardingSuitability || difficulty || showOnlyFavorites) && (
              <button
                onClick={() => {
                  setOnboardingSuitability("");
                  setDifficulty("");
                  setShowOnlyFavorites(false);
                  setPage(1);
                }}
                className="px-2.5 py-1.5 text-sm border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors"
              >
                Clear All Filters
              </button>
            )}
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="inline-block h-7 w-7 animate-spin rounded-full border-4 border-solid border-blue-500 border-r-transparent"></div>
            <p className="mt-2 text-sm text-gray-600">Loading PRs...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <p className="text-sm text-red-800">
              <strong>Error:</strong> {(error as Error).message}
            </p>
          </div>
        )}

        {/* PR Table */}
        {data && !isLoading && (
          <>
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase tracking-wide w-12">
                      ★
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Repository
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      PR #
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Title
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Suitability
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Difficulty
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Merged Date
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {data.prs.length === 0 ? (
                    <tr>
                      <td
                        colSpan={7}
                        className="px-4 py-6 text-center text-sm text-gray-500"
                      >
                        No PRs found
                      </td>
                    </tr>
                  ) : (
                    data.prs.map((pr) => (
                      <tr
                        key={pr.id}
                        onClick={() => handleRowClick(pr)}
                        className="hover:bg-gray-50 cursor-pointer transition-colors"
                      >
                        <td className="px-3 py-2.5 whitespace-nowrap text-center">
                          <button
                            onClick={(e) => handleFavoriteClick(e, pr)}
                            className="text-xl leading-none hover:scale-110 transition-transform focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded"
                            aria-label={pr.is_favorite ? "Remove from favorites" : "Add to favorites"}
                            title={pr.is_favorite ? "Remove from favorites" : "Add to favorites"}
                          >
                            {pr.is_favorite ? "★" : "☆"}
                          </button>
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap text-sm text-gray-900">
                          {pr.repo}
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap text-sm font-medium text-blue-600">
                          #{pr.pr_number}
                        </td>
                        <td className="px-4 py-2.5 text-sm text-gray-900 max-w-md truncate">
                          {pr.title}
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap">
                          {pr.onboarding_suitability ? (
                            <Badge 
                              variant={
                                pr.onboarding_suitability === "excellent" 
                                  ? "excellent" 
                                  : "poor"
                              }
                            >
                              {pr.onboarding_suitability}
                            </Badge>
                          ) : (
                            <span className="text-xs text-gray-400">N/A</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap text-sm text-gray-600">
                          {pr.difficulty ? (
                            <Badge variant="secondary">
                              {pr.difficulty}
                            </Badge>
                          ) : (
                            <span className="text-xs text-gray-400">N/A</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap text-sm text-gray-500">
                          {new Date(pr.merged_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="mt-4 flex items-center justify-between">
              <div className="text-sm text-gray-700">
                Page {page} of {totalPages} ({data.total.toLocaleString()} total
                PRs)
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default PRList;
