import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LLMPayloadCard from "./LLMPayloadCard";

describe("LLMPayloadCard", () => {
  it("renders loading state", () => {
    render(<LLMPayloadCard llmPayload={null} isLoading={true} />);
    
    expect(screen.getByText("LLM Classification Payload")).toBeInTheDocument();
    expect(screen.getByText("Loading payload...")).toBeInTheDocument();
  });

  it("renders null state when no payload available", () => {
    render(<LLMPayloadCard llmPayload={null} isLoading={false} />);
    
    expect(screen.getByText("LLM Classification Payload")).toBeInTheDocument();
    expect(screen.getByText("LLM payload not available for this PR")).toBeInTheDocument();
  });

  it("renders collapsed by default", () => {
    const payload = "This is a test LLM prompt that is quite long...".repeat(10);
    render(<LLMPayloadCard llmPayload={payload} isLoading={false} />);
    
    expect(screen.getByText("LLM Classification Payload")).toBeInTheDocument();
    // Should show character count when collapsed
    expect(screen.getByText(/Click to expand/)).toBeInTheDocument();
    expect(screen.getByText(/characters/)).toBeInTheDocument();
    
    // Prompt should not be visible when collapsed
    expect(screen.queryByText(/This is a test LLM prompt/)).not.toBeInTheDocument();
  });

  it("expands when clicked", async () => {
    const user = userEvent.setup();
    const payload = "Test prompt content for classification";
    render(<LLMPayloadCard llmPayload={payload} isLoading={false} />);
    
    // Click the header to expand
    const header = screen.getByText("LLM Classification Payload");
    await user.click(header);
    
    // Prompt should now be visible
    expect(screen.getByText(/Test prompt content for classification/)).toBeInTheDocument();
    expect(screen.getByText(/This is the exact prompt sent to the LLM/)).toBeInTheDocument();
  });

  it("collapses when clicked again", async () => {
    const user = userEvent.setup();
    const payload = "Test prompt content";
    render(<LLMPayloadCard llmPayload={payload} isLoading={false} />);
    
    const header = screen.getByText("LLM Classification Payload");
    
    // Expand
    await user.click(header);
    expect(screen.getByText("Test prompt content")).toBeInTheDocument();
    
    // Collapse
    await user.click(header);
    expect(screen.queryByText("Test prompt content")).not.toBeInTheDocument();
  });

  it("displays payload in monospace pre tag", async () => {
    const user = userEvent.setup();
    const payload = "Test prompt with\nmultiple lines\nand formatting";
    render(<LLMPayloadCard llmPayload={payload} isLoading={false} />);
    
    // Expand
    const header = screen.getByText("LLM Classification Payload");
    await user.click(header);
    
    // Find the <pre> element
    const preElement = screen.getByText(/Test prompt with/).closest("pre");
    expect(preElement).toBeInTheDocument();
    expect(preElement).toHaveClass("font-mono");
  });

  it("shows character count in collapsed state", () => {
    const payload = "x".repeat(12345);
    render(<LLMPayloadCard llmPayload={payload} isLoading={false} />);
    
    // Should show formatted character count
    expect(screen.getByText(/12,345 characters/)).toBeInTheDocument();
  });
});

