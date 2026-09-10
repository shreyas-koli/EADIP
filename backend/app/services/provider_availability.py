"""
Provider availability checking service.

Performs lightweight, non-inferential checks to determine which AI providers
are currently reachable and configured. Never contacts cloud APIs merely to
check availability — configuration checks are used for online providers, and
a local HTTP probe is used for Ollama.

No API keys or secrets are ever included in the returned data.
"""

import logging
import urllib.request
import urllib.error
import json

from app.core.config import settings
from app.schemas.assistant import ProviderStatus, ProvidersResponse

logger = logging.getLogger(__name__)

_OLLAMA_MODELS_PATH = "/api/tags"


def _check_openai() -> ProviderStatus:
    if settings.OPENAI_API_KEY:
        return ProviderStatus(
            id="openai",
            name="OpenAI",
            mode="online",
            available=True,
            reason=None,
        )
    return ProviderStatus(
        id="openai",
        name="OpenAI",
        mode="online",
        available=False,
        reason="API key not configured",
    )


def _check_gemini() -> ProviderStatus:
    if settings.GEMINI_API_KEY:
        return ProviderStatus(
            id="gemini",
            name="Gemini",
            mode="online",
            available=True,
            reason=None,
        )
    return ProviderStatus(
        id="gemini",
        name="Gemini",
        mode="online",
        available=False,
        reason="API key not configured",
    )


def _probe_ollama() -> tuple[bool, str | None]:
    """
    Probe the local Ollama service.

    Returns (available, reason). Makes one lightweight HTTP request to the
    local Ollama tags endpoint — no inference, no model download.
    """
    # Build base URL without the /v1 suffix for the management API
    base = settings.OLLAMA_BASE_URL
    if base.endswith("/v1"):
        base = base[:-3]
    elif base.endswith("/v1/"):
        base = base[:-4]

    url = base.rstrip("/") + _OLLAMA_MODELS_PATH
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = resp.read()
            data = json.loads(body)
            models = [m.get("name", "") for m in data.get("models", [])]
            configured_model = settings.OLLAMA_MODEL
            # Check if model base name is present (e.g. "llama3.2" matches "llama3.2:latest")
            model_found = any(
                configured_model == m or m.startswith(configured_model + ":")
                for m in models
            )
            if model_found:
                return True, None
            else:
                return False, (
                    f"Model '{configured_model}' is not installed. "
                    f"Run: ollama pull {configured_model}"
                )
    except OSError:
        # Connection refused or unreachable
        return False, "Ollama service is not running"
    except Exception as exc:
        logger.debug(f"Ollama probe failed: {exc}")
        return False, "Ollama service is unavailable"


def _check_ollama() -> ProviderStatus:
    available, reason = _probe_ollama()
    return ProviderStatus(
        id="ollama",
        name="Local Ollama",
        mode="local",
        available=available,
        reason=reason,
    )


def get_provider_availability() -> ProvidersResponse:
    """Return availability status for all known providers without revealing secrets."""
    providers = [
        _check_openai(),
        _check_gemini(),
        _check_ollama(),
    ]
    return ProvidersResponse(
        providers=providers,
        default_provider=settings.DEFAULT_AI_PROVIDER,
    )
