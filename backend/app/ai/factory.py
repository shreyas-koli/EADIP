from app.ai.provider import BaseAIProvider, UnsupportedAIProviderError
from app.ai.openai_provider import OpenAIProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.ollama_provider import OllamaProvider

class ProviderFactory:
    @staticmethod
    def get_provider(provider_name: str) -> BaseAIProvider:
        name = provider_name.lower().strip()
        if name == "openai":
            return OpenAIProvider()
        elif name == "gemini":
            return GeminiProvider()
        elif name == "ollama":
            return OllamaProvider()
        else:
            raise UnsupportedAIProviderError(f"Unsupported AI provider: {provider_name}")
