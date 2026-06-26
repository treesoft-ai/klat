"""
Minimal CLI UI for Klat.
Only one accent color: deep green.
"""

import sys
import threading
import time
import colorsys

# Deep green — the only accent color in Klat
THEME_CONFIG = {
    "green": {
        "accent": "\033[38;2;0;180;80m",
        "hex": "#00b450",
        "start": (0, 180, 80),
        "end": (2, 219, 99)
    },
    "red": {
        "accent": "\033[38;2;220;0;50m",
        "hex": "#dc0032",
        "start": (220, 0, 50),
        "end": (255, 60, 100)
    },
    "blue": {
        "accent": "\033[38;2;0;102;204m",
        "hex": "#0066cc",
        "start": (0, 102, 204),
        "end": (0, 204, 255)
    },
    "yellow": {
        "accent": "\033[38;2;240;160;0m",
        "hex": "#f0a000",
        "start": (240, 160, 0),
        "end": (255, 240, 0)
    },
    "pure white": {
        "accent": "\033[38;2;255;255;255m",
        "hex": "#ffffff",
        "start": (200, 200, 200),
        "end": (255, 255, 255)
    },
    "orange": {
        "accent": "\033[38;2;255;68;0m",
        "hex": "#ff4400",
        "start": (255, 68, 0),
        "end": (255, 153, 0)
    },
    "purple": {
        "accent": "\033[38;2;138;43;226m",
        "hex": "#8a2be2",
        "start": (138, 43, 226),
        "end": (218, 112, 214)
    },
    "cyan": {
        "accent": "\033[38;2;0;150;150m",
        "hex": "#009696",
        "start": (0, 150, 150),
        "end": (0, 255, 255)
    },
    "pink": {
        "accent": "\033[38;2;255;20;147m",
        "hex": "#ff1493",
        "start": (255, 20, 147),
        "end": (255, 105, 180)
    },
    "rainbow": {
        "accent": "\033[38;2;0;229;163m",
        "hex": "#00e5a3",
        "start": (0, 229, 163),
        "end": (0, 255, 204)
    },
    "animated_rainbow": {
        "accent": "\033[38;2;0;229;163m",
        "hex": "#00e5a3",
        "start": (0, 229, 163),
        "end": (0, 255, 204)
    },
    "cyberpunk": {
        "accent": "\033[38;2;255;0;128m",
        "hex": "#ff0080",
        "start": (255, 0, 128),
        "end": (0, 255, 255)
    },
    "sunset": {
        "accent": "\033[38;2;255;0;128m",
        "hex": "#ff0080",
        "start": (255, 0, 128),
        "end": (255, 170, 0)
    },
    "matrix": {
        "accent": "\033[38;2;0;255;68m",
        "hex": "#00ff44",
        "start": (0, 100, 0),
        "end": (0, 255, 68)
    },
    "ocean": {
        "accent": "\033[38;2;0;102;255m",
        "hex": "#0066ff",
        "start": (0, 50, 150),
        "end": (0, 204, 255)
    },
    "forest": {
        "accent": "\033[38;2;140;200;120m",
        "hex": "#8cc878",
        "start": (20, 80, 40),
        "end": (140, 200, 120)
    }
}


_rainbow_phase: float = 0.0
_rainbow_thread_active: bool = False
_rainbow_thread_lock: threading.Lock = threading.Lock()


def redraw_animated_banner() -> None:
    """Redraws only the banner (logo + info lines) using the current rainbow phase."""
    import sys
    import re

    # Save cursor position and hide cursor
    sys.stdout.write("\033[?25l\033[s")
    
    try:
        # Move to Row 2, Column 1 (absolute top of the banner)
        sys.stdout.write("\033[2;1H")
        
        try:
            from src.config import get_ascii_style
            style = get_ascii_style()
        except Exception:
            style = "default"

        if style == "legacy":
            logo_lines = _LEGACY_LOGO
        elif style == "experimental":
            logo_lines = _EXPERIMENTAL_LOGO
        else:
            logo_lines = _DEFAULT_LOGO

        logo_w = max(len(l) for l in logo_lines)
        sep = f"  {DIM}\u2502{RESET}  "
        
        # Re-colorize the saved info lines
        current_info: list[str] = []
        for line in _last_info_lines:
            stripped = re.sub(r'\033\[[0-9;]*[a-zA-Z]', '', line)
            parts = re.split(r'\s{2,}', stripped, maxsplit=1)
            if len(parts) == 2:
                lbl, val = parts[0], parts[1]
                padded_lbl = lbl.ljust(12)
                current_info.append(f"{DIM}{padded_lbl}{RESET}{colorize_gradient(val)}")
            else:
                current_info.append(line)
        
        rows = max(len(logo_lines), len(current_info))
        
        # Move down 1 line relatively (skipping the blank line at Row 2, which remains blank)
        sys.stdout.write("\033[K\033[1B\r")
        for i in range(rows):
            raw = logo_lines[i] if i < len(logo_lines) else ""
            info = current_info[i] if i < len(current_info) else ""
            try:
                from src.config import current_theme
                theme = current_theme()
            except Exception:
                theme = "green"
            logo = colorize_logo_line(raw.ljust(logo_w), i, theme)
            sys.stdout.write(f"\033[K{logo}{sep}{info}\033[1B\r")
        
        # Overwrite trailing blank line
        sys.stdout.write("\033[K")
    finally:
        # Restore cursor position and visibility
        sys.stdout.write("\033[u\033[?25h")
        sys.stdout.flush()


