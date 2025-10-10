import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchPRs, fetchRepos } from "@/lib/api";
import type { PullRequest } from "@/types/pr";
import { Badge } from "@/components/ui/badge";

// Helper function to calculate date N months ago
function getDateMonthsAgo(months: number): string {
  const date = new Date();
  date.setMonth(date.getMonth() - months);
  return date.toISOString().split("T")[0]; // Format as YYYY-MM-DD
}

function PRList() {
  const navigate = useNavigate();
  const [selectedRepo, setSelectedRepo] = useState<string>("");
  const [page, setPage] = useState(1);
  const perPage = 50;
  
  // Date cutoff and sort order state
  const [cutoffDate, setCutoffDate] = useState<string>(getDateMonthsAgo(3)); // Default: 3 months ago
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc"); // Default: oldest first (chronological)
  
  // Classification filter state
  const [onboardingSuitability, setOnboardingSuitability] = useState<string>("");
  const [difficulty, setDifficulty] = useState<string>("");

  // Fetch repositories for filter dropdown
  const { data: reposData } = useQuery({
    queryKey: ["repos"],
    queryFn: fetchRepos,
  });

  // Fetch PRs with pagination and filtering
  const { data, isLoading, error } = useQuery({
    queryKey: ["prs", selectedRepo, page, cutoffDate, sortOrder, onboardingSuitability, difficulty],
    queryFn: () => fetchPRs(
      selectedRepo || undefined, 
      page, 
      perPage, 
      cutoffDate, 
      sortOrder,
      onboardingSuitability || undefined,
      difficulty || undefined,
      undefined, // taskClarity - not used
      undefined  // isReproducible - not used
    ),
  });

  const handleRowClick = (pr: PullRequest) => {
    // Navigate to PR detail page
    // repo format is "owner/repo", so we split it
    const [owner, repo] = pr.repo.split("/");
    navigate(`/pr/${owner}/${repo}/${pr.pr_number}`);
  };

  const totalPages = data ? Math.ceil(data.total / perPage) : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto p-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Pull Request Explorer
          </h1>
          <p className="text-gray-600">
            Browse {data?.total.toLocaleString() || "..."} pull requests across repositories
          </p>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          {/* Row 1: Repository Filter */}
          <div className="flex gap-4 items-center mb-4">
            <label className="text-sm font-medium text-gray-700">
              Repository:
            </label>
            <select
              value={selectedRepo}
              onChange={(e) => {
                setSelectedRepo(e.target.value);
                setPage(1); // Reset to first page when filter changes
              }}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
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
          <div className="flex gap-6 items-center flex-wrap">
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
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="asc">Oldest First (Chronological)</option>
                <option value="desc">Newest First</option>
              </select>
            </div>
          </div>

          {/* Row 3: Classification Filters */}
          <div className="flex gap-6 items-center flex-wrap mt-4 pt-4 border-t">
            <div className="text-sm font-medium text-gray-700 mr-2">
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
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
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
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              >
                <option value="">All</option>
                <option value="trivial">Trivial</option>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </div>

            {/* Clear Filters Button */}
            {(onboardingSuitability || difficulty) && (
              <button
                onClick={() => {
                  setOnboardingSuitability("");
                  setDifficulty("");
                  setPage(1);
                }}
                className="px-3 py-2 text-sm border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors"
              >
                Clear All Filters
              </button>
            )}
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-500 border-r-transparent"></div>
            <p className="mt-2 text-gray-600">Loading PRs...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">
              <strong>Error:</strong> {(error as Error).message}
            </p>
          </div>
        )}

        {/* PR Table */}
        {data && !isLoading && (
          <>
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Repository
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      PR #
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Title
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Suitability
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Difficulty
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Merged Date
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {data.prs.length === 0 ? (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-6 py-8 text-center text-gray-500"
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
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {pr.repo}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-blue-600">
                          #{pr.pr_number}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-900 max-w-md truncate">
                          {pr.title}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
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
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                          {pr.difficulty ? (
                            <Badge variant="secondary">
                              {pr.difficulty}
                            </Badge>
                          ) : (
                            <span className="text-xs text-gray-400">N/A</span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {new Date(pr.merged_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="mt-6 flex items-center justify-between">
              <div className="text-sm text-gray-700">
                Page {page} of {totalPages} ({data.total.toLocaleString()} total
                PRs)
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
