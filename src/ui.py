"""
Minimal CLI UI for Klat.
Only one accent color: deep green.
"""

import sys

# Deep green — the only accent color in Klat
GREEN = "\033[38;2;0;180;80m"
RESET = "\033[0m"
DIM   = "\033[2m"

BANNER_SUBTITLE = "swe agent"


def colorize_gradient(text: str) -> str:
    """Applies a smooth green gradient (from #00b450 to #02db63) left-to-right to the text."""
    if not text:
        return ""
    n = len(text)
    if n == 1:
        return f"\033[38;2;0;180;80m{text}\033[0m"
    
    parts = []
    for j, c in enumerate(text):
        r = int(0 + 2 * j / (n - 1))
        g = int(180 + 39 * j / (n - 1))
        b = int(80 + 19 * j / (n - 1))
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

_LOGO_COLORS = [
    "\033[38;2;0;180;80m",
    "\033[38;2;0;188;84m",
    "\033[38;2;1;196;88m",
    "\033[38;2;1;203;91m",
    "\033[38;2;2;211;95m",
    "\033[38;2;2;219;99m",
]


def print_banner(info_lines: list[str] = ()) -> None:
    """Print the ASCII logo with optional info lines shown to its right."""
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
        color = _LOGO_COLORS[i] if i < len(_LOGO_COLORS) else GREEN
        logo  = f"{color}{raw.ljust(logo_w)}{RESET}"
        print(f"{logo}{sep}{info}")
    print()


def prompt_input(label: str = "task") -> str:
    """Show a clean prompt and return user input."""
    try:
        return input(f"{GREEN}>{RESET} {label}: ")
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)


def agent_print(text: str) -> None:
    """Print agent output with a green prefix."""
    print(f"{GREEN}·{RESET} {text}")


def agent_step(action: str, detail: str = "") -> None:
    """Print a single agent action step."""
    detail_str = f"  {DIM}{detail}{RESET}" if detail else ""
    print(f"  {GREEN}→{RESET} {action}{detail_str}")


def agent_done() -> None:
    print(f"\n{GREEN}✓{RESET} done\n")


def agent_error(msg: str) -> None:
    print(f"\n{GREEN}!{RESET} {msg}\n")
