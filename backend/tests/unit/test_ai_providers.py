import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from app.ai.factory import ProviderFactory
from app.ai.provider import UnsupportedAIProviderError
from app.ai.openai_provider import OpenAIProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.ollama_provider import OllamaProvider

@pytest.fixture
def mock_openai_settings(monkeypatch):
    monkeypatch.setattr("app.ai.openai_provider.settings.OPENAI_API_KEY", "test-openai-key")
    
@pytest.fixture
def mock_gemini_settings(monkeypatch):
    monkeypatch.setattr("app.ai.gemini_provider.settings.GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr("app.ai.gemini_provider.settings.GEMINI_MODEL", "gemini-3.8-flash")

@pytest.fixture
def mock_ollama_settings(monkeypatch):
    monkeypatch.setattr("app.ai.ollama_provider.settings.OLLAMA_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr("app.ai.ollama_provider.settings.OLLAMA_MODEL", "llama3.2")
    monkeypatch.setattr("app.ai.ollama_provider.settings.OLLAMA_TIMEOUT_SECONDS", 120.0)

# ── Factory Tests ────────────────────────────────────────────────

def test_factory_returns_openai(mock_openai_settings):
    provider = ProviderFactory.get_provider("openai")
    assert isinstance(provider, OpenAIProvider)

def test_factory_returns_gemini(mock_gemini_settings):
    provider = ProviderFactory.get_provider("gemini")
    assert isinstance(provider, GeminiProvider)

@patch("app.ai.ollama_provider.OpenAI")
def test_factory_returns_ollama(mock_openai_cls, mock_ollama_settings):
    provider = ProviderFactory.get_provider("ollama")
    assert isinstance(provider, OllamaProvider)

def test_factory_unsupported_provider():
    with pytest.raises(UnsupportedAIProviderError) as excinfo:
        ProviderFactory.get_provider("claude")
    assert "Unsupported AI provider" in str(excinfo.value)

# ── OpenAI Provider Tests ────────────────────────────────────────

@patch("app.ai.openai_provider.OpenAI")
def test_openai_provider_generate_sql(mock_openai, mock_openai_settings):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "SELECT * FROM test;"
    mock_client.chat.completions.create.return_value = mock_response
    
    provider = OpenAIProvider()
    result = provider.generate_sql([{"role": "user", "content": "hello"}])
    
    assert result == "SELECT * FROM test;"
    mock_client.chat.completions.create.assert_called_once_with(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.0
    )

# ── Gemini Provider Tests ────────────────────────────────────────

@patch("app.ai.gemini_provider.OpenAI")
def test_gemini_provider_generate_sql(mock_openai, mock_gemini_settings):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "SELECT * FROM test;"
    mock_client.chat.completions.create.return_value = mock_response
    
    provider = GeminiProvider()
    result = provider.generate_sql([{"role": "user", "content": "hello"}])
    
    assert result == "SELECT * FROM test;"
    mock_openai.assert_called_once_with(
        api_key="test-gemini-key",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        timeout=15.0
    )
    mock_client.chat.completions.create.assert_called_once_with(
        model="gemini-3.8-flash",
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.0
    )

# ── Ollama Provider Tests ────────────────────────────────────────

@patch("app.ai.ollama_provider.OpenAI")
def test_ollama_provider_instantiation(mock_openai_cls, mock_ollama_settings):
    """OllamaProvider reads OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS from settings."""
    provider = OllamaProvider()
    assert provider.base_url == "http://localhost:11434/v1"
    assert provider.model == "llama3.2"
    assert provider.timeout == 120.0
    mock_openai_cls.assert_called_once_with(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        timeout=120.0,
    )

@patch("app.ai.ollama_provider.OpenAI")
def test_ollama_provider_no_real_api_key(mock_openai_cls, mock_ollama_settings):
    """Ollama uses placeholder api_key='ollama', not a real secret."""
    OllamaProvider()
    call_kwargs = mock_openai_cls.call_args[1]
    assert call_kwargs["api_key"] == "ollama"

@patch("app.ai.ollama_provider.OpenAI")
def test_ollama_provider_uses_local_endpoint(mock_openai_cls, mock_ollama_settings):
    """Ollama connects to localhost, not a cloud API."""
    OllamaProvider()
    call_kwargs = mock_openai_cls.call_args[1]
    assert "localhost" in call_kwargs["base_url"]
    assert "openai.com" not in call_kwargs["base_url"]
    assert "googleapis" not in call_kwargs["base_url"]

@patch("app.ai.ollama_provider.OpenAI")
def test_ollama_provider_generate_sql(mock_openai_cls, mock_ollama_settings):
    """OllamaProvider.generate_sql returns the model's response via the OpenAI-compat API."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "SELECT id FROM users;"
    mock_client.chat.completions.create.return_value = mock_response

    provider = OllamaProvider()
    result = provider.generate_sql([{"role": "user", "content": "show users"}])

    assert result == "SELECT id FROM users;"
    mock_client.chat.completions.create.assert_called_once_with(
        model="llama3.2",
        messages=[{"role": "user", "content": "show users"}],
        temperature=0.0,
    )

@patch("app.ai.ollama_provider.OpenAI")
def test_ollama_provider_custom_model(mock_openai_cls, monkeypatch):
    """Ollama uses OLLAMA_MODEL from settings, allowing user override."""
    monkeypatch.setattr("app.ai.ollama_provider.settings.OLLAMA_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr("app.ai.ollama_provider.settings.OLLAMA_MODEL", "mistral")
    monkeypatch.setattr("app.ai.ollama_provider.settings.OLLAMA_TIMEOUT_SECONDS", 60.0)
    
    provider = OllamaProvider()
    assert provider.model == "mistral"

@patch("app.ai.ollama_provider.OpenAI")
def test_ollama_connection_refused_error(mock_openai_cls, mock_ollama_settings):
    """Connection refused produces a safe user-facing error."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("Connection refused")

    provider = OllamaProvider()
    with pytest.raises(Exception) as excinfo:
        provider.generate_sql([{"role": "user", "content": "test"}])
    assert "Ollama is running" in str(excinfo.value)
    # Ensure no raw stack trace or secrets leak
    assert "localhost:11434" not in str(excinfo.value)

@patch("app.ai.ollama_provider.OpenAI")
def test_ollama_model_not_found_error(mock_openai_cls, mock_ollama_settings):
    """Model not found produces a safe, actionable error."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("model 'llama3.2' not found")

    provider = OllamaProvider()
    with pytest.raises(Exception) as excinfo:
        provider.generate_sql([{"role": "user", "content": "test"}])
    assert "unavailable" in str(excinfo.value)

@patch("app.ai.ollama_provider.OpenAI")
def test_ollama_timeout_error(mock_openai_cls, mock_ollama_settings):
    """Timeout produces a safe user-facing error."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("Request timed out")

    provider = OllamaProvider()
    with pytest.raises(Exception) as excinfo:
        provider.generate_sql([{"role": "user", "content": "test"}])
    assert "timed out" in str(excinfo.value)

@patch("app.ai.ollama_provider.OpenAI")
def test_ollama_generic_error_no_secrets(mock_openai_cls, mock_ollama_settings):
    """Generic errors do not leak secrets or internal paths."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("some unexpected internal SDK error")

    provider = OllamaProvider()
    with pytest.raises(Exception) as excinfo:
        provider.generate_sql([{"role": "user", "content": "test"}])
    error_msg = str(excinfo.value)
    assert "encountered an error" in error_msg
    # Must not contain raw exception details
    assert "SDK" not in error_msg


# ── Provider Availability Service Tests ─────────────────────────

from app.services.provider_availability import (
    _check_openai,
    _check_gemini,
    _check_ollama,
    get_provider_availability,
)

def test_availability_openai_configured(monkeypatch):
    monkeypatch.setattr("app.services.provider_availability.settings.OPENAI_API_KEY", "sk-proj-test1234567890")
    status = _check_openai()
    assert status.id == "openai"
    assert status.available is True
    assert status.reason is None

def test_availability_openai_not_configured(monkeypatch):
    monkeypatch.setattr("app.services.provider_availability.settings.OPENAI_API_KEY", "")
    status = _check_openai()
    assert status.id == "openai"
    assert status.available is False
    assert status.reason == "API key not configured"

def test_availability_gemini_configured(monkeypatch):
    monkeypatch.setattr("app.services.provider_availability.settings.GEMINI_API_KEY", "AIzaSyTest1234567890")
    status = _check_gemini()
    assert status.id == "gemini"
    assert status.available is True
    assert status.reason is None

def test_availability_gemini_not_configured(monkeypatch):
    monkeypatch.setattr("app.services.provider_availability.settings.GEMINI_API_KEY", "")
    status = _check_gemini()
    assert status.id == "gemini"
    assert status.available is False
    assert status.reason == "API key not configured"

@patch("urllib.request.urlopen")
def test_availability_ollama_reachable(mock_urlopen, monkeypatch):
    monkeypatch.setattr("app.services.provider_availability.settings.OLLAMA_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr("app.services.provider_availability.settings.OLLAMA_MODEL", "llama3.2")
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"models": [{"name": "llama3.2:latest"}]}'
    mock_urlopen.return_value.__enter__.return_value = mock_resp
    
    status = _check_ollama()
    assert status.id == "ollama"
    assert status.available is True
    assert status.reason is None

@patch("urllib.request.urlopen")
def test_availability_ollama_unreachable(mock_urlopen, monkeypatch):
    monkeypatch.setattr("app.services.provider_availability.settings.OLLAMA_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr("app.services.provider_availability.settings.OLLAMA_MODEL", "llama3.2")
    mock_urlopen.side_effect = OSError("Connection refused")
    
    status = _check_ollama()
    assert status.id == "ollama"
    assert status.available is False
    assert "not running" in status.reason

def test_get_provider_availability_returns_all_providers(monkeypatch):
    monkeypatch.setattr("app.services.provider_availability.settings.OPENAI_API_KEY", "key1")
    monkeypatch.setattr("app.services.provider_availability.settings.GEMINI_API_KEY", "key2")
    monkeypatch.setattr("app.services.provider_availability.settings.DEFAULT_AI_PROVIDER", "gemini")
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = OSError("not running")
        resp = get_provider_availability()
        assert resp.default_provider == "gemini"
        assert len(resp.providers) == 3
        ids = [p.id for p in resp.providers]
        assert "openai" in ids
        assert "gemini" in ids
        assert "ollama" in ids



