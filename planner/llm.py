"""
llm.py — Provider-agnostic LLM client factory.

Configuration is driven entirely by environment variables (or a .env file):

    ACTIVE_PROVIDER   — one of: groq, openai, anthropic, nvidia
    ACTIVE_MODEL      — model name valid for the chosen provider
    <PROVIDER>_API_KEY — the API key for the chosen provider

Agents never reference a provider by name; they call `get_llm()` and receive
a LangChain BaseChatModel they can invoke uniformly.

How to add a new provider
--------------------------
1. Install the corresponding langchain integration package, e.g.:
       uv add langchain-mistralai
2. Add an entry to the PROVIDER_REGISTRY dict below with:
       - key:         provider name string (lowercase, used in ACTIVE_PROVIDER)
       - env_key:     name of the env var holding the API key
       - import_path: dotted module path of the chat class
       - class_name:  class to instantiate from that module
3. That's it — no other file needs changing.

Example entry:
    "mistral": {
        "env_key": "MISTRAL_API_KEY",
        "import_path": "langchain_mistralai",
        "class_name": "ChatMistralAI",
    },
"""

import importlib
import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel

load_dotenv()

# Registry of supported providers.
# Each entry specifies the env-var key for the API key and the LangChain class.
PROVIDER_REGISTRY: dict[str, dict[str, str]] = {
    "groq": {
        "env_key": "GROQ_API_KEY",
        "import_path": "langchain_groq",
        "class_name": "ChatGroq",
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "import_path": "langchain_openai",
        "class_name": "ChatOpenAI",
    },
    "anthropic": {
        "env_key": "ANTHROPIC_API_KEY",
        "import_path": "langchain_anthropic",
        "class_name": "ChatAnthropic",
    },
    "nvidia": {
        "env_key": "NVIDIA_API_KEY",
        "import_path": "langchain_nvidia_ai_endpoints",
        "class_name": "ChatNVIDIA",
    },
}


class LLMConfigError(Exception):
    """Raised when LLM configuration is missing or invalid."""
    pass


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """
    Return a configured LangChain chat model instance.

    Parameters are optional — if not provided, they are read from environment
    variables (ACTIVE_PROVIDER and ACTIVE_MODEL). Any extra kwargs are passed
    directly to the chat class constructor (e.g. temperature, max_tokens).

    Args:
        provider: Provider name (e.g. "groq", "openai"). Defaults to ACTIVE_PROVIDER env var.
        model:    Model name valid for the provider. Defaults to ACTIVE_MODEL env var.
        **kwargs: Additional arguments forwarded to the chat class.

    Returns:
        A configured BaseChatModel instance ready for use.

    Raises:
        LLMConfigError: If provider or API key is missing/unknown.
    """
    # Resolve provider and model from args or env
    resolved_provider = (provider or os.getenv("ACTIVE_PROVIDER", "")).strip().lower()
    resolved_model = (model or os.getenv("ACTIVE_MODEL", "")).strip()

    if not resolved_provider:
        raise LLMConfigError(
            "No LLM provider specified. Set ACTIVE_PROVIDER in your .env file "
            "or pass provider= to get_llm()."
        )

    if resolved_provider not in PROVIDER_REGISTRY:
        known = ", ".join(PROVIDER_REGISTRY.keys())
        raise LLMConfigError(
            f"Unknown provider '{resolved_provider}'. Known providers: {known}. "
            "To add a new provider, see the instructions in planner/llm.py."
        )

    entry = PROVIDER_REGISTRY[resolved_provider]
    api_key = os.getenv(entry["env_key"], "").strip()

    if not api_key:
        raise LLMConfigError(
            f"API key for provider '{resolved_provider}' not found. "
            f"Set {entry['env_key']} in your .env file."
        )

    # Dynamically import the chat class so we don't hard-require every package
    try:
        module = importlib.import_module(entry["import_path"])
        chat_class = getattr(module, entry["class_name"])
    except ImportError:
        raise LLMConfigError(
            f"Provider '{resolved_provider}' requires the '{entry['import_path']}' package. "
            f"Install it with: uv add {entry['import_path'].replace('_', '-')}"
        ) from None
    except AttributeError:
        raise LLMConfigError(
            f"Class '{entry['class_name']}' not found in '{entry['import_path']}'. "
            "The provider registry entry may be outdated."
        ) from None

    # Build constructor kwargs — include model if provided
    init_kwargs: dict[str, Any] = {entry["env_key"].lower(): api_key, **kwargs}
    if resolved_model:
        init_kwargs["model"] = resolved_model

    return chat_class(**init_kwargs)


def list_providers() -> list[str]:
    """Return the names of all registered providers."""
    return list(PROVIDER_REGISTRY.keys())


def update_env_variable(key: str, value: str) -> None:
    """Update environment variable both in memory and in the .env file."""
    import os
    from pathlib import Path
    
    os.environ[key] = value
    env_path = Path.cwd() / ".env"
    
    lines = []
    updated = False
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip().startswith(f"{key}="):
                lines.append(f"{key}={value}")
                updated = True
            else:
                lines.append(line)
                
    if not updated:
        lines.append(f"{key}={value}")
        
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def get_active_provider() -> str:
    """Return the current active provider."""
    import os
    return os.getenv("ACTIVE_PROVIDER", "")


def get_active_model() -> str:
    """Return the current active model."""
    import os
    return os.getenv("ACTIVE_MODEL", "")


def set_active_provider(provider: str) -> None:
    """Set the active provider and write to .env."""
    update_env_variable("ACTIVE_PROVIDER", provider)


def set_active_model(model: str) -> None:
    """Set the active model and write to .env."""
    update_env_variable("ACTIVE_MODEL", model)


def set_api_key(provider: str, api_key: str) -> None:
    """Set the API key for a provider and write to .env."""
    if provider not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider '{provider}'")
    env_key = PROVIDER_REGISTRY[provider]["env_key"]
    update_env_variable(env_key, api_key)


def get_api_key_status() -> dict[str, bool]:
    """Return a map of provider -> status (True if API key is set)."""
    import os
    status = {}
    for prov, details in PROVIDER_REGISTRY.items():
        key = os.getenv(details["env_key"], "")
        status[prov] = bool(key.strip())
    return status

