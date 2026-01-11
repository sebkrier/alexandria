from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

from app.models.ai_provider import ProviderName


class AIProviderCreate(BaseModel):
    """Schema for creating an AI provider configuration"""
    provider_name: ProviderName
    display_name: str
    model_id: str
    api_key: str  # Plaintext, will be encrypted before storage


class AIProviderUpdate(BaseModel):
    """Schema for updating an AI provider configuration"""
    display_name: str | None = None
    model_id: str | None = None
    api_key: str | None = None  # Only update if provided
    is_default: bool | None = None
    is_active: bool | None = None


class AIProviderResponse(BaseModel):
    """Schema for AI provider responses"""
    id: UUID
    provider_name: ProviderName
    display_name: str
    model_id: str
    api_key_masked: str  # Masked for display
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AIProviderTestResult(BaseModel):
    """Result of testing an AI provider configuration"""
    success: bool
    message: str


class AvailableProvidersResponse(BaseModel):
    """Information about available AI providers"""
    providers: dict  # provider_name -> {display_name, models, default_model}
