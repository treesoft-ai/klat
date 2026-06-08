"""
Klat — a simple conversational chatbot by TreeSoft.
"""

import sys
from src.config import ensure_env, current_provider, current_model, set_provider, set_model, current_reasoning, set_reasoning, get_all_settings, set_config_value, reset_config_value, randomize_config_value, current_complexity, set_complexity, COMPLEXITY_LEVELS, current_theme, set_theme, current_ui_mode, set_ui_mode
from src.providers import PROVIDERS, PROVIDER_NAMES, get_provider
from src import ui
from src.ui import print_banner, prompt_input, agent_print, agent_error, GREEN, DIM, RESET
from src.agent import KlatAgent
from src.extensions import (
    load_extensions, export_extension, import_extension, import_extension_directory,
    list_extensions, enable_extension, disable_extension, remove_extension,
    create_extension, DYNAMIC_COMMANDS
)





# ---------------------------------------------------------------------------
# Slash-command handlers
# ---------------------------------------------------------------------------

def _cmd_provider(args: str) -> None:
    """Handle /provider [name] — list or switch providers."""
    name = args.strip().lower()

    if not name:
        # List all providers
        print(f"\n  {'Provider':<14}  {'Default model':<38}  Notes")
        print(f"  {'-'*14}  {'-'*38}  {'-'*40}")
        for key, p in PROVIDERS.items():
            active = f"{GREEN}*{RESET}" if key == current_provider() else " "
            print(
                f"  {active} {key:<13}  {DIM}{p['default_model']:<38}{RESET}  "
                f"{DIM}{p['notes']}{RESET}"
            )
        print(f"\n  Active: {GREEN}{current_provider()}{RESET}  model: {GREEN}{current_model()}{RESET}\n")
        return

    try:
        set_provider(name)
        p = get_provider(name)
        agent_print(
            f"Switched to {GREEN}{p['display_name']}{RESET}  "
            f"(default model: {DIM}{current_model()}{RESET})"
        )
    except ValueError as e:
        agent_error(str(e))
        print(f"  Available: {', '.join(PROVIDER_NAMES)}\n")


def _cmd_model(args: str) -> None:
    """Handle /model [name] — show or change the active model."""
    name = args.strip()

    if not name:
        p = get_provider(current_provider())
        print(
            f"\n  Provider : {GREEN}{current_provider()}{RESET}  ({p['display_name']})\n"
            f"  Model    : {GREEN}{current_model()}{RESET}\n"
            f"  Default  : {DIM}{p['default_model']}{RESET}\n"
        )
        return

    set_model(name)
    agent_print(f"Model set to {GREEN}{name}{RESET}")


def _cmd_reasoning(args: str) -> None:
    """Handle /reasoning [level] — show or change the reasoning level."""
    val = args.strip()

    if not val:
        print(f"\n  Reasoning Level: {GREEN}{current_reasoning().capitalize()}{RESET}\n")
        return

    try:
        set_reasoning(val)
        agent_print(f"Reasoning set to {GREEN}{current_reasoning().capitalize()}{RESET}")
    except ValueError as e:
        agent_error(str(e))
        print("  Available levels: None, Minimal, Low, Medium, High, XHigh\n")


def _cmd_streaming(args: str) -> None:
    """Handle /streaming [on/off] — show or change the streaming setting."""
    from src.config import current_streaming, set_streaming
    val = args.strip().lower()

    if not val:
        status = "On" if current_streaming() else "Off"
        print(f"\n  Streaming: {GREEN}{status}{RESET}\n")
        return

    if val in ("on", "true", "1"):
        set_streaming(True)
        agent_print(f"Streaming set to {GREEN}On{RESET}")
    elif val in ("off", "false", "0"):
        set_streaming(False)
        agent_print(f"Streaming set to {GREEN}Off{RESET}")
    else:
        agent_error(f"Invalid streaming value '{args}'. Use 'on' or 'off'.")


