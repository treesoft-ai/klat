"""
Klat — a simple conversational chatbot by TreeSoft.
"""

import sys
from src.config import ensure_env, current_provider, current_model, set_provider, set_model
from src.providers import PROVIDERS, PROVIDER_NAMES, get_provider
from src import ui
from src.ui import print_banner, prompt_input, agent_print, agent_error, GREEN, DIM, RESET
from src.agent import KlatAgent
from src.extensions import (
    load_extensions, export_extension, import_extension,
    list_extensions, enable_extension, disable_extension, remove_extension
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


def _cmd_extension(args: str, agent: KlatAgent) -> None:
    """Handle /extension subcommands: list, export, import, enable, disable, remove"""
    parts = args.strip().split(None, 1)
    if not parts:
        print(f"\n  {GREEN}Klat Extension Management{RESET}")
        print("  ─────────────────────────────────────────────────────")
        print("  /extension list                 list installed extensions")
        print("  /extension export <folder>      export folder into a .ke file")
        print("  /extension import <file.ke>     import and hot-load a .ke file")
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


def _cmd_help() -> None:
    print(f"""
  {GREEN}Klat slash commands{RESET}
  ─────────────────────────────────────────────────────
  /provider              list all providers
  /provider <name>       switch active provider
  /model                 show current model
  /model <name>          set model for this session
  /extension             extension manager options
  /extension list        list installed extensions
  /extension export <d>  export a folder into a .ke file
  /extension import <f>  import and hot-load a .ke extension file
  /extension enable <n>  enable a disabled extension
  /extension disable <n> disable an active extension
  /extension remove <n>  uninstall/delete an extension
  /reset                 clear conversation history
  exit / quit / q        exit Klat
  ─────────────────────────────────────────────────────
  Providers: {', '.join(PROVIDER_NAMES)}
""")



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
    project, location = ensure_env()

    # Load existing extensions silently
    ext_count = load_extensions(silent=True)
    ext_text = int_to_words(ext_count)

    # Rebuild system prompt to include loaded extension tools/rules
    from src.agent import rebuild_system_prompt
    rebuild_system_prompt()

    agent = KlatAgent(project, location)

    p = get_provider(current_provider())
    info_lines = [
        "",
        f"{DIM}{ui.BANNER_SUBTITLE}{RESET}   {ui.colorize_gradient('TreeSoft')}",
        f"{DIM}extensions{RESET}  {ui.colorize_gradient(ext_text)}",
        f"{DIM}provider{RESET}    {ui.colorize_gradient(current_provider())}",
        f"{DIM}model{RESET}       {ui.colorize_gradient(current_model())}",
    ]
    print_banner(info_lines)

    while True:
        try:
            raw = prompt_input("you").strip()
            if not raw:
                continue

            # ── Exit ──────────────────────────────────────────────────────
            if raw.lower() in {"exit", "quit", "q"}:
                sys.exit(0)

            # ── Slash commands ────────────────────────────────────────────
            if raw.startswith("/"):
                parts     = raw[1:].split(None, 1)   # strip the leading "/"
                cmd       = parts[0].lower()
                remainder = parts[1] if len(parts) > 1 else ""

                if cmd == "provider":
                    _cmd_provider(remainder)
                elif cmd == "model":
                    _cmd_model(remainder)
                elif cmd == "extension":
                    _cmd_extension(remainder, agent)
                elif cmd in {"help", "?"}:
                    _cmd_help()
                elif cmd == "reset":
                    agent.reset()
                    agent_print("Conversation cleared.")
                else:
                    agent_error(f"Unknown command /{cmd}. Type /help for commands.")
                continue

            # ── Chat ──────────────────────────────────────────────────────
            agent.chat(raw)

        except KeyboardInterrupt:
            print()
            sys.exit(0)
        except Exception as e:
            agent_error(str(e))


if __name__ == "__main__":
    main()
