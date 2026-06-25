"""
Provider registry for Klat.

Each provider entry defines:
  - display_name   : human-readable label
  - backend        : "gemini" | "openai-compat"
  - base_url       : API endpoint (None for native SDKs)
  - default_model  : model used when none is specified
  - env_key        : env-var name that holds the API key
  - notes          : one-liner shown in /provider help
"""

from __future__ import annotations

BUILTIN_PROVIDERS: dict[str, dict] = {
    # ------------------------------------------------------------------ #
    #  Vertex AI — Google's enterprise Gemini platform (ADC, no key)      #
    # ------------------------------------------------------------------ #
    "vertexai": {
        "display_name": "Vertex AI (Gemini)",
        "backend": "gemini",
        "base_url": None,
        "default_model": "google/gemini-3.5-flash",
        "env_key": None,          # uses gcloud ADC
        "notes": "Google Vertex AI — requires gcloud ADC",
    },

    # ------------------------------------------------------------------ #
    #  AI Studio — Google's developer Gemini endpoint (API key)           #
    # ------------------------------------------------------------------ #
    "ai-studio": {
        "display_name": "AI Studio (Gemini)",
        "backend": "gemini",
        "base_url": None,
        "default_model": "gemini-3.5-flash",
        "env_key": "GEMINI_API_KEY",
        "notes": "Google AI Studio — requires GEMINI_API_KEY",
    },

    # ------------------------------------------------------------------ #
    #  OpenAI                                                              #
    # ------------------------------------------------------------------ #
    "openai": {
        "display_name": "OpenAI",
        "backend": "openai-compat",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-5.5-pro",
        "env_key": "OPENAI_API_KEY",
        "notes": "OpenAI — requires OPENAI_API_KEY",
    },

    # ------------------------------------------------------------------ #
    #  Anthropic (via their OpenAI-compatible shim)                       #
    # ------------------------------------------------------------------ #
    "anthropic": {
        "display_name": "Anthropic",
        "backend": "openai-compat",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-opus-4.8",
        "env_key": "ANTHROPIC_API_KEY",
        "notes": "Anthropic — requires ANTHROPIC_API_KEY",
    },

    # ------------------------------------------------------------------ #
    #  OpenRouter                                                          #
    # ------------------------------------------------------------------ #
    "openrouter": {
        "display_name": "OpenRouter",
        "backend": "openai-compat",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "minimax/minimax-m3",
        "env_key": "OPENROUTER_API_KEY",
        "notes": "OpenRouter — requires OPENROUTER_API_KEY",
    },

    # ------------------------------------------------------------------ #
    #  Nvidia NIM                                                          #
    # ------------------------------------------------------------------ #
    "nvidia-nim": {
        "display_name": "Nvidia NIM",
        "backend": "openai-compat",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "z-ai/glm-5.1",
        "env_key": "NVIDIA_API_KEY",
        "notes": "Nvidia NIM — requires NVIDIA_API_KEY",
    },

    # ------------------------------------------------------------------ #
    #  AgentRouter                                                         #
    # ------------------------------------------------------------------ #
    "agentrouter": {
        "display_name": "AgentRouter",
        "backend": "openai-compat",
        "base_url": "https://agentrouter.org/v1/",
        "default_model": "gpt-4o",
        "env_key": "AGENTROUTER_API_KEY",
        "notes": "AgentRouter — requires AGENTROUTER_API_KEY (use /spoof codex for client access)",
    },
}

PROVIDERS: dict[str, dict] = {}
PROVIDER_NAMES: list[str] = []


def load_custom_providers() -> None:
    """Load custom provider configurations from ~/.klat/settings/providers/."""
    import json
    import sys
    from pathlib import Path

    PROVIDERS.clear()
    PROVIDERS.update(BUILTIN_PROVIDERS)

    providers_dir: Path = Path.home() / ".klat" / "settings" / "providers"
    if providers_dir.exists():
        try:
            for file_path in providers_dir.glob("*.json"):
                if not file_path.is_file():
                    continue
                provider_name: str = file_path.stem.lower().strip()
                try:
                    with open(file_path, "r", encoding="utf-8") as file_handle:
                        config_data = json.load(file_handle)
                    if isinstance(config_data, dict):
                        PROVIDERS[provider_name] = {
                            "display_name": str(config_data.get("display_name", provider_name.title())),
                            "backend": str(config_data.get("backend", "openai-compat")),
                            "base_url": config_data.get("base_url"),
                            "default_model": str(config_data.get("default_model", "")),
                            "env_key": config_data.get("env_key"),
                            "notes": str(config_data.get("notes", f"Custom provider '{provider_name}'")),
                        }
                except json.JSONDecodeError as decode_error:
                    sys.stderr.write(f"Warning: Failed to parse custom provider config {file_path}: {decode_error}\n")
                except OSError as os_error:
                    sys.stderr.write(f"Warning: Failed to read custom provider config {file_path}: {os_error}\n")
        except OSError as dir_error:
            sys.stderr.write(f"Warning: Failed to access custom providers directory: {dir_error}\n")

    PROVIDER_NAMES.clear()
    PROVIDER_NAMES.extend(list(PROVIDERS.keys()))


# Initialize providers list on import
load_custom_providers()


def get_provider(name: str) -> dict:
    """Return provider config or raise ValueError."""
    key = name.lower().strip()
    if key not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{name}'. "
            f"Available: {', '.join(PROVIDER_NAMES)}"
        )
    return PROVIDERS[key]
