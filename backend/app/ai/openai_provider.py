from typing import List, Dict
from openai import OpenAI
from fastapi import HTTPException
from app.core.config import settings
from app.ai.provider import BaseAIProvider

class OpenAIProvider(BaseAIProvider):
    def __init__(self):
        key = settings.OPENAI_API_KEY
        if not key or not key.strip():
            raise HTTPException(
                status_code=400,
                detail="OpenAI is not configured. Please configure OPENAI_API_KEY on the backend."
            )
        if key.startswith("AIza"):
            raise HTTPException(
                status_code=400,
                detail="OPENAI_API_KEY contains a Gemini API key. Please configure OPENAI_API_KEY with a valid OpenAI key or switch provider to Gemini."
            )
        self.client = OpenAI(api_key=key, timeout=15.0)
        self.model = "gpt-3.5-turbo"

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
            if "429" in error_str or "quota" in error_str.lower() or "credit_balance_exhausted" in error_str.lower():
                raise HTTPException(
                    status_code=400,
                    detail="OpenAI quota exceeded or insufficient credits. Please check your OpenAI account balance."
                )
            if "401" in error_str or "invalid_api_key" in error_str.lower():
                raise HTTPException(
                    status_code=400,
                    detail="OpenAI API key is invalid or unauthorized."
                )
            raise HTTPException(
                status_code=400,
                detail=f"OpenAI error: {error_str}"
            )

