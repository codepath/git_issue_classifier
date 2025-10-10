import type { PullRequest } from "@/types/pr";
import { Badge } from "./ui/badge";

interface ClassificationCardProps {
  pr: PullRequest;
}

function ClassificationCard({ pr }: ClassificationCardProps) {
  // Check if PR is classified (has classified_at timestamp)
  const isClassified = pr.classified_at != null;
  
  if (!isClassified) {
    return (
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-lg font-bold text-gray-900 mb-3">
          Classification
        </h2>
        <p className="text-sm text-gray-500 italic">
          No classification available for this PR
        </p>
      </div>
    );
  }

  // Helper to get difficulty badge color
  const getDifficultyVariant = (difficulty: string) => {
    switch (difficulty) {
      case "trivial":
        return "success";
      case "easy":
        return "success";
      case "medium":
        return "warning";
      case "hard":
        return "destructive";
      default:
        return "secondary";
    }
  };

  // Helper to get task clarity badge color
  const getClarityVariant = (clarity: string) => {
    switch (clarity) {
      case "clear":
        return "success";
      case "partial":
        return "warning";
      case "poor":
        return "destructive";
      default:
        return "secondary";
    }
  };

  // Helper to get reproducibility badge color
  const getReproducibilityVariant = (reproducibility: string) => {
    switch (reproducibility) {
      case "highly likely":
        return "success";
      case "maybe":
        return "warning";
      case "unclear":
        return "destructive";
      default:
        return "secondary";
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-6">
      <h2 className="text-lg font-bold text-gray-900 mb-4">
        Classification
      </h2>

      {/* Onboarding Suitability - Prominent Display */}
      <div className="mb-6 p-4 bg-gray-50 rounded-md">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-gray-700">
            Onboarding Suitability:
          </span>
          <Badge
            variant={
              pr.onboarding_suitability === "excellent"
                ? "excellent"
                : "poor"
            }
            className="text-sm px-3 py-1"
          >
            {pr.onboarding_suitability?.toUpperCase()}
          </Badge>
        </div>
      </div>

      {/* Classification Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div>
          <div className="text-sm font-medium text-gray-500 mb-2">
            Difficulty
          </div>
          <Badge variant={getDifficultyVariant(pr.difficulty || "")}>
            {pr.difficulty}
          </Badge>
        </div>
        <div>
          <div className="text-sm font-medium text-gray-500 mb-2">
            Task Clarity
          </div>
          <Badge variant={getClarityVariant(pr.task_clarity || "")}>
            {pr.task_clarity}
          </Badge>
        </div>
        <div>
          <div className="text-sm font-medium text-gray-500 mb-2">
            Reproducibility
          </div>
          <Badge
            variant={getReproducibilityVariant(pr.is_reproducible || "")}
          >
            {pr.is_reproducible}
          </Badge>
        </div>
      </div>

      {/* Categories */}
      {pr.categories && pr.categories.length > 0 && (
        <div className="mb-4">
          <div className="text-sm font-medium text-gray-700 mb-2">
            Categories
          </div>
          <div className="flex flex-wrap gap-2">
            {pr.categories.map((category, idx) => (
              <Badge key={idx} variant="secondary">
                {category}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Concepts Taught */}
      {pr.concepts_taught && pr.concepts_taught.length > 0 && (
        <div className="mb-4">
          <div className="text-sm font-medium text-gray-700 mb-2">
            Concepts Taught
          </div>
          <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
            {pr.concepts_taught.map((concept, idx) => (
              <li key={idx}>{concept}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Prerequisites */}
      {pr.prerequisites && pr.prerequisites.length > 0 && (
        <div className="mb-4">
          <div className="text-sm font-medium text-gray-700 mb-2">
            Prerequisites
          </div>
          <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
            {pr.prerequisites.map((prereq, idx) => (
              <li key={idx}>{prereq}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Reasoning */}
      {pr.reasoning && (
        <div className="pt-4 border-t border-gray-200">
          <div className="text-sm font-medium text-gray-700 mb-2">
            Reasoning
          </div>
          <p className="text-sm text-gray-600 whitespace-pre-wrap">
            {pr.reasoning}
          </p>
        </div>
      )}
    </div>
  );
}

export default ClassificationCard;

