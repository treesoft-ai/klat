"""
Klat — a simple conversational chatbot by TreeSoft.
"""

import sys
from src.config import ensure_env, current_provider, current_model, set_provider, set_model
from src.providers import PROVIDERS, PROVIDER_NAMES, get_provider
from src.ui import print_banner, prompt_input, agent_print, agent_error, GREEN, DIM, RESET
from src.agent import KlatAgent


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


def _cmd_help() -> None:
    print(f"""
  {GREEN}Klat slash commands{RESET}
  ─────────────────────────────────────────────────────
  /provider              list all providers
  /provider <name>       switch active provider
  /model                 show current model
  /model <name>          set model for this session
  /reset                 clear conversation history
  exit / quit / q        exit Klat
  ─────────────────────────────────────────────────────
  Providers: {', '.join(PROVIDER_NAMES)}
""")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    project, location = ensure_env()
    agent = KlatAgent(project, location)

    p = get_provider(current_provider())
    info_lines = [
        "",
        f"{DIM}software engineer  ·  by TreeSoft{RESET}",
        "",
        f"{DIM}provider{RESET}  {GREEN}{current_provider()}{RESET}",
        f"{DIM}model{RESET}     {GREEN}{current_model()}{RESET}",
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
