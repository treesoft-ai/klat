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

from src.providers import PROVIDERS, PROVIDER_NAMES, get_provider, BUILTIN_PROVIDERS

# Configuration paths
CONFIG_DIR = Path.home() / ".klat" / "settings"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Old environment paths for migration
ENV_DIR  = Path(__file__).parent.parent / "env"
ENV_FILE = ENV_DIR / ".env"

# ---------------------------------------------------------------------------
# Runtime state — mutated by /provider and /model commands
# ---------------------------------------------------------------------------

COMPLEXITY_LEVELS = ("nano", "essential", "full")

_state: dict = {
    "provider": None,   # None until ensure_env() resolves one
    "model":    None,   # None → use provider's default_model
    "reasoning": "none",
    "streaming": True,
    "complexity": "full",
    "theme": "green",
    "ui_mode": "simple",
    "spoof": None,      # None = disabled; "codex" = spoof Codex CLI headers
}

_config: dict = {}


def current_complexity() -> str:
    """Return the active complexity level: 'nano', 'essential', or 'full'."""
    return _state.get("complexity", "full")


def set_complexity(value: str) -> None:
    """Set and persist the complexity level."""
    val = value.strip().lower()
    if val not in COMPLEXITY_LEVELS:
        raise ValueError(
            f"Invalid complexity level '{val}'. Choose from: {', '.join(COMPLEXITY_LEVELS)}"
        )
    _state["complexity"] = val
    _persist()


def current_ui_mode() -> str:
    """Return the active UI mode: 'simple' or 'professional'."""
    return _state.get("ui_mode", "simple")


def set_ui_mode(value: str) -> None:
    """Set and persist the UI mode."""
    old_mode = current_ui_mode()
    val = value.strip().lower()
    if val not in ("simple", "professional"):
        raise ValueError("Invalid UI mode. Choose from: simple, professional")
    _state["ui_mode"] = val
    _persist()

    if old_mode != val:
        try:
            from src.ui import animate_ui_mode_transition
            animate_ui_mode_transition(old_mode, val)
        except Exception:
            pass


def current_theme() -> str:
    """Return the active theme name."""
    return _state.get("theme", "green")


def set_theme(value: str) -> None:
    """Set and persist the theme."""
    old_theme = current_theme()
    val = value.strip().lower()
    if val in ("pure white", "pure_white", "white"):
        val = "pure white"
    if val == "animated_rainbow":
        raise ValueError("animated_rainbow is currently disabled due to reliability and other bugs")
    allowed = {"green", "red", "blue", "yellow", "pure white", "orange", "purple", "cyan", "pink", "rainbow", "cyberpunk", "sunset", "matrix", "ocean", "forest"}
    from src.ui import parse_custom_theme
    custom = parse_custom_theme(value)
    if val not in allowed and not custom:
        raise ValueError(
            f"Invalid theme '{value}'. Choose from preset ({', '.join(sorted(allowed))}) or enter two hex codes (e.g. '#ff0055 #00ffcc')"
        )
    if custom:
        rgb1, rgb2 = custom
        h1 = f"#{rgb1[0]:02x}{rgb1[1]:02x}{rgb1[2]:02x}"
        h2 = f"#{rgb2[0]:02x}{rgb2[1]:02x}{rgb2[2]:02x}"
        val = f"{h1} {h2}"
    _state["theme"] = val
    _persist()

    # Trigger the theme transition animation if the theme actually changed
    if old_theme != val:
        try:
            from src.ui import animate_theme_transition
            animate_theme_transition(old_theme, val)
        except Exception:
            pass

    try:
        from src import ui
        ui._prompt_session = None
    except Exception:
        pass


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


def current_streaming() -> bool:
    """Return whether streaming is enabled."""
    return _state.get("streaming", True)


def set_streaming(value: bool) -> None:
    """Set and persist the streaming configuration option."""
    _state["streaming"] = value
    _persist()


def current_spoof() -> str | None:
    """Return the active spoof profile, or None if disabled."""
    return _state.get("spoof", None)