def _cmd_setting(args: str) -> None:
    """Handle /setting subcommands: set, reset, random or list all settings."""
    parts = args.strip().split(None, 2)
    if not parts:
        from src.config import current_ui_mode
        settings = get_all_settings()
        ui_m = current_ui_mode()
        title = "Klat Settings"
        print(f"\n  {GREEN}{title}{RESET}")
        print("  ─────────────────────────────────────────────────────")
        for k, v in sorted(settings.items()):
            display_key = k.replace("_", " ").title() if ui_m == "professional" else k
            display_val = str(v).capitalize() if (ui_m == "professional" and isinstance(v, str) and v in ("nano", "essential", "full", "simple", "professional", "on", "off", "none", "minimal", "low", "medium", "high", "xhigh")) else v
            print(f"  {display_key:<20}: {GREEN}{display_val}{RESET}")
        print("  ─────────────────────────────────────────────────────\n")
        return

    subcmd = parts[0].lower()
    
    if subcmd == "set":
        if len(parts) < 3:
            agent_error("Usage: /setting set <key> <value>")
            return
        key = parts[1].strip()
        val = parts[2].strip()
        try:
            set_config_value(key, val)
            agent_print(f"Setting '{GREEN}{key}{RESET}' set to '{GREEN}{val}{RESET}'")
        except Exception as e:
            agent_error(str(e))

    elif subcmd == "reset":
        if len(parts) < 2:
            agent_error("Usage: /setting reset <key>")
            return
        key = parts[1].strip()
        try:
            reset_config_value(key)
            agent_print(f"Setting '{GREEN}{key}{RESET}' reset to default")
        except Exception as e:
            agent_error(str(e))

    elif subcmd == "random":
        if len(parts) < 2:
            agent_error("Usage: /setting random <key>")
            return
        key = parts[1].strip()
        try:
            val = randomize_config_value(key)
            agent_print(f"Setting '{GREEN}{key}{RESET}' randomized to '{GREEN}{val}{RESET}'")
        except Exception as e:
            agent_error(str(e))
    else:
        agent_error(f"Unknown setting action: {subcmd}. Use 'set', 'reset', or 'random'.")


