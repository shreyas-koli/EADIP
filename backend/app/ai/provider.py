from typing import Protocol, List, Dict, Any

class UnsupportedAIProviderError(Exception):
    """Exception raised when an unsupported AI provider is requested."""
    pass

class BaseAIProvider(Protocol):
    """
    Protocol for AI Providers that generate SQL queries from context and user messages.
    """
    def generate_sql(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate a SQL query response based on the provided conversation messages.
        
        Args:
            messages: A list of message dicts with 'role' and 'content'.
            
        Returns:
            The AI-generated response string, typically containing a markdown SQL block.
        """
        ...