def set_spoof(value: str | None) -> None:
    """Set and persist the active spoof profile. Pass None to disable."""
    _state["spoof"] = value
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
    """Write provider, model, reasoning, streaming, complexity, plus other keys back to config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    current_data = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception:
            pass
    current_data.update(_config)
    current_data["provider"] = _state["provider"] or ""
    current_data["model"] = _state["model"] or ""
    current_data["reasoning"] = _state["reasoning"] or "none"
    current_data["streaming"] = current_streaming()
    current_data["complexity"] = current_complexity()
    current_data["theme"] = current_theme()
    current_data["ui_mode"] = current_ui_mode()
    current_data["spoof"] = current_spoof() or ""

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(current_data, f, indent=2)


def get_all_settings() -> dict:
    """Return a dictionary of all current settings."""
    settings = {
        "provider": _state["provider"] or "",
        "model": current_model() or "",
        "reasoning": current_reasoning() or "none",
        "streaming": "on" if current_streaming() else "off",
        "complexity": current_complexity(),
        "ascii_style": get_ascii_style(),
        "theme": current_theme(),
        "ui_mode": current_ui_mode(),
    }
    for k, v in _config.items():
        if k not in ("provider", "model", "reasoning", "streaming", "complexity", "ascii_style", "theme", "ui_mode"):
            settings[k] = v
    return settings


def set_config_value(key: str, value: str) -> None:
    """Set and persist a configuration setting key/value."""
    key_lower = key.strip().lower()
    if key_lower == "provider":
        set_provider(value)
    elif key_lower == "model":
        set_model(value)
    elif key_lower == "reasoning":
        set_reasoning(value)
    elif key_lower == "streaming":
        val = value.strip().lower()
        if val in ("on", "true", "1", "yes"):
            set_streaming(True)
        elif val in ("off", "false", "0", "no"):
            set_streaming(False)
        else:
            raise ValueError("Invalid streaming value. Use 'on' or 'off'.")
    elif key_lower == "complexity":
        set_complexity(value)
    elif key_lower == "ui_mode":
        set_ui_mode(value)
    elif key_lower == "theme":
        set_theme(value)
    elif key_lower == "ascii_style":
        val = value.strip().lower()
        allowed = {"default", "legacy", "experimental"}
        if val not in allowed:
            raise ValueError(f"Invalid ASCII style. Choose from: {', '.join(sorted(allowed))}")
        _config["ascii_style"] = val
        _persist()
    else:
        _config[key_lower] = value
        _persist()
        os.environ[key_lower.upper()] = value


def reset_config_value(key: str) -> None:
    """Reset a configuration setting key to its default."""
    key_lower = key.strip().lower()
    if key_lower == "provider":
        available = configured_providers()
        if available:
            set_provider(available[0])
        else:
            raise ValueError("No providers available to reset to.")
    elif key_lower == "model":
        _state["model"] = None
        if "model" in _config:
            del _config["model"]
        _persist()
    elif key_lower == "reasoning":
        set_reasoning("none")
    elif key_lower == "streaming":
        set_streaming(True)
    elif key_lower == "complexity":
        set_complexity("full")
    elif key_lower == "ui_mode":
        set_ui_mode("simple")
    elif key_lower == "theme":
        set_theme("green")
    elif key_lower == "ascii_style":
        if "ascii_style" in _config:
            del _config["ascii_style"]
        _persist()
    else:
        if key_lower in _config:
            del _config[key_lower]
        env_key = key_lower.upper()
        if env_key in os.environ:
            del os.environ[env_key]
        _persist()


def randomize_config_value(key: str) -> str:
    """Randomly select a valid value for the configuration key, save and return it."""
    import random
    key_lower = key.strip().lower()
    if key_lower == "provider":
        available = configured_providers()
        if not available:
            raise ValueError("No configured providers available.")
        val = random.choice(available)
        set_provider(val)
        return val
    elif key_lower == "model":
        models_by_provider = {
            "vertexai": ["google/gemini-3.5-flash", "google/gemini-3.5-pro"],
            "ai-studio": ["gemini-3.5-flash", "gemini-3.5-pro"],
            "openai": ["gpt-5.5-pro", "gpt-4o", "gpt-4o-mini"],
            "anthropic": ["claude-opus-4.8", "claude-3-5-sonnet-latest"],
            "openrouter": ["minimax/minimax-m3", "meta-llama/llama-3-8b-instruct"],
            "nvidia-nim": ["z-ai/glm-5.1", "meta/llama3-70b-instruct"],
        }
        prov = current_provider()
        candidates = models_by_provider.get(prov, [get_provider(prov)["default_model"]])
        val = random.choice(candidates)
        set_model(val)
        return val
    elif key_lower == "reasoning":
        levels = ["none", "minimal", "low", "medium", "high", "xhigh"]
        val = random.choice(levels)
        set_reasoning(val)
        return val
    elif key_lower == "streaming":
        val = random.choice([True, False])
        set_streaming(val)
        return "on" if val else "off"
    elif key_lower == "ascii_style":
        styles = ["default", "legacy", "experimental"]
        val = random.choice(styles)
        _config["ascii_style"] = val
        _persist()
        return val
    elif key_lower == "theme":
        themes = ["green", "red", "blue", "yellow", "pure white", "orange", "purple", "cyan", "pink", "rainbow", "cyberpunk", "sunset", "matrix", "ocean", "forest"]
        val = random.choice(themes)
        set_theme(val)
        return val
    elif key_lower == "ui_mode":
        val = random.choice(["simple", "professional"])
        set_ui_mode(val)
        return val
    else:
        raise ValueError(f"Cannot randomize custom setting '{key}'. Supported settings: provider, model, reasoning, streaming, ascii_style, theme, ui_mode")


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
    if provider_key not in BUILTIN_PROVIDERS:
        return True
    p = PROVIDERS[provider_key]
    if provider_key == "vertexai":
        # Vertex AI — relies on gcloud ADC; we can't easily verify, so
        # check if GOOGLE_CLOUD_PROJECT is set as a proxy.
        return bool(os.getenv("GOOGLE_CLOUD_PROJECT", "").strip())
    if p.get("env_key") is None:
        # Custom provider with no env API key required (e.g., local models)
        return True
    return bool(os.getenv(p["env_key"], "").strip())


def configured_providers() -> list[str]:
    """Return provider keys that have credentials set in the environment."""
    return [k for k in PROVIDER_NAMES if _has_credentials(k)]


def needs_provider_setup() -> bool:
    """True if no provider is currently usable (catches both missing file and empty file)."""
    return not configured_providers()


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
                        key = k.lower().strip()
                        if key == "streaming":
                            if isinstance(v, bool):
                                _config[key] = v
                            else:
                                _config[key] = str(v).lower().strip() == "true"
                        else:
                            _config[key] = str(v)
        except Exception as e:
            print(f"Error reading config: {e}")

    for k, v in _config.items():
        if k not in ("provider", "model", "streaming"):
            os.environ[k.upper()] = str(v)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def ensure_env() -> tuple[str, str]:
    """
    Load ~/.klat/settings/config.json, run onboarding if needed, and return
    (project, location) for Vertex AI (empty strings when using a non-Vertex provider).

    Onboarding covers both personal questions (preferences.json) and provider/API
    key setup (config.json). Only the missing step is run.

    Exits if no provider is configured after onboarding.
    """
    _migrate_old_env()
    _load_config()

    prefs_file = CONFIG_DIR / "preferences.json"
    if not prefs_file.exists() or needs_provider_setup():
        # Local import to avoid a circular dependency with src.onboarding.
        from src.onboarding import run_full_onboarding
        run_full_onboarding()
        _load_config()  # reload to pick up keys just written

    # Restore persisted provider / model / reasoning / streaming / complexity choice
    saved_provider = _config.get("provider", "").strip()
    saved_model    = _config.get("model", "").strip()
    saved_reasoning = _config.get("reasoning", "none").strip().lower()
    saved_streaming = _config.get("streaming")
    saved_complexity = _config.get("complexity", "full").strip().lower()
    saved_theme = _config.get("theme", "green").strip().lower()
    saved_ui_mode = _config.get("ui_mode", "simple").strip().lower()
    saved_spoof = _config.get("spoof", "").strip().lower()

    if saved_provider and saved_provider in PROVIDERS:
        _state["provider"] = saved_provider
    if saved_model:
        _state["model"] = saved_model
    if saved_reasoning in {"none", "minimal", "low", "medium", "high", "xhigh"}:
        _state["reasoning"] = saved_reasoning
    if saved_streaming is not None:
        _state["streaming"] = bool(saved_streaming)
    else:
        _state["streaming"] = True
    if saved_complexity in COMPLEXITY_LEVELS:
        _state["complexity"] = saved_complexity
    else:
        _state["complexity"] = "full"
    if saved_ui_mode in ("simple", "professional"):
        _state["ui_mode"] = saved_ui_mode
    else:
        _state["ui_mode"] = "simple"
    _state["spoof"] = saved_spoof if saved_spoof in ("codex",) else None
    allowed_themes = {"green", "red", "blue", "yellow", "pure white", "orange", "purple", "cyan", "pink", "rainbow", "cyberpunk", "sunset", "matrix", "ocean", "forest"}
    from src.ui import parse_custom_theme
    if saved_theme == "animated_rainbow":
        _state["theme"] = "green"
    elif saved_theme in allowed_themes or parse_custom_theme(saved_theme):
        _state["theme"] = saved_theme
    else:
        _state["theme"] = "green"

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