def _cmd_extension(args: str, agent: KlatAgent) -> None:
    """Handle /extension subcommands: list, export, import, enable, disable, remove, create, dev"""
    parts = args.strip().split(None, 1)
    if not parts:
        print(f"\n  {GREEN}Klat Extension Management{RESET}")
        print("  ─────────────────────────────────────────────────────")
        print("  /extension list                 list installed extensions")
        print("  /extension create <folder>      generate boilerplate extension folder")
        print("  /extension export <folder>      export folder into a .ke file")
        print("  /extension import <file.ke>     import and hot-load a .ke file")
        print("  /extension dev <folder>         import and hot-load a directory directly")
        print("  /extension enable <name>        enable an extension")
        print("  /extension disable <name>       disable an extension")
        print("  /extension remove <name>        remove an extension completely")
        print("  ─────────────────────────────────────────────────────\n")
        return

    subcmd = parts[0].lower()
    remainder = parts[1].strip() if len(parts) > 1 else ""

    # Strip quotes if path has quotes
    if (remainder.startswith('"') and remainder.endswith('"')) or (remainder.startswith("'") and remainder.endswith("'")):
        remainder = remainder[1:-1]

    if subcmd == "list":
        exts = list_extensions()
        if not exts:
            agent_print("No extensions installed.")
            return
        print(f"\n  {GREEN}Installed Extensions:{RESET}")
        print("  ─────────────────────────────────────────────────────")
        for e in exts:
            status = f"{GREEN}enabled{RESET}" if e["enabled"] else f"{DIM}disabled{RESET}"
            print(f"  - {GREEN}{e['name']}{RESET} (v{e['version']}) — {status}")
            if e["description"]:
                print(f"    {DIM}{e['description']}{RESET}")
        print("  ─────────────────────────────────────────────────────\n")

    elif subcmd == "create":
        if not remainder:
            agent_error("Usage: /extension create <folder-path>")
            return
        try:
            path = create_extension(remainder)
            agent_print(f"Boilerplate extension created at: {GREEN}{path}{RESET}")
        except Exception as e:
            agent_error(f"Failed to create extension: {e}")

    elif subcmd == "export":
        if not remainder:
            agent_error("Usage: /extension export <folder-path>")
            return
        try:
            zip_path = export_extension(remainder)
            agent_print(f"Extension successfully exported to: {GREEN}{zip_path}{RESET}")
        except Exception as e:
            agent_error(f"Failed to export extension: {e}")

    elif subcmd == "import":
        if not remainder:
            agent_error("Usage: /extension import <file-path>")
            return
        try:
            ext_name = import_extension(remainder)
            agent_print(f"Extension '{GREEN}{ext_name}{RESET}' successfully imported!")
            active_count = load_extensions(silent=True)
            from src.agent import rebuild_system_prompt
            rebuild_system_prompt()
            agent.refresh_system_prompt()
            agent_print(f"Extension '{GREEN}{ext_name}{RESET}' is now active! (Total active: {active_count})")
        except Exception as e:
            agent_error(f"Failed to import extension: {e}")

    elif subcmd == "dev":
        if not remainder:
            agent_error("Usage: /extension dev <folder-path>")
            return
        try:
            ext_name = import_extension_directory(remainder)
            agent_print(f"Extension '{GREEN}{ext_name}{RESET}' successfully imported in dev mode!")
            active_count = load_extensions(silent=True)
            from src.agent import rebuild_system_prompt
            rebuild_system_prompt()
            agent.refresh_system_prompt()
            agent_print(f"Extension '{GREEN}{ext_name}{RESET}' is now active! (Total active: {active_count})")
        except Exception as e:
            agent_error(f"Failed to import extension in dev mode: {e}")

    elif subcmd in ("enable", "disable", "remove"):
        if not remainder:
            agent_error(f"Usage: /extension {subcmd} <extension-name> or '*'")
            return
        try:
            if remainder == "*":
                exts = list_extensions()
                if not exts:
                    agent_print("No extensions installed.")
                    return

                if subcmd == "remove":
                    confirm = input(f"  {ui.GREEN}!{ui.RESET} Are you sure you want to remove ALL extensions? (y/N): ").strip().lower()
                    if confirm not in ("y", "yes"):
                        agent_print("Action cancelled.")
                        return

                acted = False
                for e in exts:
                    clean_name = e["folder_name"].replace(".disabled", "")
                    if subcmd == "enable" and not e["enabled"]:
                        enable_extension(clean_name)
                        acted = True
                    elif subcmd == "disable" and e["enabled"]:
                        disable_extension(clean_name)
                        acted = True
                    elif subcmd == "remove":
                        remove_extension(clean_name)
                        acted = True

                if acted:
                    agent_print(f"All eligible extensions {subcmd}d successfully!")
                else:
                    agent_print(f"No extensions needed to be {subcmd}d.")
            else:
                if subcmd == "enable":
                    enable_extension(remainder)
                    agent_print(f"Extension '{GREEN}{remainder}{RESET}' enabled successfully!")
                elif subcmd == "disable":
                    disable_extension(remainder)
                    agent_print(f"Extension '{GREEN}{remainder}{RESET}' disabled successfully!")
                else:
                    remove_extension(remainder)
                    agent_print(f"Extension '{GREEN}{remainder}{RESET}' removed successfully!")

            # Hot reload extensions list and update active prompt immediately
            active_count = load_extensions(silent=True)
            from src.agent import rebuild_system_prompt
            rebuild_system_prompt()
            agent.refresh_system_prompt()
            agent_print(f"Reloaded. Active extensions: {GREEN}{int_to_words(active_count)}{RESET}")
        except Exception as e:
            agent_error(f"Action failed: {e}")
    else:
        agent_error(f"Unknown extension subcommand: {subcmd}. Type /extension for usage.")


def _get_info_lines(ext_text: str) -> list[str]:
    from src import sessions
    from src.config import current_ui_mode
    active_id = sessions.get_active_session_id()
    is_fresh = len([e for e in sessions.get_transcript() if e.get('type') in ('user', 'reply')]) == 0

    ui_m = current_ui_mode()
    if ui_m == "professional":
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
        f"{DIM}{subtitle}{RESET}   {ui.colorize_gradient('TreeSoft')}",
        f"{DIM}{labels[0].ljust(10)}{RESET}  {ui.colorize_gradient(ext_text)}",
        f"{DIM}{labels[1].ljust(10)}{RESET}  {ui.colorize_gradient(session_val)}",
        f"{DIM}{labels[2].ljust(10)}{RESET}  {ui.colorize_gradient(prov_val)}",
        f"{DIM}{labels[3].ljust(10)}{RESET}  {ui.colorize_gradient(model_val)}",
        f"{DIM}{labels[4].ljust(10)}{RESET}  {ui.colorize_gradient(reasoning_val)}",
    ]