def schedule_banner_redraw() -> None:
    """Schedule redraw_animated_banner on the prompt_toolkit event loop if running."""
    try:
        from prompt_toolkit.application import get_app
        app = get_app()
        if app and app.is_running and app.loop:
            app.loop.call_soon_threadsafe(redraw_animated_banner)
            return
    except Exception:
        pass
    
    try:
        redraw_animated_banner()
    except (IOError, OSError):
        pass


def _rainbow_animation_loop() -> None:
    """Daemon thread loop that updates the rainbow phase and schedules/performs banner redraw."""
    global _rainbow_phase
    while True:
        with _rainbow_thread_lock:
            if not _rainbow_thread_active:
                break
        
        if not is_session_fresh():
            stop_rainbow_animation()
            break
            
        _rainbow_phase = (_rainbow_phase + 0.02) % 1.0
        schedule_banner_redraw()
        time.sleep(0.06)


def start_rainbow_animation() -> None:
    """Start the background rainbow animation thread if not already running."""
    global _rainbow_thread_active
    with _rainbow_thread_lock:
        if _rainbow_thread_active:
            return
        _rainbow_thread_active = True
    
    t = threading.Thread(target=_rainbow_animation_loop, daemon=True)
    t.start()


def stop_rainbow_animation() -> None:
    """Stop the background rainbow animation thread."""
    global _rainbow_thread_active
    with _rainbow_thread_lock:
        _rainbow_thread_active = False


def parse_hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Helper to convert a hexadecimal color string to an RGB tuple."""
    hex_str = hex_str.lstrip('#')
    return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)


def parse_custom_theme(theme_str: str) -> tuple[tuple[int, int, int], tuple[int, int, int]] | None:
    """Check if the string contains two hex codes and return their RGB values."""
    import re
    parts = re.split(r'[\s,]+', theme_str.strip())
    if len(parts) == 2:
        hex1, hex2 = parts[0], parts[1]
        pattern = re.compile(r'^#?[0-9a-fA-F]{6}$')
        if pattern.match(hex1) and pattern.match(hex2):
            try:
                rgb1 = parse_hex_to_rgb(hex1)
                rgb2 = parse_hex_to_rgb(hex2)
                return rgb1, rgb2
            except Exception:
                pass
    return None


def get_theme_config(theme: str) -> dict:
    """Get theme configuration, dynamically creating one for custom hex themes if needed."""
    theme_lower = theme.strip().lower()
    if theme_lower in THEME_CONFIG:
        return THEME_CONFIG[theme_lower]

    custom = parse_custom_theme(theme)
    if custom:
        rgb1, rgb2 = custom
        h1 = f"#{rgb1[0]:02x}{rgb1[1]:02x}{rgb1[2]:02x}"
        accent = f"\033[38;2;{rgb1[0]};{rgb1[1]};{rgb1[2]}m"
        return {
            "accent": accent,
            "hex": h1,
            "start": rgb1,
            "end": rgb2
        }
    return THEME_CONFIG["green"]


class DynamicThemeColor(str):
    """Dynamically resolves to the active theme's accent color."""

    def __new__(cls) -> "DynamicThemeColor":
        return str.__new__(cls, "")

    @property
    def _val(self) -> str:
        try:
            from src.config import current_theme
            theme = current_theme()
        except Exception:
            theme = "green"
        config = get_theme_config(theme)
        return config["accent"]

    def __str__(self) -> str:
        return self._val

    def __repr__(self) -> str:
        return repr(self._val)

    def __format__(self, format_spec: str) -> str:
        return self._val.__format__(format_spec)

    def __add__(self, other: str) -> str:
        return self._val + other

    def __radd__(self, other: str) -> str:
        return other + self._val

    def __eq__(self, other: object) -> bool:
        return self._val == other

    def __hash__(self) -> int:
        return hash(self._val)

    def __len__(self) -> int:
        return len(self._val)


class DynamicLogoColors:
    """Dynamically generates the 6 line gradient colors for the logo."""

    def __getitem__(self, index: int) -> str:
        try:
            from src.config import current_theme
            theme = current_theme()
        except Exception:
            theme = "green"

        if theme == "rainbow":
            h_cycle = abs((index / 6.0) * 2 - 1) * 0.55 + 0.15
            r, g, b = colorsys.hsv_to_rgb(h_cycle, 0.9, 0.95)
            return f"\033[38;2;{int(r * 255)};{int(g * 255)};{int(b * 255)}m"
        elif theme == "animated_rainbow":
            h_cycle = abs(((index / 6.0 + _rainbow_phase) % 1.0) * 2 - 1) * 0.55 + 0.15
            r, g, b = colorsys.hsv_to_rgb(h_cycle, 0.9, 0.95)
            return f"\033[38;2;{int(r * 255)};{int(g * 255)};{int(b * 255)}m"

        config = get_theme_config(theme)
        start = config["start"]
        end = config["end"]
        # Interpolate between start and end RGB coordinates over 6 steps (0 to 5)
        r = int(start[0] + (end[0] - start[0]) * index / 5)
        g = int(start[1] + (end[1] - start[1]) * index / 5)
        b = int(start[2] + (end[2] - start[2]) * index / 5)
        return f"\033[38;2;{r};{g};{b}m"

    def __len__(self) -> int:
        return 6


def get_theme_hex(theme: str) -> str:
    """Return the hexadecimal accent color representation for prompt_toolkit styles."""
    config = get_theme_config(theme)
    return config["hex"]


