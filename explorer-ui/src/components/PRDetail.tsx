import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchPR } from "@/lib/api";

function PRDetail() {
  const { owner, repo, number } = useParams<{
    owner: string;
    repo: string;
    number: string;
  }>();
  const navigate = useNavigate();

  const fullRepo = `${owner}/${repo}`;
  const prNumber = parseInt(number || "0");

  const { data: pr, isLoading, error } = useQuery({
    queryKey: ["pr", fullRepo, prNumber],
    queryFn: () => fetchPR(fullRepo, prNumber),
    enabled: !!owner && !!repo && !!number,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-blue-500 border-r-transparent"></div>
          <p className="mt-4 text-gray-600">Loading PR details...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="container mx-auto p-6">
          <button
            onClick={() => navigate("/")}
            className="mb-4 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            ← Back to List
          </button>
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <h2 className="text-xl font-bold text-red-800 mb-2">Error</h2>
            <p className="text-red-700">{(error as Error).message}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!pr) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto p-6 max-w-5xl">
        {/* Back Button */}
        <button
          onClick={() => navigate("/")}
          className="mb-4 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
        >
          ← Back to List
        </button>

        {/* PR Header */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                {pr.title}
              </h1>
              <div className="flex items-center gap-3 text-sm text-gray-600">
                <span className="font-medium">{pr.repo}</span>
                <span>•</span>
                <span className="font-mono text-blue-600">#{pr.pr_number}</span>
                <span>•</span>
                <span
                  className={`px-2 py-1 text-xs font-semibold rounded-full ${
                    pr.enrichment_status === "success"
                      ? "bg-green-100 text-green-800"
                      : pr.enrichment_status === "pending"
                      ? "bg-yellow-100 text-yellow-800"
                      : "bg-red-100 text-red-800"
                  }`}
                >
                  {pr.enrichment_status}
                </span>
              </div>
            </div>
          </div>

          {/* Metadata */}
          <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200">
            <div>
              <div className="text-sm font-medium text-gray-500">Created</div>
              <div className="text-sm text-gray-900">
                {new Date(pr.created_at).toLocaleString()}
              </div>
            </div>
            <div>
              <div className="text-sm font-medium text-gray-500">Merged</div>
              <div className="text-sm text-gray-900">
                {new Date(pr.merged_at).toLocaleString()}
              </div>
            </div>
            {pr.files && (
              <>
                <div>
                  <div className="text-sm font-medium text-gray-500">Files Changed</div>
                  <div className="text-sm text-gray-900">
                    {pr.files.summary.total_files} files
                  </div>
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-500">Changes</div>
                  <div className="text-sm">
                    <span className="text-green-600">+{pr.files.summary.total_additions}</span>
                    {" / "}
                    <span className="text-red-600">-{pr.files.summary.total_deletions}</span>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* PR Body */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-bold text-gray-900 mb-3">Description</h2>
          {pr.body ? (
            <div className="text-sm text-gray-700 whitespace-pre-wrap">
              {pr.body}
            </div>
          ) : (
            <p className="text-sm text-gray-500 italic">No description provided</p>
          )}
        </div>

        {/* Linked Issue */}
        {pr.linked_issue && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-3">Linked Issue</h2>
            <div className="border border-gray-200 rounded-md p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="font-mono text-sm text-blue-600">
                  #{pr.linked_issue.number}
                </span>
                <span className="font-medium text-gray-900">
                  {pr.linked_issue.title}
                </span>
                <span
                  className={`ml-auto px-2 py-1 text-xs font-semibold rounded-full ${
                    pr.linked_issue.state === "open"
                      ? "bg-green-100 text-green-800"
                      : "bg-purple-100 text-purple-800"
                  }`}
                >
                  {pr.linked_issue.state}
                </span>
              </div>
              {pr.linked_issue.body && (
                <div className="text-sm text-gray-600 mt-2 line-clamp-3">
                  {pr.linked_issue.body}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Files Changed */}
        {pr.files && pr.files.files.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-3">
              Files Changed ({pr.files.summary.total_files})
            </h2>
            <div className="space-y-2">
              {pr.files.files.map((file, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-3 border border-gray-200 rounded-md hover:bg-gray-50"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-mono text-gray-900 truncate">
                      {file.filename}
                    </div>
                  </div>
                  <div className="flex items-center gap-4 ml-4">
                    <span
                      className={`px-2 py-1 text-xs font-medium rounded ${
                        file.status === "added"
                          ? "bg-green-100 text-green-800"
                          : file.status === "modified"
                          ? "bg-blue-100 text-blue-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {file.status}
                    </span>
                    <div className="text-sm text-gray-600">
                      <span className="text-green-600">+{file.additions}</span>
                      {" / "}
                      <span className="text-red-600">-{file.deletions}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            {pr.files.summary.truncated && (
              <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
                <p className="text-sm text-yellow-800">
                  ⚠️ File list truncated - some files not shown
                </p>
              </div>
            )}
          </div>
        )}

        {/* Issue Comments */}
        {pr.issue_comments && pr.issue_comments.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-3">
              Issue Comments ({pr.issue_comments.length})
            </h2>
            <div className="space-y-4">
              {pr.issue_comments.map((comment) => (
                <div
                  key={comment.id}
                  className="border border-gray-200 rounded-md p-4"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-medium text-sm text-gray-900">
                      {comment.user.login}
                    </span>
                    <span className="text-sm text-gray-500">
                      {new Date(comment.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="text-sm text-gray-700 whitespace-pre-wrap">
                    {comment.body}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Enrichment Error */}
        {pr.enrichment_error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mt-6">
            <h3 className="text-sm font-bold text-red-800 mb-1">Enrichment Error</h3>
            <p className="text-sm text-red-700">{pr.enrichment_error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default PRDetail;