def _cmd_session(args: str, agent: KlatAgent, project: str, location: str) -> KlatAgent:
    """Handle /session subcommands: list, new, load, delete"""
    parts = args.strip().split(None, 1)
    if not parts:
        print(f"\n  {GREEN}Klat Session Management{RESET}")
        print("  ─────────────────────────────────────────────────────")
        print("  /session list                 list all saved sessions")
        print("  /session new [id]             start a new session (replaces /reset)")
        print("  /session load <id>            load a saved session")
        print("  /session delete <id>          delete a session")
        print("  ─────────────────────────────────────────────────────\n")
        return agent

    subcmd = parts[0].lower()
    remainder = parts[1].strip() if len(parts) > 1 else ""

    from src import sessions

    if subcmd == "list":
        exts = sessions.list_sessions()
        if not exts:
            agent_print("No saved sessions found.")
            return agent
        print(f"\n  {GREEN}Saved Sessions:{RESET}")
        print("  ─────────────────────────────────────────────────────")
        active = sessions.get_active_session_id()
        for e in exts:
            status = f"{GREEN}(active){RESET}" if e == active else ""
            print(f"  - {e} {status}")
        print("  ─────────────────────────────────────────────────────\n")
        return agent

    elif subcmd == "new":
        import os
        os.system('cls' if os.name == 'nt' else 'clear')

        if remainder:
            new_id = remainder
        else:
            from datetime import datetime
            new_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        sessions.clear_transcript()
        sessions.set_active_session_id(new_id)

        # Reset the agent history and save
        agent = KlatAgent(project, location)
        agent.reset()

        # Print banner
        ext_count = load_extensions(silent=True)
        ext_text = int_to_words(ext_count)
        print_banner(_get_info_lines(ext_text))
        agent_print(f"Started new session: {GREEN}{new_id}{RESET}")
        return agent

    elif subcmd == "load":
        if not remainder:
            agent_error("Usage: /session load <session-id>")
            return agent

        session_file = sessions.get_sessions_dir() / remainder / "session.json"
        if not session_file.exists():
            agent_error(f"Session '{remainder}' not found.")
            return agent

        import os
        os.system('cls' if os.name == 'nt' else 'clear')

        sessions.set_active_session_id(remainder)
        session_data = sessions.load_session(remainder)

        if session_data:
            from src import config
            config.apply_session_settings(
                session_data.get("provider", ""),
                session_data.get("model", ""),
                session_data.get("reasoning", "none")
            )

        # Re-initialize the agent
        agent = KlatAgent(project, location)

        # Print banner
        ext_count = load_extensions(silent=True)
        ext_text = int_to_words(ext_count)
        print_banner(_get_info_lines(ext_text))

        # Replay the transcript
        sessions.replay_transcript()

        agent_print(f"Loaded session: {GREEN}{remainder}{RESET}")
        return agent

    elif subcmd == "delete":
        if not remainder:
            agent_error("Usage: /session delete <session-id>")
            return agent

        session_dir = sessions.get_sessions_dir() / remainder
        if not session_dir.exists():
            agent_error(f"Session '{remainder}' not found.")
            return agent

        sessions.delete_session(remainder)
        agent_print(f"Session '{GREEN}{remainder}{RESET}' deleted.")

        # If the deleted session was active, start a new one
        if remainder == sessions.get_active_session_id():
            agent = _cmd_session("new", agent, project, location)

        return agent

    else:
        agent_error(f"Unknown session subcommand: {subcmd}. Type /session for usage.")
        return agent


KLAT_MD_PATH = "KLAT.md"


def _run_klat_analysis() -> None:
    """Core logic shared by /create and /update — gather context, analyze, write KLAT.md."""
    import time
    from src.ui import agent_print, agent_step, agent_error
    from src.agent import run_single_completion, _gather_project_context, ANALYSIS_SYSTEM_PROMPT
    from src.tools import _write_file

    agent_print("Starting automated project analysis...")
    agent_step("gather", "Reading files and generating directory structure")

    start_time = time.time()
    try:
        context = _gather_project_context()
        prompt = f"Please analyze this project context and generate the KLAT.md analysis file.\n\nProject Context:\n{context}"

        agent_step("analyze", "Analyzing codebase architecture via LLM")
        analysis = run_single_completion(prompt, ANALYSIS_SYSTEM_PROMPT)

        agent_step("write", "Saving analysis to KLAT.md")
        _write_file(KLAT_MD_PATH, analysis)

        elapsed = time.time() - start_time
        agent_print(f"Project analysis successfully compiled and written to {KLAT_MD_PATH} ({len(analysis)} chars, {elapsed:.1f}s)")
    except Exception as e:
        agent_error(f"Failed to generate project analysis: {e}")


