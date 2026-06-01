"""
Configuration and environment management for Klat.

Provider / model selection is stored in env/.env and can be changed at
runtime with the /provider and /model slash commands.

Supported providers: vertexai, ai-studio, openai, anthropic, openrouter, nvidia-nim
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key

from src.providers import PROVIDERS, PROVIDER_NAMES, get_provider

ENV_DIR  = Path(__file__).parent.parent / "env"
ENV_FILE = ENV_DIR / ".env"

# ---------------------------------------------------------------------------
# Runtime state — mutated by /provider and /model commands
# ---------------------------------------------------------------------------

_state: dict = {
    "provider": None,   # None until ensure_env() resolves one
    "model":    None,   # None → use provider's default_model
}


def current_provider() -> str:
    return _state["provider"]


def current_model() -> str:
    """Return the active model name (falls back to provider default)."""
    if _state["model"]:
        return _state["model"]
    return PROVIDERS[_state["provider"]]["default_model"]


def set_provider(name: str) -> None:
    """Switch the active provider (and reset model to its default)."""
    get_provider(name)          # raises ValueError if unknown
    _state["provider"] = name.lower().strip()
    _state["model"] = None      # reset to new provider's default
    _persist()


def set_model(model: str) -> None:
    """Override the model for the current provider."""
    _state["model"] = model.strip()
    _persist()


def _persist() -> None:
    """Write provider & model back to env/.env."""
    ENV_DIR.mkdir(parents=True, exist_ok=True)
    set_key(str(ENV_FILE), "KLAT_PROVIDER", _state["provider"] or "")
    set_key(str(ENV_FILE), "KLAT_MODEL",    _state["model"] or "")


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------

def _has_credentials(provider_key: str) -> bool:
    """Return True if the provider has enough credentials to be usable."""
    p = PROVIDERS[provider_key]
    if p["env_key"] is None:
        # Vertex AI — relies on gcloud ADC; we can't easily verify, so
        # check if GOOGLE_CLOUD_PROJECT is set as a proxy.
        return bool(os.getenv("GOOGLE_CLOUD_PROJECT", "").strip())
    return bool(os.getenv(p["env_key"], "").strip())


def configured_providers() -> list[str]:
    """Return provider keys that have credentials set in the environment."""
    return [k for k in PROVIDER_NAMES if _has_credentials(k)]


# ---------------------------------------------------------------------------
# First-run interactive setup
# ---------------------------------------------------------------------------

def _run_setup() -> None:
    """Walk the user through setting up at least one provider."""
    from src.ui import GREEN, DIM, RESET  # local import to avoid circular

    print(f"\n{GREEN}First-time setup{RESET}")
    print("Configure at least one provider. Press Enter to skip any.\n")

    lines: list[str] = []

    for key, p in PROVIDERS.items():
        print(f"  {GREEN}{p['display_name']}{RESET}  {DIM}({p['notes']}){RESET}")

        if key == "vertexai":
            project = _ask(f"    Google Cloud project ID (blank to skip)").strip()
            if project:
                location = _ask(f"    Location (blank for global)").strip() or "global"
                lines.append(f"GOOGLE_CLOUD_PROJECT={project}")
                lines.append(f"GOOGLE_CLOUD_LOCATION={location}")
                print(f"    {DIM}✓ Vertex AI configured{RESET}")
            else:
                print(f"    {DIM}skipped{RESET}")

        elif p["env_key"]:
            val = _ask(f"    {p['env_key']} (blank to skip)").strip()
            if val:
                lines.append(f"{p['env_key']}={val}")
                print(f"    {DIM}✓ saved{RESET}")
            else:
                print(f"    {DIM}skipped{RESET}")

        print()

    if not lines:
        print(f"{GREEN}!{RESET} No providers configured — exiting.\n")
        sys.exit(1)

    ENV_DIR.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{GREEN}✓{RESET} Config saved to env/.env\n")


def _ask(prompt: str) -> str:
    """Simple input wrapper that exits cleanly on Ctrl-C / EOF."""
    try:
        from src.ui import GREEN, RESET
        return input(f"{GREEN}>{RESET} {prompt}: ")
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def ensure_env() -> tuple[str, str]:
    """
    Load env/.env, run setup wizard if needed, and return (project, location)
    for Vertex AI (empty strings when using a non-Vertex provider).

    Exits if no provider is configured after setup.
    """
    ENV_DIR.mkdir(parents=True, exist_ok=True)

    if not ENV_FILE.exists():
        _run_setup()

    load_dotenv(ENV_FILE)

    # Restore persisted provider / model choice
    saved_provider = os.getenv("KLAT_PROVIDER", "").strip()
    saved_model    = os.getenv("KLAT_MODEL",    "").strip()

    if saved_provider and saved_provider in PROVIDERS:
        _state["provider"] = saved_provider
    if saved_model:
        _state["model"] = saved_model

    # Find the best available provider
    available = configured_providers()
    if not available:
        print(
            "\n! No providers are configured in env/.env.\n"
            "  Add at least one API key and restart Klat.\n"
        )
        sys.exit(1)

    # If the saved provider isn't usable, fall back to the first available one
    if _state["provider"] not in available:
        _state["provider"] = available[0]

    project  = os.getenv("GOOGLE_CLOUD_PROJECT",  "").strip()
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "global").strip()

    return project, location
