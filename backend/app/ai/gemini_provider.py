from typing import List, Dict
from openai import OpenAI
from fastapi import HTTPException
from app.core.config import settings
from app.ai.provider import BaseAIProvider

class GeminiProvider(BaseAIProvider):
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="Gemini API key is not configured on the server.")
        self.client = OpenAI(
            api_key=settings.GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            timeout=15.0
        )
        self.model = settings.GEMINI_MODEL

    def generate_sql(self, messages: List[Dict[str, str]]) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Gemini error: {str(e)}")
