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
    monkeypatch.setattr("app.ai.openai_provider.settings.OPENAI_API_KEY", "sk-test-openai-key")
    
@pytest.fixture
def mock_gemini_settings(monkeypatch):
    monkeypatch.setattr("app.ai.gemini_provider.settings.GEMINI_API_KEY", "AIzaSy-test-gemini-key")
    monkeypatch.setattr("app.ai.gemini_provider.settings.GEMINI_MODEL", "gemini-3.8-flash")

@pytest.fixture
def mock_ollama_settings(monkeypatch):
    monkeypatch.setattr("app.ai.ollama_provider.settings.OLLAMA_BASE_URL", "http://localhost:11434")
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

def test_openai_missing_api_key_returns_400(monkeypatch):
    monkeypatch.setattr("app.ai.openai_provider.settings.OPENAI_API_KEY", None)
    with pytest.raises(HTTPException) as exc:
        OpenAIProvider()
    assert exc.value.status_code == 400
    assert "OpenAI is not configured" in exc.value.detail

def test_gemini_key_in_openai_variable_detected(monkeypatch):
    monkeypatch.setattr("app.ai.openai_provider.settings.OPENAI_API_KEY", "AIzaSyFakeGeminiKey123")
    with pytest.raises(HTTPException) as exc:
        OpenAIProvider()
    assert exc.value.status_code == 400
    assert "contains a Gemini API key" in exc.value.detail

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
        api_key="AIzaSy-test-gemini-key",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        timeout=15.0
    )
    mock_client.chat.completions.create.assert_called_once_with(
        model="gemini-3.8-flash",
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.0
    )

def test_gemini_missing_api_key_returns_400(monkeypatch):
    monkeypatch.setattr("app.ai.gemini_provider.settings.GEMINI_API_KEY", None)
    with pytest.raises(HTTPException) as exc:
        GeminiProvider()
    assert exc.value.status_code == 400
    assert "Gemini is not configured" in exc.value.detail

def test_openai_key_in_gemini_variable_detected(monkeypatch):
    monkeypatch.setattr("app.ai.gemini_provider.settings.GEMINI_API_KEY", "sk-proj-FakeOpenAIKey123")
    with pytest.raises(HTTPException) as exc:
        GeminiProvider()
    assert exc.value.status_code == 400
    assert "contains an OpenAI API key" in exc.value.detail

# ── Ollama Provider Tests ────────────────────────────────────────

@patch("app.ai.ollama_provider.OpenAI")
def test_ollama_provider_instantiation(mock_openai_cls, mock_ollama_settings):
    """OllamaProvider reads OLLAMA_BASE_URL and appends /v1 for SDK compatibility."""
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
def test_ollama_connection_refused_error(mock_openai_cls, mock_ollama_settings):
    """Connection refused produces a safe 400 HTTP exception."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("Connection refused")

    provider = OllamaProvider()
    with pytest.raises(HTTPException) as excinfo:
        provider.generate_sql([{"role": "user", "content": "test"}])
    assert excinfo.value.status_code == 400
    assert "Ollama is running" in excinfo.value.detail

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
    assert "OPENAI_API_KEY is not set" in status.reason

def test_availability_openai_gemini_key_detected(monkeypatch):
    monkeypatch.setattr("app.services.provider_availability.settings.OPENAI_API_KEY", "AIzaSyFakeKey")
    status = _check_openai()
    assert status.id == "openai"
    assert status.available is False
    assert "contains a Gemini API key" in status.reason

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
    assert "GEMINI_API_KEY is not set" in status.reason

def test_availability_gemini_openai_key_detected(monkeypatch):
    monkeypatch.setattr("app.services.provider_availability.settings.GEMINI_API_KEY", "sk-proj-FakeKey")
    status = _check_gemini()
    assert status.id == "gemini"
    assert status.available is False
    assert "contains an OpenAI API key" in status.reason

@patch("urllib.request.urlopen")
def test_availability_ollama_reachable(mock_urlopen, monkeypatch):
    monkeypatch.setattr("app.services.provider_availability.settings.OLLAMA_BASE_URL", "http://localhost:11434")
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
    monkeypatch.setattr("app.services.provider_availability.settings.OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setattr("app.services.provider_availability.settings.OLLAMA_MODEL", "llama3.2")
    mock_urlopen.side_effect = OSError("Connection refused")
    
    status = _check_ollama()
    assert status.id == "ollama"
    assert status.available is False
    assert "not running" in status.reason

def test_get_provider_availability_returns_all_providers(monkeypatch):
    monkeypatch.setattr("app.services.provider_availability.settings.OPENAI_API_KEY", "sk-key1")
    monkeypatch.setattr("app.services.provider_availability.settings.GEMINI_API_KEY", "AIza-key2")
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

# ── Service Process Assistant Chat Tests ────────────────────────

from app.services.assistant_service import process_assistant_chat
from app.schemas.assistant import AssistantRequest

@patch("app.services.assistant_service.ProviderFactory.get_provider")
def test_process_assistant_chat_respects_explicit_provider(mock_get_provider, mock_gemini_settings):
    mock_provider = MagicMock()
    mock_provider.generate_sql.return_value = "SELECT 1;"
    mock_get_provider.return_value = mock_provider
    mock_engine = MagicMock()

    req = AssistantRequest(messages=[{"role": "user", "content": "hi"}], provider="gemini")
    resp = process_assistant_chat(mock_engine, req)

    mock_get_provider.assert_called_once_with("gemini")
    assert resp.provider_used == "gemini"
    assert resp.response == "SELECT 1;"

@patch("app.services.assistant_service.ProviderFactory.get_provider")
def test_process_assistant_chat_no_silent_fallback_on_error(mock_get_provider, mock_gemini_settings):
    mock_provider = MagicMock()
    mock_provider.generate_sql.side_effect = HTTPException(status_code=400, detail="Gemini rate limit exceeded")
    mock_get_provider.return_value = mock_provider
    mock_engine = MagicMock()

    req = AssistantRequest(messages=[{"role": "user", "content": "hi"}], provider="gemini")
    with pytest.raises(HTTPException) as exc:
        process_assistant_chat(mock_engine, req)

    assert exc.value.status_code == 400
    assert "Gemini rate limit exceeded" in exc.value.detail
    # Never called ProviderFactory again for fallback
    assert mock_get_provider.call_count == 1




