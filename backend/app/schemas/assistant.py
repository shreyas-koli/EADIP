from pydantic import BaseModel, Field
from typing import List, Optional, Literal


# Valid provider identifiers — validated server-side
AIProvider = Literal["openai", "gemini", "ollama"]


class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the sender: 'user' or 'assistant'")
    content: str = Field(..., description="Content of the message")

class AssistantRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="History of chat messages")
    schema_name: Optional[str] = Field(None, description="Optional currently selected schema for context")
    table_name: Optional[str] = Field(None, description="Optional currently selected table for context")
    provider: Optional[AIProvider] = Field(
        None,
        description="AI provider to use. If omitted, the server default is used.",
    )

class AssistantResponse(BaseModel):
    response: str = Field(..., description="The assistant's markdown response")
    provider_used: str = Field(..., description="The provider that generated this response")


class ProviderStatus(BaseModel):
    id: str = Field(..., description="Provider identifier")
    name: str = Field(..., description="Human-readable provider name")
    mode: Literal["online", "local"] = Field(..., description="Whether the provider is cloud or local")
    available: bool = Field(..., description="Whether the provider is currently available")
    reason: Optional[str] = Field(None, description="Reason for unavailability (safe, no secrets)")


class ProvidersResponse(BaseModel):
    providers: List[ProviderStatus]
    default_provider: str
