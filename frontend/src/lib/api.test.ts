import { describe, it, expect, beforeEach, vi } from 'vitest'
import { toggleFavorite, fetchPRs } from './api'
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

