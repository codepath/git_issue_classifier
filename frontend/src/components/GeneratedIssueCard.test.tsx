import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import GeneratedIssueCard from "./GeneratedIssueCard";
import type { GeneratedIssue } from "../types/pr";

// Mock the IssueGenerationModal component
vi.mock("./IssueGenerationModal", () => ({
  default: () => {
    return <div data-testid="mock-modal">Mock Modal</div>;
  },
}));

// Mock the API module
vi.mock("@/lib/api", () => ({
  fetchGeneratedIssue: vi.fn(),
  fetchPRContext: vi.fn(),
  fetchDefaultIssuePrompt: vi.fn(),
  generateIssue: vi.fn(),
}));

// Helper to wrap component with QueryClient
function renderWithQueryClient(ui: JSX.Element) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe("GeneratedIssueCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders empty state when no issue exists", () => {
    renderWithQueryClient(
      <GeneratedIssueCard repo="facebook/react" prNumber={123} initialIssue={null} />
    );

    expect(screen.getByText("📝 Generated Student Issue")).toBeInTheDocument();
    expect(
      screen.getByText("No issue has been generated for this PR yet.")
    ).toBeInTheDocument();
    expect(screen.getByText("Generate Issue...")).toBeInTheDocument();
  });

  it("renders with issue when issue exists", () => {
    const mockIssue: GeneratedIssue = {
      issue_markdown: "# Test Issue\n\nThis is a test issue.",
      generated_at: new Date().toISOString(),
    };

    renderWithQueryClient(
      <GeneratedIssueCard
        repo="facebook/react"
        prNumber={123}
        initialIssue={mockIssue}
      />
    );

    expect(screen.getByText("📝 Generated Student Issue")).toBeInTheDocument();
    expect(screen.getByText("Copy Issue")).toBeInTheDocument();
    expect(screen.getByText("Regenerate...")).toBeInTheDocument();
    
    // Check that markdown is rendered (look for heading text)
    expect(screen.getByText("Test Issue")).toBeInTheDocument();
  });

  it("copies issue to clipboard when copy button is clicked", async () => {
    const user = userEvent.setup();
    
    // Mock clipboard API
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: writeTextMock,
      },
      writable: true,
      configurable: true,
    });

    // Mock alert
    const alertMock = vi.spyOn(window, "alert").mockImplementation(() => {});

    const mockIssue: GeneratedIssue = {
      issue_markdown: "# Test Issue\n\nThis is a test issue.",
      generated_at: new Date().toISOString(),
    };

    renderWithQueryClient(
      <GeneratedIssueCard
        repo="facebook/react"
        prNumber={123}
        initialIssue={mockIssue}
      />
    );

    const copyButton = screen.getByText("Copy Issue");
    await user.click(copyButton);

    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith(mockIssue.issue_markdown);
      expect(alertMock).toHaveBeenCalledWith("Issue copied to clipboard!");
    });

    alertMock.mockRestore();
  });

  it("opens modal when Generate Issue button is clicked", async () => {
    const user = userEvent.setup();

    renderWithQueryClient(
      <GeneratedIssueCard repo="facebook/react" prNumber={123} initialIssue={null} />
    );

    const generateButton = screen.getByText("Generate Issue...");
    await user.click(generateButton);

    // Check that modal is rendered (we mocked it to show "Mock Modal")
    await waitFor(() => {
      expect(screen.getByTestId("mock-modal")).toBeInTheDocument();
    });
  });

  it("opens modal when Regenerate button is clicked", async () => {
    const user = userEvent.setup();

    const mockIssue: GeneratedIssue = {
      issue_markdown: "# Test Issue",
      generated_at: new Date().toISOString(),
    };

    renderWithQueryClient(
      <GeneratedIssueCard
        repo="facebook/react"
        prNumber={123}
        initialIssue={mockIssue}
      />
    );

    const regenerateButton = screen.getByText("Regenerate...");
    await user.click(regenerateButton);

    // Check that modal is rendered
    await waitFor(() => {
      expect(screen.getByTestId("mock-modal")).toBeInTheDocument();
    });
  });

  it("displays relative timestamp for generated issue", () => {
    // Create a timestamp 2 hours ago
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();

    const mockIssue: GeneratedIssue = {
      issue_markdown: "# Test Issue",
      generated_at: twoHoursAgo,
    };

    renderWithQueryClient(
      <GeneratedIssueCard
        repo="facebook/react"
        prNumber={123}
        initialIssue={mockIssue}
      />
    );

    // Should show "2 hours ago"
    expect(screen.getByText(/2 hours? ago/i)).toBeInTheDocument();
  });
});

