"""
LLM Provider Abstraction for VibeChat.
Supports OpenAI, Anthropic, Google Gemini, and Ollama with unified interface.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Iterator, Optional
import os
from ..config import DEFAULT_MODEL_ID


# System prompt template for all providers
SYSTEM_PROMPT_TEMPLATE = """You are VibeChat, an expert AI developer living inside the Vibecode environment.

### 1. CONTEXT AWARENESS
You have the user's full codebase below.
- **Digital Twin:** This is the live code. Trust it.
- **File Tree:** Use this to understand module relationships.

### 2. CITATION PROTOCOL (MANDATORY)
When referencing specific files in your responses, you MUST use the following format:
[[REF: path/to/file.ext]]

For example:
- "The authentication logic is in [[REF: src/auth/login.py]]"
- "Check the configuration in [[REF: config/settings.yaml]]"

IMPORTANT:
- Always use forward slashes in paths
- Use the exact relative paths as they appear in the project tree
- Include the [[REF: ...]] tag whenever you reference file-specific logic

### 3. THE IMPLEMENTATION DRAFTER (CRITICAL)
When you suggest a code fix, DO NOT just show a code block. You MUST wrap it in a `<patch>` tag so the user can apply it with one click.

**Format:**
<patch file="src/path/to/file.py">
def corrected_function():
    return "Fixed Logic"
</patch>

**Rules:**
- The `file` attribute must match the exact path in the context tree
- Content inside the tag should be the complete new content for that function or file section
- Use this for bug fixes, refactors, and new implementations
- Explain what the patch does BEFORE the patch tag

The user has provided you with a complete codebase snapshot. Use it to provide accurate, contextual answers."""


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize the provider.
        
        Args:
            api_key: API key for the provider. If None, will try to get from environment.
            base_url: Optional base URL for API endpoints.
        """
        self.api_key = api_key or self._get_api_key_from_env()
        self.base_url = base_url
        if not self.api_key:
            raise ValueError(f"No API key provided for {self.__class__.__name__}")
    
    @abstractmethod
    def _get_api_key_from_env(self) -> Optional[str]:
        """Get API key from environment variable."""
        pass
    
    @abstractmethod
    def send_message(
        self, 
        messages: List[Dict[str, str]], 
        system_prompt: str = SYSTEM_PROMPT_TEMPLATE,
        temperature: float = 0.7,
        model_id: str = DEFAULT_MODEL_ID
    ) -> str:
        """Send a message to the LLM and wait for response."""
        pass
    
    @abstractmethod
    def stream_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = SYSTEM_PROMPT_TEMPLATE,
        temperature: float = 0.7,
        model_id: str = DEFAULT_MODEL_ID
    ) -> Iterator[str]:
        """Stream a message response from the LLM."""
        pass


