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
                "/extension list",
                "/extension create",
                "/extension export",
                "/extension import",
                "/extension dev",
                "/extension enable",
                "/extension disable",
                "/extension remove",
                "/extension",
                "/reset",
                "/help",
                "/create",
            ]
            # Sort shortest first so root commands suggest before subcommands
            self.commands.sort(key=len)

        def get_suggestion(self, buffer, document):
            text = document.text
            if not text.startswith("/"):
                return self.history_suggest.get_suggestion(buffer, document)

            # Smart completion for /provider
            if text.startswith("/provider "):
                arg = text[len("/provider "):]
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
            style = Style.from_dict({
                'completion-menu': 'bg:default fg:default',
                'completion-menu.completion': 'fg:#888888 bg:default',
                'completion-menu.completion.current': 'fg:#00b450 bg:default bold',
                'scrollbar': 'bg:default fg:default',
                'scrollbar.background': 'bg:default fg:default',
                'scrollbar.button': 'bg:default fg:default',
            })
            
            # Key bindings to customize Enter behavior when selecting a suggestion
            kb = KeyBindings()
            
            @Condition
            def is_completion_selected():
                app = get_app()
                buf = app.current_buffer
                return bool(buf.complete_state and buf.complete_state.current_completion)
                
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

            @kb.add('escape', 'enter', filter=has_completions & is_completion_selected)
            def _(event):
                buf = event.current_buffer
                if buf.complete_state and buf.complete_state.current_completion:
                    comp = buf.complete_state.current_completion
                    buf.apply_completion(comp)
                    buf.insert_text(' ')
                    buf.cancel_completion()

            _prompt_session = PromptSession(
                completer=MentionCompleter(),
                complete_while_typing=True,
                auto_suggest=KlatAutoSuggest(),
                style=style,
                key_bindings=kb
            )
            
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


def prompt_input(label: str = "task") -> str:
    """Show a clean prompt and return user input."""
    try:
        if HAS_PROMPT_TOOLKIT:
            session = get_prompt_session()
            prompt_text = ANSI(f"{GREEN}>{RESET} ")
            return session.prompt(prompt_text)
        else:
            return input(f"{GREEN}>{RESET} ")
    except (KeyboardInterrupt, EOFError):
        print()
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



def agent_thought(text: str) -> None:
    """Print agent internal thought/reasoning in a dim, italic style."""
    if not text.strip():
        return
    print(f"  {DIM}⌁ thinking...{RESET}")
    for line in text.strip().split("\n"):
        print(f"    {DIM}\033[3m{line}{RESET}")
    try:
        from src import sessions
        sessions.record_ui_event("thought", text=text)
    except Exception:
        pass



def agent_step(action: str, detail: str = "") -> None:
    """Print a single agent action step."""
    import time
    import sys

    action_len = len(action)
    detail_part = f"  {detail}" if detail else ""
    full_len = action_len + len(detail_part)
    
    prefix = f"  {GREEN}→{RESET} "
    delay = 0.04
    
    for step in range(1, full_len + 1):
        if step <= action_len:
            visible_act = action[:step]
            if step < full_len:
                grad_part = colorize_gradient(visible_act[:-1])
                lead_char = visible_act[-1]
                colored_text = f"{grad_part}\033[1;37m{lead_char}\033[0m"
            else:
                colored_text = colorize_gradient(visible_act)
        else:
            act_part = colorize_gradient(action)
            revealed_detail = detail_part[:step - action_len]
            if step < full_len:
                dim_part = f"{DIM}{revealed_detail[:-1]}{RESET}" if len(revealed_detail) > 1 else ""
                lead_char = revealed_detail[-1]
                colored_text = f"{act_part}{dim_part}\033[1;37m{lead_char}\033[0m"
            else:
                dim_part = f"{DIM}{revealed_detail}{RESET}"
                colored_text = f"{act_part}{dim_part}"
                
        sys.stdout.write(f"\r{prefix}{colored_text}\033[K")
        sys.stdout.flush()
        time.sleep(delay)
        
    sys.stdout.write("\n")
    sys.stdout.flush()

    try:
        from src import sessions
        sessions.record_ui_event("step", action=action, detail=detail)
    except Exception:
        pass


def agent_done() -> None:
    print(f"\n{GREEN}✓{RESET} done\n")


def agent_error(msg: str) -> None:
    print(f"\n{GREEN}!{RESET} {msg}\n")
    try:
        from src import sessions
        sessions.record_ui_event("error", text=msg)
    except Exception:
        pass
