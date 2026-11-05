"""Dependency factories for extraction providers."""

from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.modules.extraction.providers import AIExtractionProvider, LocalOCRProvider, LocalRuleBasedProvider, OpenAICompatibleProvider, OCRProvider, UnconfiguredAIProvider


def get_ocr_provider(settings: Annotated[Settings, Depends(get_settings)]) -> OCRProvider:
    return LocalOCRProvider()


def get_ai_provider(settings: Annotated[Settings, Depends(get_settings)]) -> AIExtractionProvider:
    if settings.extraction_ai_provider == "openai_compatible":
        if not settings.extraction_ai_api_url or not settings.extraction_ai_api_key:
            return UnconfiguredAIProvider()
        return OpenAICompatibleProvider(settings.extraction_ai_api_url, settings.extraction_ai_api_key, settings.extraction_ai_model, settings.extraction_ai_timeout_seconds)
    return LocalRuleBasedProvider()
