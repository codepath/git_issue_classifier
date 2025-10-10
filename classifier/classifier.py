"""
PR Classifier - orchestrates context building, prompting, and LLM classification.

This is the main entry point for classification logic.
"""

import json
import time
from typing import Dict, Any
from classifier.context_builder import build_pr_context
from classifier.prompt_template import CLASSIFICATION_PROMPT
from classifier.llm_client import LLMClient
from utils.logger import setup_logger

logger = setup_logger(__name__)


class Classifier:
    """
    PR classifier that combines context building, prompting, and LLM calls.
    
    Orchestrates the classification pipeline but has no database dependencies -
    takes PR data, returns classification dict.
    """
    
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        max_retries: int = 2,
        retry_delay: float = 2.0
    ):
        """
        Initialize classifier with LLM client.
        
        Args:
            provider: LLM provider ('anthropic' or 'openai')
            model: Model name
            api_key: API key for the provider
            max_retries: Maximum number of retries on parsing failures (default 2)
            retry_delay: Delay between retries in seconds (default 2.0)
        """
        self.llm_client = LLMClient(
            provider=provider,
            model=model,
            api_key=api_key
        )
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        logger.info(f"Initialized Classifier with {provider}/{model}")
    
    def classify_pr(self, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify a pull request using LLM.
        
        This is the main entry point. Takes PR data, returns classification.
        
        Args:
            pr_data: Dict containing PR information (repo, pr_number, title,
                    body, files, linked_issue, issue_comments)
        
        Returns:
            Classification dict with keys:
                - difficulty: str (trivial/easy/medium/hard)
                - categories: List[str]
                - concepts_taught: List[str]
                - prerequisites: List[str]
                - reasoning: str
        
        Raises:
            Exception: If classification fails after all retries
        """
        pr_number = pr_data.get("pr_number", "Unknown")
        logger.info(f"Classifying PR #{pr_number}...")
        
        # Step 1: Build context from PR data
        try:
            pr_context = build_pr_context(pr_data)
            logger.debug(f"Built PR context ({len(pr_context)} chars)")
        except Exception as e:
            logger.error(f"Failed to build PR context: {e}")
            raise
        
        # Step 2: Build full prompt
        full_prompt = CLASSIFICATION_PROMPT.format(pr_context=pr_context)
        
        # Step 3: Call LLM with retry logic
        response_text = None
        for attempt in range(1, self.max_retries + 2):  # +2 because first attempt + max_retries
            try:
                logger.debug(f"LLM call attempt {attempt}/{self.max_retries + 1}")
                
                # Send prompt to LLM (only if we don't have a response from a fix attempt)
                if response_text is None:
                    response_text = self.llm_client.send_prompt(full_prompt)
                
                # Step 4: Parse JSON response
                classification = self._parse_classification_response(response_text)
                
                # Step 5: Validate required fields
                self._validate_classification(classification)
                
                logger.info(
                    f"✓ Successfully classified PR #{pr_number} "
                    f"(difficulty: {classification.get('difficulty')}, "
                    f"attempt: {attempt})"
                )
                return classification
                
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON response (attempt {attempt}): {e}"
                )
                if attempt <= self.max_retries:
                    # Ask the LLM to fix the malformed JSON
                    logger.info("Asking LLM to fix malformed JSON...")
                    fix_prompt = (
                        f"The following JSON is malformed. Please return a corrected, "
                        f"properly formatted JSON object with the same content:\n\n{response_text}"
                    )
                    response_text = self.llm_client.send_prompt(fix_prompt)
                    # Loop will try to parse this fixed response
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed for PR #{pr_number}")
                    raise Exception(f"Failed to parse LLM response after {self.max_retries + 1} attempts") from e
            
            except ValueError as e:
                logger.warning(
                    f"Invalid classification format (attempt {attempt}): {e}"
                )
                if attempt <= self.max_retries:
                    logger.info(f"Retrying in {self.retry_delay}s...")
                    # Reset response_text so we send the original prompt again
                    response_text = None
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed for PR #{pr_number}")
                    raise Exception(f"Invalid classification format after {self.max_retries + 1} attempts") from e
            
            except Exception as e:
                # For other errors (API failures, etc.), don't retry
                logger.error(f"LLM call failed: {e}")
                raise
    
    def _parse_classification_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response.
        
        Handles cases where LLM includes extra text before/after JSON.
        
        Args:
            response_text: Raw response from LLM
        
        Returns:
            Parsed JSON as dict
        
        Raises:
            json.JSONDecodeError: If no valid JSON found
        """
        # Try to parse directly first
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            if end > start:
                json_str = response_text[start:end].strip()
                return json.loads(json_str)
        
        # Try to extract JSON object (find first { and last })
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start >= 0 and end > start:
            json_str = response_text[start:end + 1]
            return json.loads(json_str)
        
        # If all fails, raise original error
        raise json.JSONDecodeError("No valid JSON found in response", response_text, 0)
    
    def _validate_classification(self, classification: Dict[str, Any]) -> None:
        """
        Validate that classification has all required fields with correct types.
        
        Args:
            classification: Parsed classification dict
        
        Raises:
            ValueError: If validation fails
        """
        required_fields = [
            "difficulty",
            "task_clarity",
            "is_reproducible",
            "onboarding_suitability",
            "categories",
            "concepts_taught",
            "prerequisites",
            "reasoning"
        ]
        
        # Check all required fields are present
        missing = [f for f in required_fields if f not in classification]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        
        # Validate difficulty value
        valid_difficulties = ["trivial", "easy", "medium", "hard"]
        if classification["difficulty"] not in valid_difficulties:
            raise ValueError(
                f"Invalid difficulty: {classification['difficulty']}. "
                f"Must be one of: {', '.join(valid_difficulties)}"
            )
        
        # Validate array fields are lists
        for field in ["categories", "concepts_taught", "prerequisites"]:
            if not isinstance(classification[field], list):
                raise ValueError(f"{field} must be a list")
            if len(classification[field]) == 0:
                raise ValueError(f"{field} must not be empty")
        
        # Validate reasoning is a non-empty string
        if not isinstance(classification["reasoning"], str) or not classification["reasoning"].strip():
            raise ValueError("reasoning must be a non-empty string")