GREEN = DynamicThemeColor()
RESET = "\033[0m"
DIM   = "\033[2m"

BANNER_SUBTITLE = "swe agent"


def colorize_gradient(text: str) -> str:
    """Applies a smooth theme gradient left-to-right to the text."""
    if not text:
        return ""
    try:
        from src.config import current_theme
        theme = current_theme()
    except Exception:
        theme = "green"

    n = len(text)
    if theme == "rainbow":
        if n == 1:
            return f"\033[38;2;0;229;163m{text}\033[0m"
        parts = []
        for j, c in enumerate(text):
            h_cycle = abs((float(j) / max(1, n - 1)) * 2 - 1) * 0.55 + 0.15
            r, g, b = colorsys.hsv_to_rgb(h_cycle, 0.9, 0.95)
            parts.append(f"\033[38;2;{int(r * 255)};{int(g * 255)};{int(b * 255)}m{c}")
        parts.append("\033[0m")
        return "".join(parts)
    elif theme == "animated_rainbow":
        if n == 1:
            return f"\033[38;2;0;229;163m{text}\033[0m"
        parts = []
        for j, c in enumerate(text):
            h = (float(j) / max(1, n - 1) + _rainbow_phase) % 1.0
            h_cycle = abs(h * 2 - 1) * 0.55 + 0.15
            r, g, b = colorsys.hsv_to_rgb(h_cycle, 0.9, 0.95)
            parts.append(f"\033[38;2;{int(r * 255)};{int(g * 255)};{int(b * 255)}m{c}")
        parts.append("\033[0m")
        return "".join(parts)

    config = get_theme_config(theme)
    start = config["start"]
    end = config["end"]

    if n == 1:
        return f"{config['accent']}{text}\033[0m"

    parts = []
    for j, c in enumerate(text):
        r = int(start[0] + (end[0] - start[0]) * j / (n - 1))
        g = int(start[1] + (end[1] - start[1]) * j / (n - 1))
        b = int(start[2] + (end[2] - start[2]) * j / (n - 1))
        parts.append(f"\033[38;2;{r};{g};{b}m{c}")
    parts.append("\033[0m")
    return "".join(parts)


_DEFAULT_LOGO = [
    " __  __    ",
    "/\\ \\/ /    ",
    "\\ \\  _\"-.  ",
    " \\ \\_\\ \\_\\ ",
    "  \\/_/\\/_/ ",
    "           ",
]

_LEGACY_LOGO = [
    "  \u2588\u2588\u2557  \u2588\u2588\u2557\u2588\u2588\u2551      \u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557",
    "  \u2588\u2588\u2551 \u2588\u2588\u2554\u255d\u2588\u2588\u2551     \u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u255a\u2550\u2550\u2588\u2588\u2554\u2550\u2550\u255d",
    "  \u2588\u2588\u2588\u2588\u2588\u2554\u255d \u2588\u2588\u2551     \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551   \u2588\u2588\u2551   ",
    "  \u2588\u2588\u2554\u2550\u2588\u2588\u2557 \u2588\u2588\u2551     \u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2551   \u2588\u2588\u2551   ",
    "  \u2588\u2588\u2551  \u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2551  \u2588\u2588\u2551   \u2588\u2588\u2551   ",
    "  \u255a\u2550\u255d  \u255a\u2550\u255d\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u255d\u255a\u2550\u255d  \u255a\u2550\u255d   \u255a\u2550\u255d   ",
]

_EXPERIMENTAL_LOGO = [
    " __  __     __         ______     ______  ",
    "/\\ \\/ /    /\\ \\       /\\  __ \\   /\\__  _\\ ",
    "\\ \\  _\"-.  \\ \\ \\____  \\ \\  __ \\  \\/_/\\ \\/ ",
    " \\ \\_\\ \\_\\  \\ \\_____\\  \\ \\_\\ \\_\\    \\ \\_\\ ",
    "  \\/_/\\/_/   \\/_____/   \\/_/\\/_/     \\/_/ ",
    "                                          ",
]

_LOGO_COLORS = DynamicLogoColors()


def is_session_fresh() -> bool:
    """Return True if no user input or replies have occurred in the current session."""
    try:
        from src import sessions
        transcript = sessions.get_transcript()
        return len([e for e in transcript if e.get('type') in ('user', 'reply')]) == 0
    except Exception:
        return True


def colorize_logo_line(text: str, row: int, theme: str) -> str:
    """Applies logo-specific coloring depending on the theme."""
    if not text:
        return ""
    if theme not in ("rainbow", "animated_rainbow"):
        color = _LOGO_COLORS[row] if row < len(_LOGO_COLORS) else GREEN
        return f"{color}{text}{RESET}"

    parts = []
    phase = _rainbow_phase if theme == "animated_rainbow" else 0.0
    for col, c in enumerate(text):
        if c.isspace():
            parts.append(c)
        else:
            h_cycle = abs(((col / 15.0 + row / 5.0 + phase) % 1.0) * 2 - 1) * 0.55 + 0.15
            r, g, b = colorsys.hsv_to_rgb(h_cycle, 0.9, 0.95)
            parts.append(f"\033[38;2;{int(r * 255)};{int(g * 255)};{int(b * 255)}m{c}")
    return "".join(parts) + RESET


_last_info_lines = []


