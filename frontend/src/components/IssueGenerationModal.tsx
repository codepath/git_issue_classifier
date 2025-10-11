import { useState, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import * as api from "@/lib/api";
import type { GeneratedIssue } from "@/types/pr";

type Tab = "context" | "prompt" | "preview";

interface IssueGenerationModalProps {
  repo: string;
  prNumber: number;
  onClose: () => void;
  onIssueGenerated: (issue: GeneratedIssue) => void;
}

/**
 * Modal for generating student issues from PRs.
 * 
 * Features:
 * - 3-tab interface: PR Context, Prompt Template, Preview
 * - Editable prompt template (per-generation only)
 * - Generation with loading state
 * - Result view with rendered markdown
 * - Save & copy functionality
 */
function IssueGenerationModal({
  repo,
  prNumber,
  onClose,
  onIssueGenerated,
}: IssueGenerationModalProps) {
  const [activeTab, setActiveTab] = useState<Tab>("prompt");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedIssue, setGeneratedIssue] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch default prompt template
  const { data: defaultPrompt, isLoading: loadingPrompt } = useQuery({
    queryKey: ["default-issue-prompt"],
    queryFn: () => api.fetchDefaultIssuePrompt(),
    staleTime: Infinity, // Prompt template rarely changes
  });

  // Fetch PR context
  const { data: prContext, isLoading: loadingContext } = useQuery({
    queryKey: ["pr-context", repo, prNumber],
    queryFn: () => api.fetchPRContext(repo, prNumber),
  });

  // Local state for editable prompt (starts with default)
  const [promptTemplate, setPromptTemplate] = useState("");

  useEffect(() => {
    if (defaultPrompt && !promptTemplate) {
      setPromptTemplate(defaultPrompt);
    }
  }, [defaultPrompt, promptTemplate]);

  // Build preview (template + context)
  const previewPrompt = useMemo(() => {
    if (!prContext || !promptTemplate) return "";

    return promptTemplate
      .replace("{pr_context}", prContext.pr_context)
      .replace("{classification_info}", prContext.classification_info);
  }, [promptTemplate, prContext]);

  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);

    try {
      // Send custom prompt template to backend (if different from default)
      const customPrompt = promptTemplate !== defaultPrompt ? promptTemplate : undefined;
      const result = await api.generateIssue(repo, prNumber, customPrompt);
      setGeneratedIssue(result.issue_markdown);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error occurred";
      setError(errorMessage);
      console.error("Failed to generate issue:", err);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleGenerateAgain = () => {
    setGeneratedIssue(null);
    setError(null);
    setActiveTab("prompt");
  };

  const handleSave = () => {
    if (generatedIssue) {
      onIssueGenerated({
        issue_markdown: generatedIssue,
        generated_at: new Date().toISOString(),
      });
    } else {
      onClose();
    }
  };

  const copyToClipboard = async () => {
    if (!generatedIssue) return;

    try {
      await navigator.clipboard.writeText(generatedIssue);
      alert("Issue copied to clipboard!");
    } catch (err) {
      console.error("Failed to copy:", err);
      alert("Failed to copy to clipboard. Please try again.");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      onKeyDown={handleKeyDown}
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-5xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-bold text-gray-900">
            Generate Student Issue - PR #{prNumber}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
            aria-label="Close modal"
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
                    onClick={() => setActiveTab("context")}
                    className={`py-3 px-4 border-b-2 font-medium transition-colors ${
                      activeTab === "context"
                        ? "border-blue-600 text-blue-600"
                        : "border-transparent text-gray-600 hover:text-gray-800"
                    }`}
                  >
                    PR Context
                  </button>
                  <button
                    onClick={() => setActiveTab("prompt")}
                    className={`py-3 px-4 border-b-2 font-medium transition-colors ${
                      activeTab === "prompt"
                        ? "border-blue-600 text-blue-600"
                        : "border-transparent text-gray-600 hover:text-gray-800"
                    }`}
                  >
                    Prompt Template
                  </button>
                  <button
                    onClick={() => setActiveTab("preview")}
                    className={`py-3 px-4 border-b-2 font-medium transition-colors ${
                      activeTab === "preview"
                        ? "border-blue-600 text-blue-600"
                        : "border-transparent text-gray-600 hover:text-gray-800"
                    }`}
                  >
                    Preview
                  </button>
                </div>
              </div>

              {/* Tab Content */}
              <div className="flex-1 overflow-auto p-6">
                {activeTab === "context" && (
                  <div>
                    <p className="text-sm text-gray-600 mb-4">
                      This is the PR context that will be sent to the LLM.
                      Review it to ensure all necessary information is included.
                    </p>
                    {loadingContext ? (
                      <div className="text-center py-8">
                        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-500 border-r-transparent"></div>
                        <p className="mt-2 text-gray-600">Loading context...</p>
                      </div>
                    ) : (
                      <textarea
                        value={prContext?.pr_context || "No context available"}
                        readOnly
                        className="w-full h-96 font-mono text-xs p-4 border rounded bg-gray-50 resize-none"
                      />
                    )}
                  </div>
                )}

                {activeTab === "prompt" && (
                  <div>
                    <p className="text-sm text-gray-600 mb-4">
                      Edit the prompt template. Changes only apply to this generation.
                      The template uses <code className="bg-gray-100 px-1 rounded">{"{pr_context}"}</code> and{" "}
                      <code className="bg-gray-100 px-1 rounded">{"{classification_info}"}</code> placeholders.
                    </p>
                    {loadingPrompt ? (
                      <div className="text-center py-8">
                        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-500 border-r-transparent"></div>
                        <p className="mt-2 text-gray-600">Loading prompt template...</p>
                      </div>
                    ) : (
                      <>
                        <textarea
                          value={promptTemplate}
                          onChange={(e) => setPromptTemplate(e.target.value)}
                          className="w-full h-96 font-mono text-xs p-4 border rounded resize-none"
                          placeholder="Loading prompt template..."
                        />
                        <button
                          onClick={() => setPromptTemplate(defaultPrompt || "")}
                          className="mt-2 text-sm text-blue-600 hover:underline"
                        >
                          Restore Default Template
                        </button>
                      </>
                    )}
                  </div>
                )}

                {activeTab === "preview" && (
                  <div>
                    <p className="text-sm text-gray-600 mb-4">
                      Preview of the complete prompt that will be sent to the LLM
                      (template with placeholders filled in).
                    </p>
                    {loadingContext || loadingPrompt ? (
                      <div className="text-center py-8">
                        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-500 border-r-transparent"></div>
                        <p className="mt-2 text-gray-600">Loading preview...</p>
                      </div>
                    ) : (
                      <textarea
                        value={previewPrompt}
                        readOnly
                        className="w-full h-96 font-mono text-xs p-4 border rounded bg-gray-50 resize-none"
                      />
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            /* Generated Issue View */
            <div className="flex-1 overflow-auto p-6">
              <div className="bg-gray-50 rounded-lg border border-gray-200 p-6">
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
                    {generatedIssue}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="mx-6 mb-4 bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-800 text-sm font-medium">Error</p>
              <p className="text-red-700 text-sm mt-1">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t p-6 flex justify-end gap-3">
          {!generatedIssue ? (
            <>
              <button
                onClick={onClose}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleGenerate}
                disabled={isGenerating || !promptTemplate || loadingContext || loadingPrompt}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isGenerating ? (
                  <>
                    <span className="inline-block animate-spin mr-2">⏳</span>
                    Generating...
                  </>
                ) : (
                  "Generate"
                )}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={handleGenerateAgain}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded transition-colors"
              >
                Generate Again
              </button>
              <button
                onClick={copyToClipboard}
                className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
              >
                Copy Issue
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
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

export default IssueGenerationModal;

