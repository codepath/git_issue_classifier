import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { GeneratedIssue } from "@/types/pr";
import IssueGenerationModal from "./IssueGenerationModal";

interface GeneratedIssueCardProps {
  repo: string;
  prNumber: number;
  initialIssue?: GeneratedIssue | null;
}

/**
 * Displays the generated student issue for a PR.
 * 
 * Shows:
 * - Empty state with "Generate Issue..." button if no issue exists
 * - Rendered markdown with copy/regenerate buttons if issue exists
 * - Opens modal for generation/regeneration
 */
function GeneratedIssueCard({ repo, prNumber, initialIssue }: GeneratedIssueCardProps) {
  const [showModal, setShowModal] = useState(false);
  const [issue, setIssue] = useState<GeneratedIssue | null | undefined>(initialIssue);

  const copyToClipboard = async () => {
    if (!issue) return;

    try {
      await navigator.clipboard.writeText(issue.issue_markdown);
      alert("Issue copied to clipboard!");
    } catch (err) {
      console.error("Failed to copy:", err);
      alert("Failed to copy to clipboard. Please try again.");
    }
  };

  const formatTimestamp = (timestamp: string): string => {
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      if (diffMins < 1) return "just now";
      if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? "" : "s"} ago`;
      if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
      if (diffDays < 30) return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
      
      return date.toLocaleDateString();
    } catch {
      return "recently";
    }
  };

  return (
    <>
      <div className="bg-white rounded-lg shadow mb-6">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-gray-900">
              📝 Generated Student Issue
            </h2>

            {issue && (
              <div className="flex gap-2">
                <button
                  onClick={copyToClipboard}
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                >
                  Copy Issue
                </button>
                <button
                  onClick={() => setShowModal(true)}
                  className="px-3 py-1 text-sm bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
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
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Generate Issue...
              </button>
            </div>
          ) : (
            <div>
              <div className="bg-gray-50 rounded-lg border border-gray-200 p-6">
                {/* Render markdown */}
                <div className="prose prose-slate max-w-none">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      // Custom rendering for checkboxes
                      input: (props) => {
                        if (props.type === "checkbox") {
                          return <input {...props} className="mr-2" disabled />;
                        }
                        return <input {...props} />;
                      },
                    }}
                  >
                    {issue.issue_markdown}
                  </ReactMarkdown>
                </div>
              </div>

              <div className="mt-4 text-sm text-gray-500">
                Generated {formatTimestamp(issue.generated_at)}
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
          onIssueGenerated={(newIssue: GeneratedIssue) => {
            setIssue(newIssue);
            setShowModal(false);
          }}
        />
      )}
    </>
  );
}

export default GeneratedIssueCard;