def print_banner(info_lines: list[str] = ()) -> None:
    """Print the ASCII logo with optional info lines shown to its right."""
    global _last_info_lines
    if info_lines:
        _last_info_lines = list(info_lines)
    try:
        from src.config import get_ascii_style
        style = get_ascii_style()
    except Exception:
        style = "default"

    if style == "legacy":
        logo_lines = _LEGACY_LOGO
    elif style == "experimental":
        logo_lines = _EXPERIMENTAL_LOGO
    else:
        logo_lines = _DEFAULT_LOGO

    logo_w = max(len(l) for l in logo_lines)

    sep = f"  {DIM}\u2502{RESET}  "   # dim │
    rows = max(len(logo_lines), len(info_lines))
    print()
    for i in range(rows):
        raw   = logo_lines[i] if i < len(logo_lines) else ""
        info  = info_lines[i]  if i < len(info_lines)  else ""
        try:
            from src.config import current_theme
            theme = current_theme()
        except Exception:
            theme = "green"
        logo = colorize_logo_line(raw.ljust(logo_w), i, theme)
        print(f"{logo}{sep}{info}")
    print()


# Try importing prompt_toolkit, otherwise fallback to standard input
try:
    import os
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.styles import Style
    from prompt_toolkit.layout.containers import FloatContainer, HSplit, Window
    from prompt_toolkit.layout.menus import CompletionsMenu, MultiColumnCompletionsMenu
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.filters import Condition, has_completions
    from prompt_toolkit.application import get_app
    from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion, AutoSuggestFromHistory
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False

