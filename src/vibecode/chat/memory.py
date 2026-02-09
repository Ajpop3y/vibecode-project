"""
Conversation Memory Management for VibeChat.
Handles chat history, context injection, and token management.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class ChatMemory:
    """
    Manages conversation history and context for VibeChat.
    
    Handles:
    - Message history tracking
    - Context window management
    - Token counting and trimming
    """
    
    context: str  # Injected codebase content (from PDF)
    max_tokens: int = 128000  # Default for GPT-4, Claude 3, Gemini Pro
    messages: List[Dict[str, str]] = field(default_factory=list)
    context_tokens: int = 0  # Cached token count for context
    
    def __post_init__(self):
        """Calculate initial context token count."""
        self.context_tokens = self._estimate_tokens(self.context)
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count using character heuristic.
        Same as LLMRenderer: chars // 4
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        return len(text) // 4
    
    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation history.
        
        Args:
            role: 'user' or 'assistant'
            content: Message content
        """
        if role not in ('user', 'assistant'):
            raise ValueError(f"Invalid role: {role}. Must be 'user' or 'assistant'")
        
        self.messages.append({
            'role': role,
            'content': content
        })
    
    def get_messages(self) -> List[Dict[str, str]]:
        """
        Get all messages in the conversation.
        
        Returns:
            List of message dictionaries
        """
        return self.messages.copy()
    
    def get_context_size(self) -> int:
        """
        Calculate total token count including context and messages.
        
        Returns:
            Total estimated tokens
        """
        message_tokens = sum(
            self._estimate_tokens(msg['content']) 
            for msg in self.messages
        )
        return self.context_tokens + message_tokens
    
    def get_available_tokens(self) -> int:
        """
        Get remaining tokens before hitting the limit.
        
        Returns:
            Available tokens
        """
        return max(0, self.max_tokens - self.get_context_size())
    
    def needs_trimming(self) -> bool:
        """
        Check if conversation needs trimming to stay under token limit.
        
        Returns:
            True if trimming is needed
        """
        return self.get_context_size() > self.max_tokens
    
    def trim_if_needed(self, preserve_recent: int = 4) -> bool:
        """
        Trim old messages if exceeding token limit.
        Always preserves the most recent N messages.
        
        Args:
            preserve_recent: Number of recent messages to always keep
            
        Returns:
            True if trimming was performed
        """
        if not self.needs_trimming():
            return False
        
        if len(self.messages) <= preserve_recent:
            # Can't trim further without losing recent context
            return False
        
        # Remove oldest messages until under limit
        while self.needs_trimming() and len(self.messages) > preserve_recent:
            self.messages.pop(0)
        
        return True
    
    def summarize_and_trim(self, preserve_recent: int = 4) -> Optional[str]:
        """
        Create a summary of old messages before trimming.
        This is a placeholder for future enhancement.
        
        Args:
            preserve_recent: Number of recent messages to preserve
            
        Returns:
            Summary of removed messages (currently returns None)
        """
        if not self.needs_trimming():
            return None
        
        # Calculate how many messages to remove
        remove_count = 0
        while self.needs_trimming() and len(self.messages) - remove_count > preserve_recent:
            remove_count += 1
        
        if remove_count == 0:
            return None
        
        # Get messages to be removed
        removed_messages = self.messages[:remove_count]
        
        # Create a simple summary
        summary_parts = []
        for msg in removed_messages:
            role_label = "User" if msg['role'] == 'user' else "Assistant"
            preview = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
            summary_parts.append(f"{role_label}: {preview}")
        
        summary = "Earlier conversation:\n" + "\n".join(summary_parts)
        
        # Perform the trim
        self.messages = self.messages[remove_count:]
        
        # TODO: In future, send this summary to LLM to create a condensed version
        # and inject it as a system message
        
        return summary
    
    def clear(self) -> None:
        """Clear all messages from the conversation."""
        self.messages = []
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get statistics about the current memory state.
        
        Returns:
            Dictionary with stats: message_count, total_tokens, etc.
        """
        return {
            'message_count': len(self.messages),
            'context_tokens': self.context_tokens,
            'message_tokens': self.get_context_size() - self.context_tokens,
            'total_tokens': self.get_context_size(),
            'max_tokens': self.max_tokens,
            'available_tokens': self.get_available_tokens(),
            'usage_percent': (self.get_context_size() / self.max_tokens) * 100
        }


class ContextTier:
    """
    Helper class to determine optimal context injection strategy.
    """
    
    TIER_1_LIMIT = 32000  # Fits in most models
    TIER_2_LIMIT = 128000  # Fits in GPT-4, Claude, Gemini
    
    @staticmethod
    def get_tier(token_count: int) -> str:
        """
        Determine which context tier applies.
        
        Args:
            token_count: Estimated token count of the codebase
            
        Returns:
            Tier description
        """
        if token_count <= ContextTier.TIER_1_LIMIT:
            return "TIER_1_FULL"  # Full injection, fits everywhere
        elif token_count <= ContextTier.TIER_2_LIMIT:
            return "TIER_2_FULL"  # Full injection, fits in large context models
        else:
            return "TIER_3_RAG"  # Need RAG fallback
    
    @staticmethod
    def can_use_full_context(token_count: int, model_limit: int = 128000) -> bool:
        """
        Check if full context injection is feasible.
        
        Args:
            token_count: Estimated codebase tokens
            model_limit: Model's context window limit
            
        Returns:
            True if full context can be used
        """
        # Reserve 30% for conversation and response
        usable_context = model_limit * 0.7
        return token_count <= usable_context
