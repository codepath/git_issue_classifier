import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ClassificationCard from './ClassificationCard'
import type { PullRequest } from '@/types/pr'

describe('ClassificationCard', () => {
  const mockPR: PullRequest = {
    id: 1,
    repo: 'facebook/react',
    repo_url: 'https://github.com/facebook/react/pull/123',
    pr_number: 123,
    title: 'Fix bug in component',
    body: 'This fixes a bug',
    merged_at: '2024-01-01T00:00:00Z',
    created_at: '2024-01-01T00:00:00Z',
    linked_issue_number: null,
    platform: 'github',
    files: null,
    linked_issue: null,
    issue_comments: null,
    enrichment_status: 'success',
    enrichment_attempted_at: null,
    enrichment_error: null,
    // Classification fields
    onboarding_suitability: 'excellent',
    difficulty: 'easy',
    task_clarity: 'clear',
    is_reproducible: 'highly likely',
    categories: ['bug-fix', 'ui'],
    concepts_taught: ['React hooks', 'CSS styling'],
    prerequisites: ['Basic React knowledge'],
    reasoning: 'This is a well-documented bug fix that demonstrates clear coding patterns.',
    classified_at: '2024-01-01T00:00:00Z',
    llm_payload: null
  }

  it('renders classification data correctly', () => {
    render(<ClassificationCard pr={mockPR} />)

    // Check main heading
    expect(screen.getByText('Classification')).toBeInTheDocument()

    // Check onboarding suitability
    expect(screen.getByText('EXCELLENT')).toBeInTheDocument()

    // Check difficulty, clarity, and reproducibility
    expect(screen.getByText('easy')).toBeInTheDocument()
    expect(screen.getByText('clear')).toBeInTheDocument()
    expect(screen.getByText('highly likely')).toBeInTheDocument()

    // Check categories
    expect(screen.getByText('bug-fix')).toBeInTheDocument()
    expect(screen.getByText('ui')).toBeInTheDocument()

    // Check concepts taught
    expect(screen.getByText('React hooks')).toBeInTheDocument()
    expect(screen.getByText('CSS styling')).toBeInTheDocument()

    // Check prerequisites
    expect(screen.getByText('Basic React knowledge')).toBeInTheDocument()

    // Check reasoning
    expect(screen.getByText(/well-documented bug fix/)).toBeInTheDocument()
  })

  it('shows "no classification" message when PR is not classified', () => {
    const unclassifiedPR = {
      ...mockPR,
      classified_at: null,
      difficulty: null,
      task_clarity: null,
      is_reproducible: null,
      onboarding_suitability: null,
      categories: null,
      concepts_taught: null,
      prerequisites: null,
      reasoning: null
    }
    render(<ClassificationCard pr={unclassifiedPR} />)
    
    expect(screen.getByText('Classification')).toBeInTheDocument()
    expect(screen.getByText(/no classification available/i)).toBeInTheDocument()
  })

  it('applies excellent badge variant for excellent suitability', () => {
    const excellentPR = {
      ...mockPR,
      onboarding_suitability: 'excellent' as const,
    }

    const { container } = render(<ClassificationCard pr={excellentPR} />)
    
    const excellentBadge = screen.getByText('EXCELLENT')
    expect(excellentBadge).toBeInTheDocument()
    // Check that it has green styling (from badge.tsx excellent variant)
    expect(excellentBadge.className).toContain('bg-green-100')
  })

  it('applies poor badge variant for poor suitability', () => {
    const poorPR = {
      ...mockPR,
      onboarding_suitability: 'poor' as const,
    }

    const { container } = render(<ClassificationCard pr={poorPR} />)
    
    const poorBadge = screen.getByText('POOR')
    expect(poorBadge).toBeInTheDocument()
    // Check that it has red styling (from badge.tsx poor variant)
    expect(poorBadge.className).toContain('bg-red-100')
  })

  it('handles empty arrays gracefully', () => {
    const emptyArraysPR = {
      ...mockPR,
      categories: [],
      concepts_taught: [],
      prerequisites: [],
    }

    render(<ClassificationCard pr={emptyArraysPR} />)
    
    // Should still render without errors
    expect(screen.getByText('Classification')).toBeInTheDocument()
    expect(screen.getByText('EXCELLENT')).toBeInTheDocument()
    
    // Categories/concepts/prerequisites sections should not appear
    expect(screen.queryByText('Categories')).not.toBeInTheDocument()
    expect(screen.queryByText('Concepts Taught')).not.toBeInTheDocument()
    expect(screen.queryByText('Prerequisites')).not.toBeInTheDocument()
  })

  it('renders all difficulty levels with appropriate styling', () => {
    const difficulties = ['trivial', 'easy', 'medium', 'hard'] as const
    
    difficulties.forEach((difficulty) => {
      const pr = {
        ...mockPR,
        difficulty,
      }
      
      const { unmount } = render(<ClassificationCard pr={pr} />)
      expect(screen.getByText(difficulty)).toBeInTheDocument()
      unmount()
    })
  })

  it('renders all task clarity levels', () => {
    const clarityLevels = ['clear', 'partial', 'poor'] as const
    
    clarityLevels.forEach((clarity) => {
      const pr = {
        ...mockPR,
        task_clarity: clarity,
      }
      
      const { unmount } = render(<ClassificationCard pr={pr} />)
      expect(screen.getByText(clarity)).toBeInTheDocument()
      unmount()
    })
  })

  it('renders all reproducibility levels', () => {
    const reproducibilityLevels = ['highly likely', 'maybe', 'unclear'] as const
    
    reproducibilityLevels.forEach((reproducibility) => {
      const pr = {
        ...mockPR,
        is_reproducible: reproducibility,
      }
      
      const { unmount } = render(<ClassificationCard pr={pr} />)
      expect(screen.getByText(reproducibility)).toBeInTheDocument()
      unmount()
    })
  })
})

