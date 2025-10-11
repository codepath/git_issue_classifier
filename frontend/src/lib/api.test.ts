import { describe, it, expect, beforeEach, vi } from 'vitest'
import { 
  toggleFavorite, 
  fetchPRs,
  fetchPRContext,
  fetchDefaultIssuePrompt,
  fetchGeneratedIssue,
  generateIssue
} from './api'
import type { PullRequest } from '@/types/pr'

// Mock fetch globally
global.fetch = vi.fn()

describe('toggleFavorite', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should toggle favorite for a PR', async () => {
    const mockPR: PullRequest = {
      id: 1,
      repo: 'facebook/react',
      repo_url: 'https://github.com/facebook/react/pull/12345',
      pr_number: 12345,
      title: 'Test PR',
      body: 'Test description',
      merged_at: '2024-01-01T00:00:00Z',
      created_at: '2023-12-01T00:00:00Z',
      linked_issue_number: null,
      platform: 'github',
      files: null,
      linked_issue: null,
      issue_comments: null,
      enrichment_status: 'success',
      enrichment_attempted_at: null,
      enrichment_error: null,
      is_favorite: true,
    }

    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPR,
    })

    const result = await toggleFavorite('facebook/react', 12345)

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/prs/facebook/react/12345/favorite',
      { method: 'POST' }
    )
    expect(result).toEqual(mockPR)
  })

  it('should throw error when PR not found', async () => {
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
    })

    await expect(toggleFavorite('facebook/react', 99999)).rejects.toThrow(
      'PR not found: facebook/react#99999'
    )
  })

  it('should throw generic error on other failures', async () => {
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    })

    await expect(toggleFavorite('facebook/react', 12345)).rejects.toThrow(
      'Failed to toggle favorite: Internal Server Error'
    )
  })
})

describe('fetchPRs with isFavorite filter', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should include is_favorite=true query parameter when filtering favorites', async () => {
    const mockResponse = {
      prs: [],
      total: 0,
      page: 1,
      per_page: 50,
    }

    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    })

    await fetchPRs(
      undefined,
      1,
      50,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      true // isFavorite
    )

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('is_favorite=true')
    )
  })

  it('should not include is_favorite parameter when undefined', async () => {
    const mockResponse = {
      prs: [],
      total: 0,
      page: 1,
      per_page: 50,
    }

    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    })

    await fetchPRs(
      undefined,
      1,
      50,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined // isFavorite
    )

    const callUrl = (global.fetch as any).mock.calls[0][0]
    expect(callUrl).not.toContain('is_favorite')
  })

  it('should include is_favorite=false when explicitly false', async () => {
    const mockResponse = {
      prs: [],
      total: 0,
      page: 1,
      per_page: 50,
    }

    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    })

    await fetchPRs(
      undefined,
      1,
      50,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      false // isFavorite
    )

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('is_favorite=false')
    )
  })
})

// ============================================================================
// Issue Generation API Tests
// ============================================================================

describe('fetchPRContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should fetch PR context successfully', async () => {
    const mockContext = {
      pr_context: 'PR context string...',
      classification_info: 'Difficulty: easy\nTask Clarity: clear'
    }

    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockContext,
    })

    const result = await fetchPRContext('facebook/react', 12345)

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/prs/facebook%2Freact/12345/context'
    )
    expect(result).toEqual(mockContext)
  })

  it('should throw error when PR not found', async () => {
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
    })

    await expect(fetchPRContext('facebook/react', 99999)).rejects.toThrow(
      'PR not found: facebook/react#99999'
    )
  })
})

describe('fetchDefaultIssuePrompt', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should fetch default prompt template', async () => {
    const mockResponse = {
      prompt_template: 'You are helping create training exercises...'
    }

    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    })

    const result = await fetchDefaultIssuePrompt()

    expect(global.fetch).toHaveBeenCalledWith('/api/prompts/issue-generation')
    expect(result).toBe(mockResponse.prompt_template)
  })

  it('should throw error on fetch failure', async () => {
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: false,
      statusText: 'Internal Server Error',
    })

    await expect(fetchDefaultIssuePrompt()).rejects.toThrow(
      'Failed to fetch prompt template: Internal Server Error'
    )
  })
})

describe('fetchGeneratedIssue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should fetch generated issue when exists', async () => {
    const mockIssue = {
      issue_markdown: '# Test Issue\n\n## Motivation\n...',
      generated_at: '2025-10-11T10:30:00Z'
    }

    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockIssue,
    })

    const result = await fetchGeneratedIssue('facebook/react', 12345)

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/prs/facebook%2Freact/12345/generated-issue'
    )
    expect(result).toEqual(mockIssue)
  })

  it('should return null when no issue generated (404)', async () => {
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
    })

    const result = await fetchGeneratedIssue('facebook/react', 12345)

    expect(result).toBeNull()
  })

  it('should throw error on other failures', async () => {
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    })

    await expect(fetchGeneratedIssue('facebook/react', 12345)).rejects.toThrow(
      'Failed to fetch generated issue: Internal Server Error'
    )
  })
})

describe('generateIssue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should generate issue with default prompt', async () => {
    const mockResponse = {
      issue_markdown: '# Generated Issue\n\n## Motivation\n...',
      generated_at: '2025-10-11T10:30:00Z'
    }

    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    })

    const result = await generateIssue('facebook/react', 12345)

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/prs/facebook%2Freact/12345/generate-issue',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          custom_prompt_template: null,
        }),
      }
    )
    expect(result).toEqual(mockResponse)
  })

  it('should generate issue with custom prompt template', async () => {
    const customPrompt = 'Custom prompt: {pr_context}\n{classification_info}'
    const mockResponse = {
      issue_markdown: '# Custom Issue\n...',
      generated_at: '2025-10-11T10:30:00Z'
    }

    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    })

    const result = await generateIssue('facebook/react', 12345, customPrompt)

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/prs/facebook%2Freact/12345/generate-issue',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          custom_prompt_template: customPrompt,
        }),
      }
    )
    expect(result).toEqual(mockResponse)
  })

  it('should throw error when PR not found', async () => {
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
    })

    await expect(generateIssue('facebook/react', 99999)).rejects.toThrow(
      'PR not found: facebook/react#99999'
    )
  })

  it('should throw error with response text on failure', async () => {
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      text: async () => 'LLM API call failed',
    })

    await expect(generateIssue('facebook/react', 12345)).rejects.toThrow(
      'Failed to generate issue:'
    )
  })
})