def _cmd_create(agent: KlatAgent) -> None:
    """Handle /create — analyze the codebase and write project context to KLAT.md."""
    import os
    from src.ui import agent_print

    if os.path.exists(KLAT_MD_PATH):
        agent_print(f"{KLAT_MD_PATH} already exists. Run {GREEN}/update{RESET} to regenerate it.")
        return

    _run_klat_analysis()
    agent._update_run_notification = True


def _cmd_update(agent: KlatAgent) -> None:
    """Handle /update — re-analyze the codebase and overwrite KLAT.md."""
    _run_klat_analysis()
    agent._update_run_notification = True


def _cmd_demo() -> None:
    """Handle /demo — run the interactive logo viewer."""
    from src import demo
    from src.config import current_theme
    from src.ui import stop_rainbow_animation, start_rainbow_animation

    was_animated = (current_theme() == "animated_rainbow")
    if was_animated:
        stop_rainbow_animation()

    demo.main()

    # Restore Klat UI
    import os
    os.system('cls' if os.name == 'nt' else 'clear')

    ext_count = load_extensions(silent=True)
    ext_text = int_to_words(ext_count)
    print_banner(_get_info_lines(ext_text))

    if was_animated:
        start_rainbow_animation()

    from src import sessions
    sessions.replay_transcript()
    print(f"\n  {GREEN}🌿{RESET} Klat Demo finished.\n")


def _cmd_help() -> None:
    from src.config import current_ui_mode
    ui_m = current_ui_mode()
    title = "Klat Slash Commands" if ui_m == "professional" else "Klat slash commands"
    print(f"""
  {GREEN}{title}{RESET}
  ─────────────────────────────────────────────────────
  /provider              list all providers
  /provider <name>       switch active provider
  /model                 show current model
  /model <name>          set model for this session
  /reasoning             show current reasoning level
  /reasoning <level>     set reasoning level (None, Minimal, Low, Medium, High, XHigh)
  /streaming             show current streaming status
  /streaming <on|off>    toggle streaming response on or off
  /complexity            show current complexity level
  /complexity <level>    set complexity level (nano, essential, full)
  /ui                    show current UI mode
  /ui <mode>             set UI mode (simple, professional)
  /theme                 list all themes
  /theme <name>          set theme (presets or two hex codes for custom)
  /setting               show all settings and their current values
  /setting set <k> <v>   set setting key <k> to value <v>
  /setting reset <k>     reset setting key <k> to default
  /setting random <k>    randomize setting key <k>
  /onboard               re-run onboarding (personal questions + provider setup)
  /create                analyze codebase and generate project reference KLAT.md
  /update                re-analyze codebase and overwrite KLAT.md
  /extension             extension manager options
  /extension list        list installed extensions
  /extension create <d>  generate a boilerplate extension folder
  /extension export <d>  export a folder into a .ke file
  /extension import <f>  import and hot-load a .ke extension file
  /extension dev <f>     import and hot-load an extension directory directly
  /extension enable <n>  enable a disabled extension
  /extension disable <n> disable an active extension
  /extension remove <n>  uninstall/delete an extension
  /session               session manager options
  /session list          list all saved sessions
  /session new [id]      start a new session (replaces /reset)
  /session load <id>     load a saved session
  /session delete <id>   delete a session
  /reset                 alias for /session new
  /demo                  run the interactive Klat logo viewer
  exit / quit / q        exit Klat
  ─────────────────────────────────────────────────────
  Providers: {', '.join(PROVIDER_NAMES)}
""")


def _cmd_onboard(agent: KlatAgent) -> None:
    """Handle /onboard — re-run the onboarding wizard (overwrites preferences)."""
    from src.onboarding import run_full_onboarding
    run_full_onboarding(force=True)
    from src.agent import rebuild_system_prompt
    rebuild_system_prompt()
    agent.refresh_system_prompt()



def _cmd_complexity(args: str, agent: "KlatAgent") -> None:
    """Handle /complexity [level] — show or change the complexity level."""
    val = args.strip().lower()

    if not val:
        level = current_complexity()
        print(f"\n  Complexity: {GREEN}{level.capitalize()}{RESET}")
        print(f"  {DIM}nano{RESET}      — minimal chat assistant, no tools, tiny prompt")
        print(f"  {DIM}essential{RESET} — core file/git tools, trimmed prompt")
        print(f"  {DIM}full{RESET}      — all tools, full prompt (default)")
        print()
        return

    try:
        set_complexity(val)
        from src.agent import rebuild_system_prompt
        rebuild_system_prompt()
        agent.refresh_system_prompt()
        agent_print(f"Complexity set to {GREEN}{current_complexity().capitalize()}{RESET}")
    except ValueError as e:
        agent_error(str(e))
        print(f"  Available levels: {', '.join(COMPLEXITY_LEVELS)}\n")


