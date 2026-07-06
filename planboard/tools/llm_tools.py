"""
planboard/tools/llm_tools.py — LLM client factory and request handlers.
"""

import os
import json
import importlib
from typing import Generator, Any
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage
from planboard.tools.exceptions import LLMCallError, LLMParseError

# Load environment variables from the project root .env file if it exists
from pathlib import Path

def find_project_root() -> Path:
    """Find the project root containing PLANBOARD/ by searching upwards from CWD."""
    curr = Path.cwd().resolve()
    for parent in [curr] + list(curr.parents):
        if (parent / "PLANBOARD").exists() and (parent / "PLANBOARD").is_dir():
            return parent
    return curr

load_dotenv(dotenv_path=find_project_root() / ".env", override=True)

# Registry of supported providers
PROVIDER_MAP: dict[str, dict[str, Any]] = {
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
    "ollama": {
        "env_key": None,  # Usually doesn't require key, but can be set
        "import_path": "langchain_community.chat_models",
        "class_name": "ChatOllama",
    },
    "gemini": {
        "env_key": "GOOGLE_API_KEY",
        "import_path": "langchain_google_genai",
        "class_name": "ChatGoogleGenerativeAI",
    },
    "openai-compatible": {
        "env_key": "OPENAI_COMPATIBLE_API_KEY",
        "import_path": "langchain_openai",
        "class_name": "ChatOpenAI",
    }
}

def get_llm_client(**kwargs: Any) -> BaseChatModel:
    """
    Reads provider config from environment (or arguments) and instantiates the correct LangChain chat client.
    Supported: groq, openai, anthropic, nvidia, ollama, gemini, openai-compatible.
    """
    provider = kwargs.pop("provider", None) or os.getenv("ACTIVE_PROVIDER") or os.getenv("PROVIDER")
    model = kwargs.pop("model", None) or os.getenv("ACTIVE_MODEL") or os.getenv("MODEL")
    
    if not provider:
        raise LLMCallError("No LLM provider specified. Set ACTIVE_PROVIDER or PROVIDER in your environment.")
        
    provider = provider.strip().lower()
    
    if provider not in PROVIDER_MAP:
        known = ", ".join(PROVIDER_MAP.keys())
        raise LLMCallError(f"Unknown LLM provider '{provider}'. Supported: {known}")
        
    entry = PROVIDER_MAP[provider]
    
    # Check for API key if required
    api_key = ""
    if entry["env_key"]:
        api_key = os.getenv(entry["env_key"], "").strip()
        if not api_key:
            raise LLMCallError(f"API key for provider '{provider}' ({entry['env_key']}) is missing.")
            
    # Try importing the package dynamically
    import_path = entry["import_path"]
    class_name = entry["class_name"]
    
    try:
        module = importlib.import_module(import_path)
        chat_class = getattr(module, class_name)
    except ImportError:
        # Fallback for ollama community imports if needed
        if provider == "ollama":
            try:
                module = importlib.import_module("langchain_ollama")
                chat_class = getattr(module, "ChatOllama")
            except ImportError:
                raise LLMCallError("Provider 'ollama' requires the 'langchain-community' or 'langchain-ollama' package.")
        else:
            raise LLMCallError(f"Provider '{provider}' requires package '{import_path}'. Please install it.")
    except AttributeError:
        raise LLMCallError(f"Class '{class_name}' not found in '{import_path}'.")
        
    # Build initialization kwargs
    init_kwargs = {**kwargs}
    if entry["env_key"] and api_key:
        if provider == "openai-compatible":
            init_kwargs["api_key"] = api_key
            init_kwargs["openai_api_key"] = api_key
        else:
            arg_name = entry["env_key"].lower()
            init_kwargs[arg_name] = api_key
            
    if provider == "openai-compatible":
        base_url = os.getenv("OPENAI_COMPATIBLE_API_BASE") or os.getenv("OPENAI_COMPATIBLE_BASE_URL")
        if not base_url:
            raise LLMCallError(
                "Base URL for provider 'openai-compatible' (OPENAI_COMPATIBLE_API_BASE) is missing. "
                "Configure it via: /config baseurl <url>"
            )
        init_kwargs["openai_api_base"] = base_url
        init_kwargs["base_url"] = base_url
        
    if model:
        init_kwargs["model"] = model.strip()
        
    try:
        return chat_class(**init_kwargs)
    except Exception as exc:
        raise LLMCallError(f"Failed to instantiate LLM client for provider '{provider}': {exc}")

