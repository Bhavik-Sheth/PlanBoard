"""
Unit tests for planner/llm.py

All external LLM calls are mocked — tests pass without any API keys.
"""

import importlib
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from planner.llm import LLMConfigError, get_llm, list_providers, PROVIDER_REGISTRY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_env(**overrides) -> dict:
    """Build a minimal env dict for the factory."""
    base = {
        "ACTIVE_PROVIDER": "groq",
        "ACTIVE_MODEL": "llama3-70b-8192",
        "GROQ_API_KEY": "gsk_test_key",
        "OPENAI_API_KEY": "sk_test_key",
        "ANTHROPIC_API_KEY": "ant_test_key",
    }
    base.update(overrides)
    return base


def _mock_chat_class():
    """Return a mock class that behaves like a LangChain chat model."""
    mock_instance = MagicMock()
    mock_instance.invoke.return_value = MagicMock(content="Mocked response")
    mock_class = MagicMock(return_value=mock_instance)
    return mock_class, mock_instance


# ---------------------------------------------------------------------------
# Tests: list_providers
# ---------------------------------------------------------------------------

def test_list_providers_returns_all_registered():
    providers = list_providers()
    assert "groq" in providers
    assert "openai" in providers
    assert "anthropic" in providers


# ---------------------------------------------------------------------------
# Tests: missing / bad config
# ---------------------------------------------------------------------------

def test_get_llm_raises_when_no_provider_set():
    with patch.dict(os.environ, {"ACTIVE_PROVIDER": "", "ACTIVE_MODEL": ""}, clear=False):
        with pytest.raises(LLMConfigError, match="No LLM provider specified"):
            get_llm()


def test_get_llm_raises_on_unknown_provider():
    with patch.dict(os.environ, {"ACTIVE_PROVIDER": "unicorn_llm"}, clear=False):
        with pytest.raises(LLMConfigError, match="Unknown provider"):
            get_llm()


def test_get_llm_raises_when_api_key_missing():
    env = {"ACTIVE_PROVIDER": "groq", "ACTIVE_MODEL": "llama3-70b-8192", "GROQ_API_KEY": ""}
    with patch.dict(os.environ, env, clear=False):
        with pytest.raises(LLMConfigError, match="API key for provider 'groq' not found"):
            get_llm()


# ---------------------------------------------------------------------------
# Tests: correct provider instantiation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider,env_key,model", [
    ("groq",      "GROQ_API_KEY",      "llama3-70b-8192"),
    ("openai",    "OPENAI_API_KEY",    "gpt-4o"),
    ("anthropic", "ANTHROPIC_API_KEY", "claude-3-5-sonnet-20241022"),
])
def test_get_llm_instantiates_correct_class(provider, env_key, model):
    env = {
        "ACTIVE_PROVIDER": provider,
        "ACTIVE_MODEL": model,
        env_key: "test_api_key_value",
    }
    mock_class, mock_instance = _mock_chat_class()

    with patch.dict(os.environ, env, clear=False):
        # Patch importlib.import_module to return a module-like object
        mock_module = MagicMock()
        setattr(mock_module, PROVIDER_REGISTRY[provider]["class_name"], mock_class)

        with patch("importlib.import_module", return_value=mock_module):
            llm = get_llm()

    # The mock class should have been called (i.e., instantiated)
    mock_class.assert_called_once()
    assert llm is mock_instance


def test_get_llm_overrides_via_args():
    """Provider and model passed as args take precedence over env vars."""
    env = {
        "ACTIVE_PROVIDER": "groq",   # would be used if no arg
        "ACTIVE_MODEL": "wrong-model",
        "OPENAI_API_KEY": "sk_test",
    }
    mock_class, mock_instance = _mock_chat_class()

    with patch.dict(os.environ, env, clear=False):
        mock_module = MagicMock()
        setattr(mock_module, "ChatOpenAI", mock_class)

        with patch("importlib.import_module", return_value=mock_module):
            llm = get_llm(provider="openai", model="gpt-4o-mini")

    # ChatOpenAI should have been instantiated with model="gpt-4o-mini"
    call_kwargs = mock_class.call_args.kwargs
    assert call_kwargs.get("model") == "gpt-4o-mini"
    assert llm is mock_instance


def test_get_llm_raises_on_missing_package():
    """If the provider's package isn't installed, raise a clear error."""
    env = {"ACTIVE_PROVIDER": "nvidia", "ACTIVE_MODEL": "some-model", "NVIDIA_API_KEY": "nv_test"}
    with patch.dict(os.environ, env, clear=False):
        with patch("importlib.import_module", side_effect=ImportError("no module")):
            with pytest.raises(LLMConfigError, match="requires the"):
                get_llm()


def test_get_llm_forwards_extra_kwargs():
    """Extra kwargs (temperature, max_tokens) are passed through to the chat class."""
    env = {"ACTIVE_PROVIDER": "openai", "ACTIVE_MODEL": "gpt-4o", "OPENAI_API_KEY": "sk_test"}
    mock_class, _ = _mock_chat_class()

    with patch.dict(os.environ, env, clear=False):
        mock_module = MagicMock()
        setattr(mock_module, "ChatOpenAI", mock_class)

        with patch("importlib.import_module", return_value=mock_module):
            get_llm(temperature=0.2, max_tokens=512)

    call_kwargs = mock_class.call_args.kwargs
    assert call_kwargs.get("temperature") == 0.2
    assert call_kwargs.get("max_tokens") == 512


def test_llm_config_getters_and_setters(tmp_path):
    """Verify that get/set helpers correctly mutate os.environ and update .env file."""
    from planner import llm
    
    # Mock Path.cwd() to return our tmp_path
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        # 1. Initially values from env
        with patch.dict(os.environ, {"ACTIVE_PROVIDER": "groq", "ACTIVE_MODEL": "test-model"}, clear=True):
            assert llm.get_active_provider() == "groq"
            assert llm.get_active_model() == "test-model"
            
            # 2. Update config
            llm.set_active_provider("openai")
            llm.set_active_model("gpt-4o")
            
            # Env should be updated in memory
            assert llm.get_active_provider() == "openai"
            assert llm.get_active_model() == "gpt-4o"
            
            # .env file should be created/updated
            env_file = tmp_path / ".env"
            assert env_file.exists()
            content = env_file.read_text(encoding="utf-8")
            assert "ACTIVE_PROVIDER=openai" in content
            assert "ACTIVE_MODEL=gpt-4o" in content

        # 3. Set API key
        with patch.dict(os.environ, {}, clear=True):
            llm.set_api_key("anthropic", "ant-secret-key")
            assert os.environ["ANTHROPIC_API_KEY"] == "ant-secret-key"
            content = env_file.read_text(encoding="utf-8")
            assert "ANTHROPIC_API_KEY=ant-secret-key" in content
            
            # Status check
            status = llm.get_api_key_status()
            assert status["anthropic"] is True
            assert status["groq"] is False

