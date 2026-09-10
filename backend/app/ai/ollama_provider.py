import logging
from typing import List, Dict
from openai import OpenAI
from app.core.config import settings
from app.ai.provider import BaseAIProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseAIProvider):
    """
    AI Provider for local Ollama inference via the OpenAI-compatible API.
    
    Communicates exclusively with a local Ollama server.
    No cloud API key required. No internet access required.
    """

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT_SECONDS
        # Ollama does not require a real API key.
        # The OpenAI SDK requires a non-empty string, so we use a placeholder.
        self.client = OpenAI(
            base_url=self.base_url,
            api_key="ollama",
            timeout=self.timeout,
        )

    def generate_sql(self, messages: List[Dict[str, str]]) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0,
            )
            return response.choices[0].message.content
        except Exception as e:
            error_str = str(e).lower()
            # Connection refused / unreachable
            if "connection" in error_str or "refused" in error_str or "connect" in error_str:
                raise Exception(
                    "Local AI service is unavailable. Please make sure Ollama is running."
                )
            # Model not found
            if "model" in error_str and ("not found" in error_str or "does not exist" in error_str):
                raise Exception(
                    f"The configured local AI model '{self.model}' is unavailable. "
                    f"Please pull it with: ollama pull {self.model}"
                )
            # Timeout
            if "timeout" in error_str or "timed out" in error_str:
                raise Exception(
                    "Local AI inference timed out. The model may be too large or the machine is under heavy load."
                )
            # Generic — log details server-side, return safe message
            logger.error(f"Ollama provider error: {e}")
            raise Exception("Local AI provider encountered an error.")