def _cmd_ui(args: str, agent: "KlatAgent") -> None:
    """Handle /ui [mode] — show or change the UI mode."""
    from src.config import current_ui_mode, set_ui_mode
    val = args.strip().lower()

    if not val:
        mode = current_ui_mode()
        print(f"\n  UI Mode: {GREEN}{mode.capitalize()}{RESET}")
        print(f"  {DIM}simple{RESET}       — simple clean UI, all lowercase labels")
        print(f"  {DIM}professional{RESET} — professional UI, capitalized labels and actions")
        print()
        return

    try:
        set_ui_mode(val)
        agent_print(f"UI mode set to {GREEN}{current_ui_mode().capitalize()}{RESET}")
    except ValueError as e:
        agent_error(str(e))
        print("  Available modes: simple, professional\n")


def _cmd_theme(args: str) -> None:
    """Handle /theme [name] — show or change the active theme."""
    name = args.strip().lower()

    if name in ("pure white", "pure_white", "white"):
        name = "pure white"

    if not name:
        themes = ["green", "red", "blue", "yellow", "pure white", "orange", "purple", "cyan", "pink", "rainbow", "cyberpunk", "sunset", "matrix", "ocean", "forest"]
        print(f"\n  Available themes:")
        print(f"  ─────────────────────────────────────────────────────")
        current = current_theme()
        for t in themes:
            active = f"{GREEN}*{RESET}" if t == current else " "
            print(f"  {active} {t}")
        if current not in themes:
            print(f"  {GREEN}*{RESET} custom: {current}")
        print(f"  ─────────────────────────────────────────────────────\n")
        return

    try:
        set_theme(args.strip())
        agent_print(f"Theme set to {GREEN}{current_theme()}{RESET}")
    except ValueError as e:
        agent_error(str(e))
        print("  Available themes: green, red, blue, yellow, pure white, orange, purple, cyan, pink, rainbow, cyberpunk, sunset, matrix, ocean, forest\n")
        print("  Or enter two hex codes for a custom theme (e.g. '/theme #ff0055 #00ffcc')\n")