get_llm = get_llm_client

def llm_call(prompt: str, system: str = "", max_tokens: int = 4000) -> str:
    """
    Single LLM call, returns response text.
    Raises LLMCallError on failure (timeout, API error, empty response).
    """
    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))
    
    try:
        # Instantiate client with max_tokens if applicable (or pass extra kwargs)
        # Note: some providers use max_tokens, others use max_output_tokens (e.g. ChatAnthropic)
        client = get_llm_client(max_tokens=max_tokens)
        response = client.invoke(messages)
        content = response.content
        if not content:
            raise LLMCallError("LLM response was empty.")
        return str(content)
    except Exception as exc:
        if isinstance(exc, LLMCallError):
            raise exc
        raise LLMCallError(f"LLM call failed: {exc}")

def llm_call_with_retry(prompt: str, system: str = "", max_retries: int = 1) -> str:
    """
    Wraps llm_call with retries on LLMCallError.
    On failure after max_retries, raises LLMCallError.
    """
    attempts = max_retries + 1
    last_err = None
    for attempt in range(attempts):
        try:
            return llm_call(prompt, system)
        except LLMCallError as exc:
            last_err = exc
            if attempt < max_retries:
                # Retry
                continue
    raise LLMCallError(f"LLM call failed after {attempts} attempts. Last error: {last_err}")

def llm_call_json(prompt: str, system: str = "") -> dict:
    """
    Same as llm_call but parses response as JSON.
    Strips markdown fences before parsing.
    """
    response_text = llm_call(prompt, system)
    
    # Strip markdown fences
    t = response_text.strip()
    if t.startswith("```json"):
        t = t[7:]
    elif t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    t = t.strip()
    
    try:
        return json.loads(t)
    except json.JSONDecodeError as exc:
        raise LLMParseError(f"Failed to parse LLM response as JSON. Content: {response_text}. Error: {exc}")

def stream_llm_call(prompt: str, system: str = "") -> Generator[str, None, None]:
    """
    Streaming version of llm_call — yields text chunks as they arrive.
    """
    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))
    
    try:
        client = get_llm_client()
        for chunk in client.stream(messages):
            if chunk.content:
                yield str(chunk.content)
    except Exception as exc:
        raise LLMCallError(f"LLM stream call failed: {exc}")

PROVIDER_REGISTRY = PROVIDER_MAP

def list_providers() -> list[str]:
    """Return the names of all registered providers."""
    return list(PROVIDER_MAP.keys())

def update_env_variable(key: str, value: str) -> None:
    """Update environment variable both in memory and in the .env file."""
    import os
    from pathlib import Path
    
    os.environ[key] = value
    env_path = find_project_root() / ".env"
    
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
    return os.getenv("ACTIVE_PROVIDER", "")

def get_active_model() -> str:
    """Return the current active model."""
    return os.getenv("ACTIVE_MODEL", "")

def set_active_provider(provider: str) -> None:
    """Set the active provider and write to .env."""
    update_env_variable("ACTIVE_PROVIDER", provider)

def set_active_model(model: str) -> None:
    """Set the active model and write to .env."""
    update_env_variable("ACTIVE_MODEL", model)

def set_api_key(provider: str, api_key: str) -> None:
    """Set the API key for a provider and write to .env."""
    if provider not in PROVIDER_MAP:
        raise ValueError(f"Unknown provider '{provider}'")
    env_key = PROVIDER_MAP[provider]["env_key"]
    if env_key:
        update_env_variable(env_key, api_key)

def get_api_key_status() -> dict[str, bool]:
    """Return a map of provider -> status (True if API key is set)."""
    status = {}
    for prov, details in PROVIDER_MAP.items():
        key = details["env_key"]
        if key:
            val = os.getenv(key, "")
            status[prov] = bool(val.strip())
        else:
            status[prov] = True  # e.g. ollama doesn't require key
    return status