class GoogleProvider(BaseLLMProvider):
    """Google Gemini provider."""
    
    def _get_api_key_from_env(self) -> Optional[str]:
        return os.getenv('GOOGLE_API_KEY')
    
    def send_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = SYSTEM_PROMPT_TEMPLATE,
        temperature: float = 0.7,
        model_id: str = DEFAULT_MODEL_ID
    ) -> str:
        """Send message to Google Gemini."""
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ImportError(
                "google-genai not installed. "
                "Install with: pip install google-genai"
            )
        
        client = genai.Client(api_key=self.api_key)
        
        # Convert messages to Gemini format
        # Gemini uses a simpler format - just concatenate with role labels
        full_prompt = system_prompt + "\n\n"
        for msg in messages:
            role_label = "User" if msg['role'] == 'user' else "Assistant"
            full_prompt += f"{role_label}: {msg['content']}\n\n"
        full_prompt += "Assistant:"
        
        response = client.models.generate_content(
            model=model_id,
            contents=full_prompt,
            config=types.GenerateContentConfig(temperature=temperature)
        )
        return response.text
    
    def stream_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = SYSTEM_PROMPT_TEMPLATE,
        temperature: float = 0.7,
        model_id: str = DEFAULT_MODEL_ID
    ) -> Iterator[str]:
        """Stream message from Google Gemini."""
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ImportError("google-genai not installed.")
        
        client = genai.Client(api_key=self.api_key)
        
        # Convert messages to Gemini format
        full_prompt = system_prompt + "\n\n"
        for msg in messages:
            role_label = "User" if msg['role'] == 'user' else "Assistant"
            full_prompt += f"{role_label}: {msg['content']}\n\n"
        full_prompt += "Assistant:"
        
        # Use streaming with the new SDK
        for chunk in client.models.generate_content_stream(
            model=model_id,
            contents=full_prompt,
            config=types.GenerateContentConfig(temperature=temperature)
        ):
            if chunk.text:
                yield chunk.text


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider."""
    
    def _get_api_key_from_env(self) -> Optional[str]:
        return os.getenv('OPENAI_API_KEY')
    
    def send_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = SYSTEM_PROMPT_TEMPLATE,
        temperature: float = 0.7,
        model_id: str = "gpt-4o"
    ) -> str:
        """Send message to OpenAI."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai not installed.")
        
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        # Add system message
        api_messages = [{"role": "system", "content": system_prompt}] + messages
        
        response = client.chat.completions.create(
            model=model_id,
            messages=api_messages,
            temperature=temperature
        )
        return response.choices[0].message.content
    
    def stream_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = SYSTEM_PROMPT_TEMPLATE,
        temperature: float = 0.7,
        model_id: str = "gpt-4o"
    ) -> Iterator[str]:
        """Stream message from OpenAI."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai not installed.")
        
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        # Add system message
        api_messages = [{"role": "system", "content": system_prompt}] + messages
        
        stream = client.chat.completions.create(
            model=model_id,
            messages=api_messages,
            temperature=temperature,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""
    
    def _get_api_key_from_env(self) -> Optional[str]:
        return os.getenv('ANTHROPIC_API_KEY')
    
    def send_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = SYSTEM_PROMPT_TEMPLATE,
        temperature: float = 0.7,
        model_id: str = "claude-3-5-sonnet-20241022"
    ) -> str:
        """Send message to Anthropic."""
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "anthropic not installed. "
                "Install with: pip install anthropic"
            )
        
        client = Anthropic(api_key=self.api_key, base_url=self.base_url)
        
        response = client.messages.create(
            model=model_id,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            temperature=temperature
        )
        return response.content[0].text
    
    def stream_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = SYSTEM_PROMPT_TEMPLATE,
        temperature: float = 0.7,
        model_id: str = "claude-3-5-sonnet-20241022"
    ) -> Iterator[str]:
        """Stream message from Anthropic."""
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "anthropic not installed. "
                "Install with: pip install anthropic"
            )
        
        client = Anthropic(api_key=self.api_key, base_url=self.base_url)
        
        with client.messages.stream(
            model=model_id,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            temperature=temperature
        ) as stream:
            for text in stream.text_stream:
                yield text


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "http://localhost:11434"):
        """
        Initialize Ollama provider.
        
        Args:
            api_key: Not used for Ollama (kept for interface compatibility)
            base_url: Ollama server URL
        """
        self.base_url = base_url
        self.api_key = "ollama"  # Dummy key for compatibility
    
    def _get_api_key_from_env(self) -> Optional[str]:
        return os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    
    def send_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = SYSTEM_PROMPT_TEMPLATE,
        temperature: float = 0.7,
        model_id: str = "llama2"
    ) -> str:
        """Send message to Ollama."""
        import requests
        
        # Add system message to the beginning
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": model_id,
                "messages": full_messages,
                "stream": False,
                "options": {"temperature": temperature}
            }
        )
        response.raise_for_status()
        return response.json()['message']['content']
    
    def stream_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = SYSTEM_PROMPT_TEMPLATE,
        temperature: float = 0.7,
        model_id: str = "llama2"
    ) -> Iterator[str]:
        """Stream message from Ollama."""
        import requests
        import json as json_lib
        
        # Add system message to the beginning
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": model_id,
                "messages": full_messages,
                "stream": True,
                "options": {"temperature": temperature}
            },
            stream=True
        )
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                chunk = json_lib.loads(line)
                if 'message' in chunk and 'content' in chunk['message']:
                    yield chunk['message']['content']


def get_provider(provider_name: str, api_key: Optional[str] = None, base_url: Optional[str] = None) -> BaseLLMProvider:
    """
    Factory function to get the appropriate LLM provider.
    
    Args:
        provider_name: Name of the provider ('google', 'openai', 'anthropic', 'ollama')
        api_key: Optional API key. If None, will try environment variables.
        base_url: Optional base URL for API endpoints.
        
    Returns:
        Initialized provider instance
        
    Raises:
        ValueError: If provider name is invalid
    """
    providers = {
        'google': GoogleProvider,
        'gemini': GoogleProvider,  # Alias
        'openai': OpenAIProvider,
        'gpt': OpenAIProvider,  # Alias
        'anthropic': AnthropicProvider,
        'claude': AnthropicProvider,  # Alias
        'ollama': OllamaProvider,
        'custom': OpenAIProvider, # Default to OpenAI-compatible for custom
    }
    
    provider_class = providers.get(provider_name.lower())
    if not provider_class:
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            f"Valid options: {', '.join(set(providers.keys()))}"
        )
    
    # Ollama provider handles base_url differently (in constructor default), 
    # but we can pass it if provided
    if provider_name.lower() == 'ollama' and base_url:
        return provider_class(api_key=api_key, base_url=base_url)
        
    return provider_class(api_key=api_key, base_url=base_url)