def int_to_words(n: int) -> str:
    """Convert an integer to a hyphenated word representation (e.g. two-hundred-and-eleven)."""
    if n == 0:
        return "none"
    
    ones = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", 
            "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", 
            "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    
    if n < 20:
        return ones[n]
    if n < 100:
        suffix = ones[n % 10]
        prefix = tens[n // 10]
        return f"{prefix}-{suffix}" if suffix else prefix
    if n < 1000:
        hundreds = ones[n // 100]
        remainder = n % 100
        if remainder:
            return f"{hundreds}-hundred-and-{int_to_words(remainder)}"
        return f"{hundreds}-hundred"
    return str(n)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, IOError):
        pass

    session_id = None
    if len(sys.argv) > 1:
        for i in range(1, len(sys.argv)):
            if sys.argv[i] == "--session" and i + 1 < len(sys.argv):
                session_id = sys.argv[i+1]
                break

    from src import sessions
    if session_id:
        sessions.set_active_session_id(session_id)
        # Apply settings if the session exists on disk
        session_data = sessions.load_session(session_id)
        if session_data:
            from src import config
            config.apply_session_settings(
                session_data.get("provider", ""),
                session_data.get("model", ""),
                session_data.get("reasoning", "none")
            )
    else:
        from datetime import datetime
        new_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        sessions.clear_transcript()
        sessions.set_active_session_id(new_id)

    project, location = ensure_env()

    # Load existing extensions silently
    ext_count = load_extensions(silent=True)
    ext_text = int_to_words(ext_count)

    # Rebuild system prompt to include loaded extension tools/rules
    from src.agent import rebuild_system_prompt
    rebuild_system_prompt()

    agent = KlatAgent(project, location)

    # Save session state immediately on startup so it exists on disk
    p = get_provider(current_provider())
    backend = p["backend"]
    history = agent._gemini_history if backend == "gemini" else agent._openai_messages
    sessions.save_session(
        session_id=sessions.get_active_session_id(),
        provider=current_provider(),
        model=current_model(),
        reasoning=current_reasoning(),
        history=history,
        backend=backend
    )

    print_banner(_get_info_lines(ext_text))

    from src.ui import is_session_fresh
    if current_theme() == "animated_rainbow" and is_session_fresh():
        from src.ui import start_rainbow_animation
        start_rainbow_animation()

    # Replay transcript on startup if it exists
    active_id = sessions.get_active_session_id()
    session_data = sessions.load_session(active_id)
    if session_data:
        sessions.replay_transcript()

    _agent_busy = False
    while True:
        try:
            raw = prompt_input("you").strip()
            if not raw:
                continue

            # ── Exit ──────────────────────────────────────────────────────────
            if raw.lower() in {"exit", "quit", "q"}:
                print()
                ui.print_session_summary()
                sys.exit(0)

            # ── Slash commands ────────────────────────────────────────────
            if raw.startswith("/"):
                sessions.record_ui_event("command", text=raw)
                parts     = raw[1:].split(None, 1)   # strip the leading "/"
                cmd       = parts[0].lower()
                remainder = parts[1] if len(parts) > 1 else ""

                if cmd == "demo":
                    _cmd_demo()
                    p = get_provider(current_provider())
                    backend = p["backend"]
                    history = agent._gemini_history if backend == "gemini" else agent._openai_messages
                    sessions.save_session(
                        session_id=sessions.get_active_session_id(),
                        provider=current_provider(),
                        model=current_model(),
                        reasoning=current_reasoning(),
                        history=history,
                        backend=backend
                    )
                    continue

                # Intercept stdout to capture output of command
                import sys
                from src.sessions import OutputInterceptor, set_replaying
                interceptor = OutputInterceptor(sys.stdout)
                original_stdout = sys.stdout
                sys.stdout = interceptor
                set_replaying(True)

                try:
                    if cmd == "setting":
                        _cmd_setting(remainder)
                    elif cmd == "provider":
                        _cmd_provider(remainder)
                    elif cmd == "model":
                        _cmd_model(remainder)
                    elif cmd == "reasoning":
                        _cmd_reasoning(remainder)
                    elif cmd == "streaming":
                        _cmd_streaming(remainder)
                    elif cmd == "complexity":
                        _cmd_complexity(remainder, agent)
                    elif cmd == "ui":
                        _cmd_ui(remainder, agent)
                    elif cmd == "theme":
                        _cmd_theme(remainder)
                    elif cmd == "onboard":
                        _cmd_onboard(agent)
                    elif cmd == "extension":
                        _cmd_extension(remainder, agent)
                    elif cmd == "session":
                        agent = _cmd_session(remainder, agent, project, location)
                    elif cmd == "create":
                        _cmd_create(agent)
                    elif cmd == "update":
                        _cmd_update(agent)
                    elif cmd in {"help", "?"}:
                        _cmd_help()
                    elif cmd == "reset":
                        agent = _cmd_session("new", agent, project, location)
                    elif cmd in DYNAMIC_COMMANDS:
                        res = DYNAMIC_COMMANDS[cmd]["handler"](remainder, agent)
                        if isinstance(res, KlatAgent):
                            agent = res
                    else:
                        agent_error(f"Unknown command /{cmd}. Type /help for commands.")
                finally:
                    sys.stdout = original_stdout
                    set_replaying(False)

                # Record the captured output in the transcript
                captured = "".join(interceptor.captured_text)
                if captured:
                    sessions.record_ui_event("command_output", text=captured)

                # Save session state after executing slash command to preserve settings changes & command in transcript
                p = get_provider(current_provider())
                backend = p["backend"]
                history = agent._gemini_history if backend == "gemini" else agent._openai_messages
                sessions.save_session(
                    session_id=sessions.get_active_session_id(),
                    provider=current_provider(),
                    model=current_model(),
                    reasoning=current_reasoning(),
                    history=history,
                    backend=backend
                )
                continue

            # ── Chat ──────────────────────────────────────────────────────
            _agent_busy = True
            sessions.record_ui_event("user", text=raw)
            agent.chat(raw)
            _agent_busy = False

        except KeyboardInterrupt:
            _agent_busy = False
            print()
            agent_error("Stopped.")
        except Exception as e:
            _agent_busy = False
            agent_error(str(e))


if __name__ == "__main__":
    main()
