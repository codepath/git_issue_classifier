"""
Tests for classification components.

Keeping tests simple and focused on basic functionality.
"""

import json
import pytest
from unittest.mock import Mock, patch
from classifier.context_builder import build_pr_context
from classifier.llm_client import LLMClient
from classifier.classifier import Classifier
from classifier.prompt_template import CLASSIFICATION_PROMPT


class TestContextBuilder:
    """Tests for context building functionality."""
    
    def test_build_context_minimal_pr(self):
        """Test context building with minimal PR data (no files, no issue)."""
        pr_data = {
            "repo": "facebook/react",
            "pr_number": 123,
            "title": "Fix typo in README",
            "body": "Simple typo fix",
            "merged_at": "2024-01-01T12:00:00Z",
        }
        
        context = build_pr_context(pr_data)
        
        # Should contain all basic sections
        assert "PULL REQUEST METADATA" in context
        assert "PR DESCRIPTION" in context
        assert "CHANGED FILES AND DIFFS" in context
        assert "facebook/react" in context
        assert "123" in context
        assert "Fix typo in README" in context
        assert "Simple typo fix" in context
        assert "(No files information available)" in context
    
    def test_build_context_full_pr(self):
        """Test context building with complete PR data."""
        pr_data = {
            "repo": "facebook/react",
            "pr_number": 456,
            "title": "Add new hook",
            "body": "Fixes #789\n\nAdds a new React hook for state management.",
            "merged_at": "2024-01-01T12:00:00Z",
            "files": [
                {
                    "filename": "src/hooks/useNewHook.js",
                    "status": "added",
                    "additions": 50,
                    "deletions": 0,
                    "patch": "+export function useNewHook() {\n+  return useState(null);\n+}"
                }
            ],
            "linked_issue": {
                "number": 789,
                "title": "Need better state management",
                "state": "closed",
                "body": "We need a better way to manage state."
            },
            "issue_comments": [
                {
                    "user": {"login": "reviewer1"},
                    "created_at": "2024-01-01T10:00:00Z",
                    "body": "Good idea!"
                }
            ]
        }
        
        context = build_pr_context(pr_data)
        
        # Should contain all sections
        assert "PULL REQUEST METADATA" in context
        assert "PR DESCRIPTION" in context
        assert "CHANGED FILES AND DIFFS" in context
        assert "LINKED ISSUE" in context
        assert "ISSUE DISCUSSION" in context
        
        # Check content
        assert "facebook/react" in context
        assert "Add new hook" in context
        assert "useNewHook.js" in context
        assert "Need better state management" in context
        assert "Good idea!" in context


class TestPromptTemplate:
    """Tests for prompt template."""
    
    def test_prompt_has_required_fields(self):
        """Test that prompt template includes all required classification fields."""
        assert "difficulty" in CLASSIFICATION_PROMPT
        assert "categories" in CLASSIFICATION_PROMPT
        assert "concepts_taught" in CLASSIFICATION_PROMPT
        assert "prerequisites" in CLASSIFICATION_PROMPT
        assert "reasoning" in CLASSIFICATION_PROMPT
        assert "trivial" in CLASSIFICATION_PROMPT
        assert "{pr_context}" in CLASSIFICATION_PROMPT  # Format placeholder


class TestLLMClient:
    """Tests for LLM client."""
    
    def test_init_validates_provider(self):
        """Test that initialization validates provider."""
        with pytest.raises(ValueError, match="Unsupported provider"):
            LLMClient(provider="invalid", model="test", api_key="test")
    
    def test_init_validates_api_key(self):
        """Test that initialization validates API key."""
        with pytest.raises(ValueError, match="API key is required"):
            LLMClient(provider="anthropic", model="test", api_key="")
    
    @patch('classifier.llm_client.OpenAI')
    def test_send_prompt_success(self, mock_openai_class):
        """Test successful prompt sending."""
        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test response"))]
        mock_response.usage = Mock(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        # Create client and send prompt
        client = LLMClient(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            api_key="test_key"
        )
        result = client.send_prompt("Test prompt")
        
        # Verify
        assert result == "Test response"
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('classifier.llm_client.OpenAI')
    def test_generate_issue_success(self, mock_openai_class):
        """Test successful issue generation."""
        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_markdown = """# Fix button overflow
        
## Motivation
Users in Japan report that button text is cut off.

## Current Behavior
The button container doesn't expand for longer text.

## Expected Behavior
Button should resize to accommodate text.

## Verification
Test with Japanese locale."""
        
        mock_response.choices = [Mock(message=Mock(content=mock_markdown))]
        mock_response.usage = Mock(
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300
        )
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        # Create client and generate issue
        client = LLMClient(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            api_key="test_key"
        )
        result = client.generate_issue("Generate an issue for this PR...")
        
        # Verify
        assert result == mock_markdown
        assert "# Fix button overflow" in result
        assert "## Motivation" in result
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('classifier.llm_client.OpenAI')
    def test_generate_issue_empty_response(self, mock_openai_class):
        """Test issue generation with empty LLM response."""
        # Mock OpenAI client to return empty string
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=""))]
        mock_response.usage = Mock(
            prompt_tokens=100,
            completion_tokens=0,
            total_tokens=100
        )
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        # Create client and generate issue
        client = LLMClient(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            api_key="test_key"
        )
        result = client.generate_issue("Generate an issue...")
        
        # Should return empty string without error
        assert result == ""
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('classifier.llm_client.OpenAI')
    def test_generate_issue_api_error(self, mock_openai_class):
        """Test issue generation with API error."""
        # Mock OpenAI client to raise an exception
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API rate limit exceeded")
        mock_openai_class.return_value = mock_client
        
        # Create client and generate issue
        client = LLMClient(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            api_key="test_key"
        )
        
        # Should raise the exception
        with pytest.raises(Exception, match="API rate limit exceeded"):
            client.generate_issue("Generate an issue...")


