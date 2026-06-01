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

PROVIDERS: dict[str, dict] = {
    # ------------------------------------------------------------------ #
    #  Vertex AI — Google's enterprise Gemini platform (ADC, no key)      #
    # ------------------------------------------------------------------ #
    "vertexai": {
        "display_name": "Vertex AI (Gemini)",
        "backend": "gemini",
        "base_url": None,
        "default_model": "gemini-2.0-flash-001",
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
        "default_model": "gemini-2.0-flash",
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
        "default_model": "gpt-4o",
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
        "default_model": "claude-opus-4-5",
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
        "default_model": "google/gemini-2.0-flash-001",
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
        "default_model": "meta/llama-4-scout-17b-16e-instruct",
        "env_key": "NVIDIA_API_KEY",
        "notes": "Nvidia NIM — requires NVIDIA_API_KEY",
    },
}

# Ordered list for display / tab completion
PROVIDER_NAMES: list[str] = list(PROVIDERS.keys())


def get_provider(name: str) -> dict:
    """Return provider config or raise ValueError."""
    key = name.lower().strip()
    if key not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{name}'. "
            f"Available: {', '.join(PROVIDER_NAMES)}"
        )
    return PROVIDERS[key]
