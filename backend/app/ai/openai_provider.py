from typing import List, Dict
from openai import OpenAI
from fastapi import HTTPException
from app.core.config import settings
from app.ai.provider import BaseAIProvider

class OpenAIProvider(BaseAIProvider):
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OpenAI API key is not configured on the server.")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=15.0)
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
            raise Exception(f"OpenAI error: {str(e)}")