class TestClassifier:
    """Tests for classifier."""
    
    @patch('classifier.classifier.LLMClient')
    def test_classify_pr_success(self, mock_llm_class):
        """Test successful PR classification."""
        # Mock LLM client to return valid classification JSON
        mock_llm = Mock()
        classification_response = json.dumps({
            "difficulty": "medium",
            "categories": ["feature", "api"],
            "concepts_taught": ["React hooks", "State management"],
            "prerequisites": ["Basic React knowledge"],
            "reasoning": "This PR adds a new hook for state management."
        })
        mock_llm.send_prompt.return_value = classification_response
        mock_llm_class.return_value = mock_llm
        
        # Create classifier
        classifier = Classifier(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            api_key="test_key"
        )
        
        # Classify PR
        pr_data = {
            "pr_number": 123,
            "repo": "facebook/react",
            "title": "Add useNewHook",
            "body": "New hook for state",
            "merged_at": "2024-01-01T12:00:00Z",
            "files": []
        }
        
        result = classifier.classify_pr(pr_data)
        
        # Verify
        assert result["difficulty"] == "medium"
        assert "feature" in result["categories"]
        assert "React hooks" in result["concepts_taught"]
        assert "Basic React knowledge" in result["prerequisites"]
        assert len(result["reasoning"]) > 0
    
    @patch('classifier.classifier.LLMClient')
    def test_classify_pr_validates_response(self, mock_llm_class):
        """Test that classifier validates LLM response."""
        # Mock LLM client to return invalid classification (missing field)
        mock_llm = Mock()
        invalid_response = json.dumps({
            "difficulty": "medium",
            "categories": ["feature"],
            # Missing concepts_taught, prerequisites, reasoning
        })
        mock_llm.send_prompt.return_value = invalid_response
        mock_llm_class.return_value = mock_llm
        
        # Create classifier
        classifier = Classifier(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            api_key="test_key",
            max_retries=0  # Don't retry for this test
        )
        
        # Classify PR - should raise exception
        pr_data = {
            "pr_number": 123,
            "repo": "facebook/react",
            "title": "Test PR",
            "body": "Test",
            "merged_at": "2024-01-01T12:00:00Z",
            "files": []
        }
        
        with pytest.raises(Exception, match="Invalid classification format"):
            classifier.classify_pr(pr_data)
    
    @patch('classifier.classifier.LLMClient')
    def test_classify_pr_parses_json_from_markdown(self, mock_llm_class):
        """Test that classifier can parse JSON from markdown code blocks."""
        # Mock LLM client to return JSON wrapped in markdown
        mock_llm = Mock()
        classification_data = {
            "difficulty": "easy",
            "categories": ["bug-fix"],
            "concepts_taught": ["Debugging"],
            "prerequisites": ["Basic programming"],
            "reasoning": "Simple bug fix."
        }
        markdown_response = f"Here is the classification:\n```json\n{json.dumps(classification_data)}\n```"
        mock_llm.send_prompt.return_value = markdown_response
        mock_llm_class.return_value = mock_llm
        
        # Create classifier
        classifier = Classifier(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            api_key="test_key"
        )
        
        # Classify PR
        pr_data = {
            "pr_number": 123,
            "repo": "facebook/react",
            "title": "Fix bug",
            "body": "Fixes a bug",
            "merged_at": "2024-01-01T12:00:00Z",
            "files": []
        }
        
        result = classifier.classify_pr(pr_data)
        
        # Verify it parsed correctly
        assert result["difficulty"] == "easy"
        assert "bug-fix" in result["categories"]

