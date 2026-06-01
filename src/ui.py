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


_LOGO_LINES = [
    "  \u2588\u2588\u2557  \u2588\u2588\u2557\u2588\u2588\u2551      \u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557",
    "  \u2588\u2588\u2551 \u2588\u2588\u2554\u255d\u2588\u2588\u2551     \u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u255a\u2550\u2550\u2588\u2588\u2554\u2550\u2550\u255d",
    "  \u2588\u2588\u2588\u2588\u2588\u2554\u255d \u2588\u2588\u2551     \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551   \u2588\u2588\u2551   ",
    "  \u2588\u2588\u2554\u2550\u2588\u2588\u2557 \u2588\u2588\u2551     \u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2551   \u2588\u2588\u2551   ",
    "  \u2588\u2588\u2551  \u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2551  \u2588\u2588\u2551   \u2588\u2588\u2551   ",
    "  \u255a\u2550\u255d  \u255a\u2550\u255d\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u255d\u255a\u2550\u255d  \u255a\u2550\u255d   \u255a\u2550\u255d   ",
]

_LOGO_W = max(len(l) for l in _LOGO_LINES)  # all lines same width; used for padding


def print_banner(info_lines: list[str] = ()) -> None:
    """Print the ASCII logo with optional info lines shown to its right."""
    sep = f"  {DIM}\u2502{RESET}  "   # dim │
    rows = max(len(_LOGO_LINES), len(info_lines))
    print()
    for i in range(rows):
        raw   = _LOGO_LINES[i] if i < len(_LOGO_LINES) else ""
        info  = info_lines[i]  if i < len(info_lines)  else ""
        logo  = f"{GREEN}{raw.ljust(_LOGO_W)}{RESET}"
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