if HAS_PROMPT_TOOLKIT:
    class KlatAutoSuggest(AutoSuggest):
        def __init__(self):
            self.history_suggest = AutoSuggestFromHistory()
            self.commands = [
                "/provider",
                "/model",
                "/reasoning",
                "/streaming",
                "/complexity",
                "/ui",
                "/theme",
                "/setting set",
                "/setting reset",
                "/setting random",
                "/setting",
                "/extension list",
                "/extension create",
                "/extension export",
                "/extension import",
                "/extension dev",
                "/extension enable",
                "/extension disable",
                "/extension remove",
                "/extension",
                "/spoof",
                "/reset",
                "/help",
                "/create",
                "/global",
                "/install",
            ]
            # Sort shortest first so root commands suggest before subcommands
            self.commands.sort(key=len)

        def get_suggestion(self, buffer, document):
            text = document.text
            if not text.startswith("/"):
                return self.history_suggest.get_suggestion(buffer, document)

            # Smart completion for /theme
            if text.startswith("/theme "):
                arg = text[len("/theme "):]
                themes = ["green", "red", "blue", "yellow", "pure white", "orange", "purple", "cyan", "pink", "rainbow", "cyberpunk", "sunset", "matrix", "ocean", "forest"]
                for t in themes:
                    if t.startswith(arg) and t != arg:
                        return Suggestion(t[len(arg):])
                return None

            # Smart completion for /setting set
            if text.startswith("/setting set "):
                arg = text[len("/setting set "):]
                parts = arg.split(None, 1)
                if len(parts) == 2 or (len(parts) == 1 and arg.endswith(" ")):
                    key = parts[0].strip().lower()
                    val = parts[1].strip() if len(parts) == 2 else ""
                    candidates = []
                    if key == "ascii_style":
                        candidates = ["default", "legacy", "experimental"]
                    elif key == "reasoning":
                        candidates = ["none", "minimal", "low", "medium", "high", "xhigh"]
                    elif key == "streaming":
                        candidates = ["on", "off"]
                    elif key == "complexity":
                        candidates = ["nano", "essential", "full"]
                    elif key == "ui_mode":
                        candidates = ["simple", "professional"]
                    elif key == "theme":
                        candidates = ["green", "red", "blue", "yellow", "pure white", "orange", "purple", "cyan", "pink", "rainbow", "cyberpunk", "sunset", "matrix", "ocean", "forest"]
                    elif key == "provider":
                        try:
                            from src.config import configured_providers
                            candidates = sorted(configured_providers())
                        except Exception:
                            pass
                    for c in candidates:
                        if c.startswith(val) and c != val:
                            return Suggestion(c[len(val):])
                else:
                    try:
                        from src.config import get_all_settings
                        keys = sorted(get_all_settings().keys())
                    except Exception:
                        keys = ["ascii_style", "complexity", "model", "provider", "reasoning", "streaming", "theme", "ui_mode"]
                    for k in keys:
                        if k.startswith(arg) and k != arg:
                            return Suggestion(k[len(arg):])
                return None

            # Smart completion for /setting reset
            if text.startswith("/setting reset "):
                arg = text[len("/setting reset "):]
                try:
                    from src.config import get_all_settings
                    keys = sorted(get_all_settings().keys())
                except Exception:
                    keys = ["ascii_style", "complexity", "model", "provider", "reasoning", "streaming", "theme", "ui_mode"]
                for k in keys:
                    if k.startswith(arg) and k != arg:
                        return Suggestion(k[len(arg):])
                return None

            # Smart completion for /setting random
            if text.startswith("/setting random "):
                arg = text[len("/setting random "):]
                keys = ["ascii_style", "complexity", "model", "provider", "reasoning", "streaming", "theme", "ui_mode"]
                for k in keys:
                    if k.startswith(arg) and k != arg:
                        return Suggestion(k[len(arg):])
                return None

            # Smart completion for /provider
            if text.startswith("/provider "):
                arg = text[len("/provider "):]
                
                # Check for subcommands first
                subcmds = ["add", "edit", "remove"]
                for sc in subcmds:
                    if sc.startswith(arg) and sc != arg:
                        return Suggestion(sc[len(arg):])
                        
                # Check for sub-arguments for edit and remove (custom providers only)
                if arg.startswith("edit ") or arg.startswith("remove "):
                    parts = arg.split(None, 1)
                    sub_arg = parts[1] if len(parts) > 1 else ""
                    
                    from pathlib import Path
                    custom_providers = []
                    providers_dir = Path.home() / ".klat" / "settings" / "providers"
                    if providers_dir.exists():
                        try:
                            custom_providers = [p.stem.lower() for p in providers_dir.glob("*.json") if p.is_file()]
                        except Exception:
                            pass
                    for cp in sorted(custom_providers):
                        if cp.startswith(sub_arg) and cp != sub_arg:
                            return Suggestion(cp[len(sub_arg):])
                    return None

                try:
                    from src.config import configured_providers
                    providers = sorted(configured_providers())
                except Exception:
                    providers = []
                for p in providers:
                    if p.startswith(arg) and p != arg:
                        return Suggestion(p[len(arg):])
                return None

            # Smart completion for /reasoning
            if text.startswith("/reasoning "):
                arg = text[len("/reasoning "):]
                levels = ["none", "minimal", "low", "medium", "high", "xhigh"]
                for lvl in levels:
                    if lvl.startswith(arg) and lvl != arg:
                        return Suggestion(lvl[len(arg):])
                return None

            # Smart completion for /complexity
            if text.startswith("/complexity "):
                arg = text[len("/complexity "):]
                levels = ["nano", "essential", "full"]
                for lvl in levels:
                    if lvl.startswith(arg) and lvl != arg:
                        return Suggestion(lvl[len(arg):])
                return None

            # Smart completion for /ui
            if text.startswith("/ui "):
                arg = text[len("/ui "):]
                modes = ["simple", "professional"]
                for m in modes:
                    if m.startswith(arg) and m != arg:
                        return Suggestion(m[len(arg):])
                return None

            # Smart completion for /streaming
            if text.startswith("/streaming "):
                arg = text[len("/streaming "):]
                options = ["on", "off"]
                for opt in options:
                    if opt.startswith(arg) and opt != arg:
                        return Suggestion(opt[len(arg):])
                return None

            # Smart completion for /spoof
            if text.startswith("/spoof "):
                arg = text[len("/spoof "):]
                options = ["codex", "off"]
                for opt in options:
                    if opt.startswith(arg) and opt != arg:
                        return Suggestion(opt[len(arg):])
                return None

            # Smart completion for /extension enable/disable/remove
            if text.startswith("/extension enable "):
                arg = text[len("/extension enable "):]
                try:
                    from src.extensions import list_extensions
                    candidates = [e["folder_name"].replace(".disabled", "") for e in list_extensions() if not e["enabled"]]
                except Exception:
                    candidates = []
                for name in sorted(candidates):
                    if name.startswith(arg) and name != arg:
                        return Suggestion(name[len(arg):])
                return None

            if text.startswith("/extension disable "):
                arg = text[len("/extension disable "):]
                try:
                    from src.extensions import list_extensions
                    candidates = [e["folder_name"].replace(".disabled", "") for e in list_extensions() if e["enabled"]]
                except Exception:
                    candidates = []
                for name in sorted(candidates):
                    if name.startswith(arg) and name != arg:
                        return Suggestion(name[len(arg):])
                return None

            if text.startswith("/extension remove "):
                arg = text[len("/extension remove "):]
                try:
                    from src.extensions import list_extensions
                    candidates = [e["folder_name"].replace(".disabled", "") for e in list_extensions()]
                except Exception:
                    candidates = []
                for name in sorted(candidates):
                    if name.startswith(arg) and name != arg:
                        return Suggestion(name[len(arg):])
                return None

            # Smart completion for dynamic commands
            if text.startswith("/"):
                cmd_line = text[1:]
                if " " in cmd_line:
                    cmd_name, remainder = cmd_line.split(" ", 1)
                    try:
                        from src.extensions import DYNAMIC_COMMANDS
                        if cmd_name in DYNAMIC_COMMANDS:
                            ac_handler = DYNAMIC_COMMANDS[cmd_name].get("autocomplete")
                            if ac_handler:
                                try:
                                    suggestion_str = ac_handler(remainder, document)
                                    if suggestion_str:
                                        return Suggestion(suggestion_str)
                                except Exception:
                                    pass
                    except Exception:
                        pass

            # Default command completion
            try:
                from src.extensions import DYNAMIC_COMMANDS
                all_cmds = self.commands + [f"/{c}" for c in DYNAMIC_COMMANDS]
            except Exception:
                all_cmds = self.commands

            for cmd in all_cmds:
                if cmd.startswith(text) and cmd != text:
                    return Suggestion(cmd[len(text):])
            return None

    class MentionCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            idx = text.rfind('@')
            if idx == -1:
                return
            
            # Check if there are spaces between that '@' and the cursor.
            after_at = text[idx+1:]
            if ' ' in after_at:
                return
            
            # Parse directory part and prefix
            import re
            parts = re.split(r'[/\\]', after_at)
            if len(parts) > 1:
                dir_str = after_at[:len(after_at) - len(parts[-1])]
                prefix = parts[-1]
            else:
                dir_str = ""
                prefix = after_at
            
            from src.tools import WORK_DIR
            search_dir = WORK_DIR
            if dir_str:
                resolved_dir = WORK_DIR / dir_str.replace('/', os.sep).replace('\\', os.sep)
                if resolved_dir.exists() and resolved_dir.is_dir():
                    search_dir = resolved_dir
                else:
                    return
            
            try:
                entries = os.listdir(search_dir)
            except Exception:
                return
            
            for entry in sorted(entries, key=lambda s: (not os.path.isdir(os.path.join(search_dir, s)), s.lower())):
                if entry.lower().startswith(prefix.lower()):
                    full_path = os.path.join(search_dir, entry)
                    is_dir = os.path.isdir(full_path)
                    
                    completion_text = entry
                    if is_dir:
                        sep = '\\' if '\\' in dir_str or (os.sep == '\\' and '/' not in dir_str) else '/'
                        completion_text += sep
                    
                    symbol = "+ "
                    if is_dir:
                        symbol = "> "
                    else:
                        name_lower = entry.lower()
                        if name_lower in ("readme.md", "readme.txt", "readme"):
                            symbol = "i "

                    display_text = f"{symbol}{entry}\\" if is_dir else f"{symbol}{entry}"
                    yield Completion(
                        completion_text,
                        start_position=-len(prefix),
                        display=display_text
                    )

    _prompt_session = None

    def get_prompt_session():
        global _prompt_session
        if _prompt_session is None:
            try:
                from src.config import current_theme
                theme = current_theme()
            except Exception:
                theme = "green"
            theme_hex = get_theme_hex(theme)

            style = Style.from_dict({
                'completion-menu': 'bg:default fg:default',
                'completion-menu.completion': 'fg:#888888 bg:default',
                'completion-menu.completion.current': f'fg:{theme_hex} bg:default bold',
                'scrollbar': 'bg:default fg:default',
                'scrollbar.background': 'bg:default fg:default',
                'scrollbar.button': 'bg:default fg:default',
            })
            
            kb = KeyBindings()

            @Condition
            def is_completion_selected():
                app = get_app()
                buf = app.current_buffer
                return bool(buf.complete_state and buf.complete_state.current_completion)

            @Condition
            def no_completion_selected():
                app = get_app()
                buf = app.current_buffer
                return not (buf.complete_state and buf.complete_state.current_completion)

            # Track when text last changed to detect pastes
            _last_text_change = [time.time()]

            # Enter submits normally. If text changed within the last 60ms,
            # it's likely a paste — insert newline instead of submitting.
            @kb.add('enter', filter=no_completion_selected)
            def _(event):
                buf = event.current_buffer
                if not buf.text.strip():
                    return
                if time.time() - _last_text_change[0] < 0.06:
                    buf.insert_text('\n')
                else:
                    buf.validate_and_handle()

            # Enter accepts the selected completion
            @kb.add('enter', filter=has_completions & is_completion_selected)
            def _(event):
                buf = event.current_buffer
                if buf.complete_state and buf.complete_state.current_completion:
                    comp = buf.complete_state.current_completion
                    is_dir = comp.text.endswith('/') or comp.text.endswith('\\')
                    buf.apply_completion(comp)
                    if is_dir:
                        buf.start_completion()
                    else:
                        buf.insert_text(' ')
                        buf.cancel_completion()

            # ALT+Enter inserts a newline
            @kb.add('escape', 'enter')
            def _(event):
                event.current_buffer.insert_text('\n')

            _prompt_session = PromptSession(
                completer=MentionCompleter(),
                complete_while_typing=True,
                auto_suggest=KlatAutoSuggest(),
                style=style,
                key_bindings=kb,
                multiline=True
            )
            
            @_prompt_session.default_buffer.on_text_changed.add_handler
            def _(buffer):
                _last_text_change[0] = time.time()
                try:
                    from src.tools import _send_vscode_message
                    _send_vscode_message({"action": "status", "state": "idle"})
                except Exception:
                    pass
            
            # Customize the layout of PromptSession to:
            # 1. Start suggestions at the start of the line (left-aligned)
            # 2. Add 1 line of padding from the input box
            root = _prompt_session.layout.container
            def find_float_container(container):
                if isinstance(container, FloatContainer):
                    return container
                if hasattr(container, 'children'):
                    for c in container.children:
                        res = find_float_container(c)
                        if res:
                            return res
                if hasattr(container, 'content'):
                    res = find_float_container(container.content)
                    if res:
                        return res
                if hasattr(container, 'alternative_content'):
                    res = find_float_container(container.alternative_content)
                    if res:
                        return res
                return None

            fc = find_float_container(root)
            if fc:
                for f in fc.floats:
                    if isinstance(f.content, (CompletionsMenu, MultiColumnCompletionsMenu)):
                        f.xcursor = False  # Start of line (left-aligned)
                        f.left = 0  # Align to column 0 of FloatContainer
                        f.content = HSplit([
                            Window(height=1, dont_extend_height=True),  # 1 line padding
                            f.content
                        ])
        return _prompt_session


