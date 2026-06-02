"""
Configuration and environment management for Klat.

Provider / model selection is stored in env/.env and can be changed at
runtime with the /provider and /model slash commands.

Supported providers: vertexai, ai-studio, openai, anthropic, openrouter, nvidia-nim
"""

"""
Configuration and environment management for Klat.

Provider / model selection is stored in ~/.klat/settings/config.json and can be changed at
runtime with the /provider and /model slash commands.

Supported providers: vertexai, ai-studio, openai, anthropic, openrouter, nvidia-nim
"""

import os
import sys
import json
from pathlib import Path

from src.providers import PROVIDERS, PROVIDER_NAMES, get_provider

# Configuration paths
CONFIG_DIR = Path.home() / ".klat" / "settings"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Old environment paths for migration
ENV_DIR  = Path(__file__).parent.parent / "env"
ENV_FILE = ENV_DIR / ".env"

# ---------------------------------------------------------------------------
# Runtime state — mutated by /provider and /model commands
# ---------------------------------------------------------------------------

_state: dict = {
    "provider": None,   # None until ensure_env() resolves one
    "model":    None,   # None → use provider's default_model
    "reasoning": "none",
}

_config: dict[str, str] = {}


def current_reasoning() -> str:
    return _state["reasoning"]


def set_reasoning(value: str) -> None:
    """Set and persist the reasoning configuration level."""
    val = value.strip().lower()
    allowed = {"none", "minimal", "low", "medium", "high", "xhigh"}
    if val not in allowed:
        raise ValueError(f"Invalid reasoning level. Choose from: {', '.join(sorted(allowed))}")
    _state["reasoning"] = val
    _persist()



def current_provider() -> str:
    return _state["provider"]


def get_ascii_style() -> str:
    """Return the ascii_style config value, defaulting to 'default'."""
    return _config.get("ascii_style", "default").strip().lower()


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
    """Write provider, model & reasoning back to config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    current_data = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception:
            pass
    current_data["provider"] = _state["provider"] or ""
    current_data["model"] = _state["model"] or ""
    current_data["reasoning"] = _state["reasoning"] or "none"

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(current_data, f, indent=2)


def apply_session_settings(provider: str, model: str, reasoning: str) -> None:
    """Apply session-specific configuration settings."""
    _state["provider"] = provider
    _state["model"] = model
    _state["reasoning"] = reasoning
    _persist()


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

    setup_config: dict[str, str] = {}

    for key, p in PROVIDERS.items():
        print(f"  {GREEN}{p['display_name']}{RESET}  {DIM}({p['notes']}){RESET}")

        if key == "vertexai":
            project = _ask(f"    Google Cloud project ID (blank to skip)").strip()
            if project:
                location = _ask(f"    Location (blank for global)").strip() or "global"
                setup_config["google_cloud_project"] = project
                setup_config["google_cloud_location"] = location
                print(f"    {DIM}✓ Vertex AI configured{RESET}")
            else:
                print(f"    {DIM}skipped{RESET}")

        elif p["env_key"]:
            val = _ask(f"    {p['env_key']} (blank to skip)").strip()
            if val:
                setup_config[p["env_key"].lower()] = val
                print(f"    {DIM}✓ saved{RESET}")
            else:
                print(f"    {DIM}skipped{RESET}")

        print()

    if not setup_config:
        print(f"{GREEN}!{RESET} No providers configured — exiting.\n")
        sys.exit(1)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    current_data = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception:
            pass
    current_data.update(setup_config)

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(current_data, f, indent=2)
    print(f"{GREEN}✓{RESET} Config saved to {CONFIG_FILE}\n")


def _ask(prompt: str) -> str:
    """Simple input wrapper that exits cleanly on Ctrl-C / EOF."""
    try:
        from src.ui import GREEN, RESET
        return input(f"{GREEN}>{RESET} {prompt}: ")
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)


# ---------------------------------------------------------------------------
# Migration and Loading helpers
# ---------------------------------------------------------------------------

def _migrate_old_env() -> None:
    """Automatically migrate old env/.env file to ~/.klat/settings/config.json."""
    if ENV_FILE.exists():
        migrated_data = {}
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
                            v = v[1:-1]
                        norm_key = k.lower()
                        if norm_key.startswith("klat_"):
                            norm_key = norm_key[5:]
                        migrated_data[norm_key] = v

            if migrated_data:
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                existing_data = {}
                if CONFIG_FILE.exists():
                    try:
                        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                            existing_data = json.load(f)
                    except Exception:
                        pass
                existing_data.update(migrated_data)

                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(existing_data, f, indent=2)

            try:
                ENV_FILE.unlink()
                if ENV_DIR.exists() and not any(ENV_DIR.iterdir()):
                    ENV_DIR.rmdir()
            except Exception:
                pass
        except Exception as e:
            print(f"Migration error: {e}")


def _load_config() -> None:
    """Load configuration from config.json and inject API keys into os.environ."""
    global _config
    _config = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        _config[k.lower().strip()] = str(v)
        except Exception as e:
            print(f"Error reading config: {e}")

    for k, v in _config.items():
        if k not in ("provider", "model"):
            os.environ[k.upper()] = v


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def ensure_env() -> tuple[str, str]:
    """
    Load ~/.klat/settings/config.json, run setup wizard if needed, and return
    (project, location) for Vertex AI (empty strings when using a non-Vertex provider).

    Exits if no provider is configured after setup.
    """
    _migrate_old_env()

    if not CONFIG_FILE.exists():
        _run_setup()

    _load_config()

    # Restore persisted provider / model / reasoning choice
    saved_provider = _config.get("provider", "").strip()
    saved_model    = _config.get("model", "").strip()
    saved_reasoning = _config.get("reasoning", "none").strip().lower()

    if saved_provider and saved_provider in PROVIDERS:
        _state["provider"] = saved_provider
    if saved_model:
        _state["model"] = saved_model
    if saved_reasoning in {"none", "minimal", "low", "medium", "high", "xhigh"}:
        _state["reasoning"] = saved_reasoning

    # Find the best available provider
    available = configured_providers()
    if not available:
        print(
            f"\n! No providers are configured in {CONFIG_FILE}.\n"
            "  Add at least one API key and restart Klat.\n"
        )
        sys.exit(1)

    # If the saved provider isn't usable, fall back to the first available one
    if _state["provider"] not in available:
        _state["provider"] = available[0]

    project  = _config.get("google_cloud_project", "").strip()
    location = _config.get("google_cloud_location", "global").strip()

    if project:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project
    if location:
        os.environ["GOOGLE_CLOUD_LOCATION"] = location

    return project, location

