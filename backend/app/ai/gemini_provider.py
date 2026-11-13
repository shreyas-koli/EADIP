from typing import List, Dict
from openai import OpenAI
from fastapi import HTTPException
from app.core.config import settings
from app.ai.provider import BaseAIProvider

class GeminiProvider(BaseAIProvider):
    def __init__(self):
        key = settings.GEMINI_API_KEY
        if not key or not key.strip():
            raise HTTPException(
                status_code=400,
                detail="Gemini is not configured. Please configure GEMINI_API_KEY on the backend."
            )
        if key.startswith("sk-"):
            raise HTTPException(
                status_code=400,
                detail="GEMINI_API_KEY contains an OpenAI API key. Please configure GEMINI_API_KEY with a valid Gemini key or switch provider to OpenAI."
            )
        self.client = OpenAI(
            api_key=key,
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
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower() or "resource_exhausted" in error_str.lower():
                raise HTTPException(
                    status_code=400,
                    detail="Gemini quota exceeded or rate limit reached. Please check your Gemini account or quota."
                )
            if "401" in error_str or "403" in error_str or "invalid" in error_str.lower():
                raise HTTPException(
                    status_code=400,
                    detail="Gemini API key is invalid or unauthorized."
                )
            raise HTTPException(
                status_code=400,
                detail=f"Gemini error: {error_str}"
            )

