"""
LLM client for sending prompts to Claude or OpenAI.

Uses OpenAI Python SDK which supports both OpenAI and Anthropic models,
providing a unified interface for both providers.
"""

from typing import Optional
from openai import OpenAI
from utils.logger import setup_logger

logger = setup_logger(__name__)


class LLMClient:
    """
    Client for interacting with LLM providers.
    
    Uses OpenAI SDK which natively supports both OpenAI and Anthropic models
    through a unified interface.
    """
    
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        temperature: float = 0.0,
        max_tokens: int = 16384
    ):
        """
        Initialize LLM client.
        
        Args:
            provider: LLM provider - 'anthropic' or 'openai'
            model: Model name (e.g., 'claude-sonnet-4-5-20250929', 'claude-3-5-haiku-20241022', 'gpt-4')
            api_key: API key for the provider
            temperature: Sampling temperature (0.0 to 1.0, default 0.0 for deterministic output)
            max_tokens: Maximum tokens in response (default 16384)
                       Claude 4.5 Sonnet supports up to 64000 tokens output
                       Note: max_tokens is required for Anthropic API and cannot be omitted
        
        Raises:
            ValueError: If provider is not supported or API key is missing
        """
        self.provider = provider.lower()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Validate provider
        if self.provider not in ["anthropic", "openai"]:
            raise ValueError(f"Unsupported provider: {provider}. Must be 'anthropic' or 'openai'")
        
        # Validate API key
        if not api_key:
            raise ValueError(f"{provider} API key is required but not provided")
        
        # Initialize OpenAI client
        # For Anthropic, OpenAI SDK uses base_url and api_key
        if self.provider == "anthropic":
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.anthropic.com/v1"
            )
        else:
            self.client = OpenAI(api_key=api_key)
        
        logger.info(f"Initialized LLMClient: provider={provider}, model={model}")
    
    def send_prompt(self, prompt: str, system: Optional[str] = None) -> str:
        """
        Send a prompt to the LLM and get a text response.
        
        This is a simple wrapper that sends text and gets text back.
        No knowledge of PR structure or classification logic.
        
        Args:
            prompt: The prompt text to send
            system: Optional system message (for Anthropic/OpenAI)
        
        Returns:
            Text response from the LLM
        
        Raises:
            Exception: If API call fails (auth, rate limit, etc.)
        """
        try:
            logger.debug(f"Sending prompt to {self.provider} ({len(prompt)} chars)")
            
            # Build messages
            messages = [{"role": "user", "content": prompt}]
            
            # For Anthropic, system messages are handled differently
            # But OpenAI SDK normalizes this for us
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            
            if system:
                # For providers that support system messages
                kwargs["messages"].insert(0, {"role": "system", "content": system})
            
            # Make API call
            response = self.client.chat.completions.create(**kwargs)
            
            # Extract response text
            response_text = response.choices[0].message.content
            
            # Log token usage
            if hasattr(response, "usage") and response.usage:
                logger.info(
                    f"LLM usage: {response.usage.prompt_tokens} prompt tokens, "
                    f"{response.usage.completion_tokens} completion tokens, "
                    f"{response.usage.total_tokens} total"
                )
            
            logger.debug(f"Received response from {self.provider} ({len(response_text)} chars)")
            return response_text
            
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise
    
    def generate_issue(self, prompt: str) -> str:
        """
        Generate a student-facing issue from a PR using LLM.
        
        Similar to send_prompt() but specifically for issue generation.
        Expects plain markdown output (no JSON parsing needed).
        
        Args:
            prompt: The complete prompt including PR context and instructions
        
        Returns:
            str: The generated issue in markdown format (may be empty if LLM returns empty)
        
        Raises:
            Exception: If API call fails (auth, rate limit, network errors, etc.)
        """
        try:
            logger.debug(f"Generating issue with {self.provider} ({len(prompt)} chars)")
            
            # Build messages
            messages = [{"role": "user", "content": prompt}]
            
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            
            # Make API call
            response = self.client.chat.completions.create(**kwargs)
            
            # Extract response text
            response_text = response.choices[0].message.content
            
            # Log token usage
            if hasattr(response, "usage") and response.usage:
                logger.info(
                    f"Issue generation usage: {response.usage.prompt_tokens} prompt tokens, "
                    f"{response.usage.completion_tokens} completion tokens, "
                    f"{response.usage.total_tokens} total"
                )
            
            logger.info(f"Generated issue ({len(response_text) if response_text else 0} chars)")
            
            # Return response as-is, even if empty
            return response_text if response_text else ""
            
        except Exception as e:
            logger.error(f"Issue generation API call failed: {e}")
            raise