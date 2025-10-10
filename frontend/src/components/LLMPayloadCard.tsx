import { useState } from "react";

interface LLMPayloadCardProps {
  llmPayload: string | null | undefined;
  isLoading?: boolean;
}

function LLMPayloadCard({ llmPayload, isLoading = false }: LLMPayloadCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-bold text-gray-900">LLM Classification Payload</h2>
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-solid border-gray-400 border-r-transparent"></div>
        </div>
        <p className="text-sm text-gray-500">Loading payload...</p>
      </div>
    );
  }

  if (!llmPayload) {
    return (
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-lg font-bold text-gray-900 mb-3">
          LLM Classification Payload
        </h2>
        <p className="text-sm text-gray-500 italic">
          LLM payload not available for this PR
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-6">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between mb-3 hover:opacity-70 transition-opacity"
      >
        <h2 className="text-lg font-bold text-gray-900">
          LLM Classification Payload
        </h2>
        <svg
          className={`w-5 h-5 text-gray-600 transition-transform ${
            isExpanded ? "rotate-180" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {isExpanded ? (
        <div className="space-y-2">
          <p className="text-sm text-gray-600">
            This is the exact prompt sent to the LLM for classification. Review it to understand
            why the LLM made its classification decision.
          </p>
          <div className="relative">
            <pre className="mt-2 p-4 bg-gray-50 border border-gray-200 rounded-md text-xs font-mono overflow-auto max-h-[600px] whitespace-pre-wrap break-words">
              {llmPayload}
            </pre>
          </div>
        </div>
      ) : (
        <p className="text-sm text-gray-500">
          Click to expand and view the full prompt sent to the LLM ({llmPayload.length.toLocaleString()} characters)
        </p>
      )}
    </div>
  );
}

export default LLMPayloadCard;

