"""
Onboarding — first-run experience for Klat.

Walks new users through:
  1. A few personal questions (role, coding experience, AI familiarity, languages)
     → stored in ~/.klat/settings/preferences.json
  2. Provider / API key setup (delegated to config._run_setup)
     → stored in ~/.klat/settings/config.json

Behavior will later be tailored based on the stored preferences.
For now, the answers are only persisted — not yet acted on.
"""

import json
import sys
from pathlib import Path

from src.config import CONFIG_DIR, _run_setup

PREFERENCES_FILE = CONFIG_DIR / "preferences.json"


# ---------------------------------------------------------------------------
# Question options
# ---------------------------------------------------------------------------

JOB_ROLES = [
    "Software engineer",
    "Web developer",
    "Data / ML engineer",
    "Designer",
    "Product manager",
    "Founder / Indie hacker",
    "Student",
    "Other (type your own)",
]

CODING_EXPERIENCE = [
    "Newcomer — just starting out",
    "Beginner — a few months of practice",
    "Intermediate — comfortable in at least one language",
    "Advanced — I ship real projects",
    "Expert — I write code for a living",
]

AI_FAMILIARITY = [
    "Curious — heard about it, haven't really used it",
    "Exploring — tried a few tools (ChatGPT, Copilot, etc.)",
    "Regular — I use AI tools weekly",
    "Power user — I build with AI daily",
]

LANGUAGES = [
    "Python",
    "JavaScript / TypeScript",
    "Rust",
    "Go",
    "C / C++",
    "Java",
    "C#",
    "Ruby",
    "PHP",
    "Swift",
    "Kotlin",
    "Other",
]


# ---------------------------------------------------------------------------
# IO helpers — small, dependency-free
# ---------------------------------------------------------------------------

def _ask_text(prompt: str, allow_skip: bool = True) -> str:
    """Free-text input. Enter = empty string (treated as skip)."""
    from src.ui import colorize_gradient
    suffix = "  (press Enter to skip)" if allow_skip else ""
    try:
        val = input(f"  {colorize_gradient(prompt)}{suffix}: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)
    return val


def _ask_choice(prompt: str, options: list[str], allow_skip: bool = True) -> str | None:
    """Single-select from a numbered list. Returns the option string, or None if skipped."""
    from src.ui import colorize_gradient, DIM, RESET
    print(f"  {colorize_gradient(prompt)}")
    for i, opt in enumerate(options, 1):
        print(f"    {DIM}{i:>2}{RESET}. {opt}")
    if allow_skip:
        print(f"    {DIM} 0{RESET}. Skip")
    print()
    try:
        raw = input(f"  {colorize_gradient('Choice')}: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)
    if not raw or raw == "0":
        return None
    try:
        idx = int(raw)
    except ValueError:
        return None
    if 1 <= idx <= len(options):
        return options[idx - 1]
    return None


def _ask_multiselect(prompt: str, options: list[str], allow_skip: bool = True) -> list[str]:
    """Multi-select via comma-separated numbers. Preserves order, dedupes."""
    from src.ui import colorize_gradient, DIM, RESET
    print(f"  {colorize_gradient(prompt)}  {DIM}(comma-separated, e.g. 1,3,5){RESET}")
    for i, opt in enumerate(options, 1):
        print(f"    {DIM}{i:>2}{RESET}. {opt}")
    if allow_skip:
        print(f"    {DIM} 0{RESET}. Skip")
    print()
    try:
        raw = input(f"  {colorize_gradient('Choices')}: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)
    if not raw or raw == "0":
        return []
    seen: set[str] = set()
    out: list[str] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            idx = int(piece)
        except ValueError:
            continue
        if 1 <= idx <= len(options):
            opt = options[idx - 1]
            if opt not in seen:
                seen.add(opt)
                out.append(opt)
    return out


def _section(title: str, subtitle: str = "") -> None:
    from src.ui import colorize_gradient, DIM, RESET
    print()
    print(f"  {colorize_gradient(title)}")
    if subtitle:
        print(f"  {DIM}{subtitle}{RESET}")
    print()


# ---------------------------------------------------------------------------
# Personal questions
# ---------------------------------------------------------------------------

def _run_personal_questions() -> dict:
    """Ask the four personal questions and return the resulting dict."""
    _section("1 / 4  —  About you", "What do you do?")
    role = _ask_choice("Pick the closest match", JOB_ROLES)
    if role == "Other (type your own)":
        role = _ask_text("Type your role") or ""
    elif role is None:
        role = ""

    _section("2 / 4  —  Coding experience", "How comfortable are you with code?")
    coding = _ask_choice("Pick one", CODING_EXPERIENCE) or ""

    _section("3 / 4  —  AI familiarity", "How much AI tooling do you use today?")
    ai = _ask_choice("Pick one", AI_FAMILIARITY) or ""

    _section("4 / 4  —  Programming languages", "Which ones do you use?")
    langs = _ask_multiselect("Pick all that apply", LANGUAGES)

    return {
        "role": role,
        "coding_experience": coding,
        "ai_familiarity": ai,
        "languages": langs,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_full_onboarding(force: bool = False) -> dict:
    """
    Run the complete first-run experience:
      - personal questions → preferences.json
      - provider / API key setup → config.json (via config._run_setup)

    Skips steps that are already complete, unless force=True.
    A step is considered complete only when its data is actually usable:
      - preferences.json must exist
      - at least one provider must have credentials in config.json / env
    """
    from src.ui import colorize_gradient, DIM, RESET
    from src.config import needs_provider_setup

    print()
    print(f"  🌿  {colorize_gradient('Welcome to Klat  —  Onboarding')}")
    print(f"  {DIM}A couple of quick steps to get you going. Press Enter to skip anything.{RESET}")

    prefs: dict = {}
    if force or not PREFERENCES_FILE.exists():
        prefs = _run_personal_questions()
        save_preferences(prefs)

    if force or needs_provider_setup():
        _section("Now let's connect an AI provider.",
                 "Pick at least one. You can switch providers anytime with /provider.")
        _run_setup()

    # Determine if global wrapper setup should be offered
    bin_path = Path.home() / ".klat" / "bin"
    if force or not bin_path.exists():
        _section("Global Access setup", "Run Klat from any folder by typing 'klat'")
        global_choice = _ask_choice("Install global launcher wrapper?", ["Yes", "No"], allow_skip=True)
        if global_choice == "Yes":
            from src.global_install import install_global
            install_global()

    _section("All set.", f"Preferences saved to {PREFERENCES_FILE}")
    return prefs



def save_preferences(prefs: dict) -> None:
    """Persist preferences to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(PREFERENCES_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2)


def load_preferences() -> dict:
    """Read preferences.json, returning {} if missing or unreadable."""
    if not PREFERENCES_FILE.exists():
        return {}
    try:
        with open(PREFERENCES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def is_onboarded() -> bool:
    """True once preferences have been recorded at least once."""
    return PREFERENCES_FILE.exists()


def preferences_path() -> Path:
    """Path to the preferences file (may not exist yet)."""
    return PREFERENCES_FILE