def format_multiline(text: str) -> str:
    """Format multiline text for display: first line prefixed with '>', rest indented 4 spaces."""
    if not text:
        return ""
    lines = text.split("\n")
    result = f"{GREEN}>{RESET} {lines[0]}"
    for line in lines[1:]:
        result += f"\n    {line}"
    return result


def prompt_input(label: str = "task") -> str:
    """Show a clean prompt and return user input."""
    try:
        if HAS_PROMPT_TOOLKIT:
            session = get_prompt_session()
            prompt_text = ANSI(f"{GREEN}>{RESET} ")
            return session.prompt(prompt_text)
        else:
            lines: list[str] = []
            while True:
                p = f"{GREEN}>{RESET} " if not lines else "    "
                try:
                    line = input(p)
                except (KeyboardInterrupt, EOFError):
                    if not lines:
                        raise
                    print()
                    break
                if not line:
                    break
                lines.append(line)
            return "\n".join(lines)
    except (KeyboardInterrupt, EOFError):
        sys.stdout.write("\033[2K\r")     # clear current line
        sys.stdout.write("\033[1A\033[2K\r")  # move up, clear the ">" prompt line
        sys.stdout.flush()
        print_session_summary()
        sys.exit(0)



def strip_markdown(text: str) -> str:
    """Strip bold, italic, and header markdown that looks bad in a plain terminal."""
    import re
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        # Remove ATX headers: # / ## / ### (and any deeper) at the start of a line
        line = re.sub(r"^#{1,6}\s+", "", line)
        # Remove bold: **text** or __text__
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"__(.+?)__", r"\1", line)
        # Remove italic: *text* or _text_ (but not inside words)
        line = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", line)
        line = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", line)
        # Remove setext-style horizontal rules: lines that are only --- or ***
        if re.match(r"^(\s*[-*]\s*){3,}$", line):
            continue
        # Remove markdown table rows: lines that start and end with |
        if re.match(r"^\s*\|.*\|\s*$", line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def agent_print(text: str) -> None:
    """Print agent output with a green prefix."""
    text = strip_markdown(text)
    print(f"{GREEN}·{RESET} {text}")
    try:
        from src import sessions
        sessions.record_ui_event("reply", text=text)
    except Exception:
        pass



def thinking_label() -> str:
    """Return 'thinking...' or 'Thinking...' based on current UI mode."""
    try:
        from src.config import current_ui_mode
        if current_ui_mode() == "professional":
            return "Thinking..."
    except Exception:
        pass
    return "thinking..."


def agent_thought(text: str) -> None:
    """Print agent internal thought/reasoning in a dim, italic style."""
    if not text.strip():
        return
    print(f"  {DIM}⌁ {thinking_label()}{RESET}")
    for line in text.strip().split("\n"):
        print(f"    {DIM}\033[3m{line}{RESET}")
    try:
        from src import sessions
        sessions.record_ui_event("thought", text=text)
    except Exception:
        pass


def agent_step(action: str, detail: str = "") -> None:
    """Print a single agent action step."""
    from src.config import current_ui_mode
    if current_ui_mode() == "professional":
        action_formatted = action.replace("_", " ").replace("-", " ").title()
    else:
        action_formatted = action

    detail_part = f"  {detail}" if detail else ""
    print(f"  {GREEN}→{RESET} {colorize_gradient(action_formatted)}{DIM}{detail_part}{RESET}")

    try:
        from src import sessions
        sessions.record_ui_event("step", action=action, detail=detail)
    except Exception:
        pass



def agent_done() -> None:
    from src.config import current_ui_mode
    done_label = "Done" if current_ui_mode() == "professional" else "done"
    print(f"\n{GREEN}✓{RESET} {done_label}\n")


def agent_error(msg: str) -> None:
    print(f"\n{GREEN}!{RESET} {msg}\n")
    try:
        from src import sessions
        sessions.record_ui_event("error", text=msg)
    except Exception:
        pass


def print_session_summary() -> None:
    """Print the session token usage summary."""
    try:
        from src import sessions
        from src.config import current_ui_mode
        usage = sessions.get_token_usage()
        inp = usage.get("input", 0)
        out = usage.get("output", 0)
        total = inp + out
        if total == 0:
            return
        
        ui_m = current_ui_mode()
        if ui_m == "professional":
            header = "Session Summary"
            labels = ["Input", "Output", "Total"]
        else:
            header = "session summary"
            labels = ["input", "output", "total"]

        print(f"  {GREEN}{header}{RESET}")
        print(f"  {DIM}─────────────────────────────────────────────────────{RESET}")
        print(f"    {labels[0]:<7}: {GREEN}{inp:,}{RESET}")
        print(f"    {labels[1]:<7}: {GREEN}{out:,}{RESET}")
        print(f"    {labels[2]:<7}: {GREEN}{total:,}{RESET}")
        print(f"  {DIM}─────────────────────────────────────────────────────{RESET}\n")
    except Exception:
        pass


def animate_theme_transition(old_theme: str, new_theme: str) -> None:
    """Instantly update the colors of the banner and the command prompt prefix to the new theme."""
    if old_theme == "animated_rainbow":
        stop_rainbow_animation()

    import sys
    import re

    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    
    try:
        # Save cursor position
        sys.stdout.write("\033[s")
        
        fresh = is_session_fresh()
        if fresh:
            # Move to Row 2, Column 1 (absolute top of the banner)
            sys.stdout.write("\033[2;1H")
            
            # Redraw banner with the new color config
            try:
                from src.config import get_ascii_style
                style = get_ascii_style()
            except Exception:
                style = "default"

            if style == "legacy":
                logo_lines = _LEGACY_LOGO
            elif style == "experimental":
                logo_lines = _EXPERIMENTAL_LOGO
            else:
                logo_lines = _DEFAULT_LOGO

            logo_w = max(len(l) for l in logo_lines)
            sep = f"  {DIM}\u2502{RESET}  "
            
            # Re-colorize the saved info lines
            current_info = []
            for line in _last_info_lines:
                stripped = re.sub(r'\033\[[0-9;]*[a-zA-Z]', '', line)
                parts = re.split(r'\s{2,}', stripped, maxsplit=1)
                if len(parts) == 2:
                    lbl, val = parts[0], parts[1]
                    padded_lbl = lbl.ljust(12)
                    current_info.append(f"{DIM}{padded_lbl}{RESET}{colorize_gradient(val)}")
                else:
                    current_info.append(line)
            
            rows = max(len(logo_lines), len(current_info))
            
            # Overwrite leading blank line and move down 1 line relatively
            sys.stdout.write("\033[K\033[1B\r")
            for i in range(rows):
                raw = logo_lines[i] if i < len(logo_lines) else ""
                info = current_info[i] if i < len(current_info) else ""
                logo = colorize_logo_line(raw.ljust(logo_w), i, new_theme)
                sys.stdout.write(f"\033[K{logo}{sep}{info}\033[1B\r")
            
            # Overwrite trailing blank line
            sys.stdout.write("\033[K")
            
            # Restore cursor
            sys.stdout.write("\033[u")
        
        # Update command prompt prefix `>` on the line above
        sys.stdout.write("\033[1A\r")
        sys.stdout.write(f"{GREEN}>{RESET}")
        
        # Restore cursor to original position
        sys.stdout.write("\033[u")
        sys.stdout.flush()
    finally:
        # Restore cursor visibility
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    if new_theme == "animated_rainbow" and fresh:
        start_rainbow_animation()


def _build_info_lines_for_mode(ui_mode: str) -> list[str]:
    from src.config import current_provider, current_model, current_reasoning
    from src.extensions import list_extensions
    
    # Count enabled extensions
    try:
        ext_count = len([e for e in list_extensions() if e.get("enabled", True)])
    except Exception:
        ext_count = 0
        
    # simple int_to_words mapping for common numbers
    ones = ["none", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", 
            "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", 
            "seventeen", "eighteen", "nineteen"]
    ext_text = ones[ext_count] if ext_count < len(ones) else str(ext_count)
    
    from src import sessions
    active_id = sessions.get_active_session_id()
    is_fresh = len([e for e in sessions.get_transcript() if e.get('type') in ('user', 'reply')]) == 0
    
    if ui_mode == "professional":
        subtitle = "SWE Agent"
        labels = ["Extensions", "Session", "Provider", "Model", "Reasoning"]
        session_val = "Fresh" if is_fresh else active_id
        prov_val = current_provider().title()
        model_val = current_model()
        reasoning_val = current_reasoning().capitalize()
    else:
        subtitle = "swe agent"
        labels = ["extensions", "session", "provider", "model", "reasoning"]
        session_val = "fresh" if is_fresh else active_id
        prov_val = current_provider()
        model_val = current_model()
        reasoning_val = current_reasoning()
        
    return [
        f"{DIM}{subtitle}{RESET}   {colorize_gradient('TreeSoft')}",
        f"{DIM}{labels[0].ljust(10)}{RESET}  {colorize_gradient(ext_text)}",
        f"{DIM}{labels[1].ljust(10)}{RESET}  {colorize_gradient(session_val)}",
        f"{DIM}{labels[2].ljust(10)}{RESET}  {colorize_gradient(prov_val)}",
        f"{DIM}{labels[3].ljust(10)}{RESET}  {colorize_gradient(model_val)}",
        f"{DIM}{labels[4].ljust(10)}{RESET}  {colorize_gradient(reasoning_val)}",
    ]


def animate_ui_mode_transition(old_mode: str, new_mode: str) -> None:
    """Instantly update the capitalisations of the banner labels and prefix."""
    import sys
    global _last_info_lines
    
    # Generate new info lines for the new mode and update the cache
    _last_info_lines = _build_info_lines_for_mode(new_mode)
    
    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    
    try:
        # Save cursor position
        sys.stdout.write("\033[s")
        
        fresh = is_session_fresh()
        if fresh:
            # Move to Row 2, Column 1 (absolute top of the banner)
            sys.stdout.write("\033[2;1H")
            
            # Redraw banner with the new UI mode settings
            try:
                from src.config import get_ascii_style
                style = get_ascii_style()
            except Exception:
                style = "default"
                
            if style == "legacy":
                logo_lines = _LEGACY_LOGO
            elif style == "experimental":
                logo_lines = _EXPERIMENTAL_LOGO
            else:
                logo_lines = _DEFAULT_LOGO
                
            logo_w = max(len(l) for l in logo_lines)
            sep = f"  {DIM}\u2502{RESET}  "
            
            rows = max(len(logo_lines), len(_last_info_lines))
            
            # Overwrite leading blank line and move down 1 line relatively
            sys.stdout.write("\033[K\033[1B\r")
            for i in range(rows):
                raw = logo_lines[i] if i < len(logo_lines) else ""
                info = _last_info_lines[i] if i < len(_last_info_lines) else ""
                try:
                    from src.config import current_theme
                    theme = current_theme()
                except Exception:
                    theme = "green"
                logo = colorize_logo_line(raw.ljust(logo_w), i, theme)
                sys.stdout.write(f"\033[K{logo}{sep}{info}\033[1B\r")
                
            # Overwrite trailing blank line
            sys.stdout.write("\033[K")
            
            # Restore cursor
            sys.stdout.write("\033[u")
            
        # Update command prompt prefix `>` on the line above
        sys.stdout.write("\033[1A\r")
        sys.stdout.write(f"{GREEN}>{RESET}")
        
        # Restore cursor to original position
        sys.stdout.write("\033[u")
        sys.stdout.flush()
    finally:
        # Restore cursor visibility
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
