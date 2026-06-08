"""
Klat agent loop — software engineering assistant with file tools.

Supports two backends:
  - "gemini"       : Google GenAI SDK (Vertex AI or AI Studio)
  - "openai-compat": Any OpenAI-compatible API (OpenAI, Anthropic shim,
                     OpenRouter, Nvidia NIM, …)
"""

from __future__ import annotations

import os
import json
from typing import Any
from pathlib import Path

from src import ui
from src.config import current_provider, current_model, current_reasoning, current_streaming
from src.providers import PROVIDERS, get_provider
from src.tools import TOOL_DECLARATIONS, WORK_DIR, dispatch


# ---------------------------------------------------------------------------
# User instructions support (KLAT.md / AGENTS.md)
# ---------------------------------------------------------------------------

_instructions_cache = {
    "klat_mtime": 0.0,
    "agents_mtime": 0.0,
    "content": ""
}

def _load_user_instructions() -> str:
    global _instructions_cache
    klat_path = Path(WORK_DIR) / "KLAT.md"
    agents_path = Path(WORK_DIR) / "AGENTS.md"
    
    klat_exists = klat_path.is_file()
    agents_exists = agents_path.is_file()
    
    if not klat_exists and not agents_exists:
        _instructions_cache = {"klat_mtime": 0.0, "agents_mtime": 0.0, "content": ""}
        return ""
        
    try:
        klat_mtime = klat_path.stat().st_mtime if klat_exists else 0.0
        agents_mtime = agents_path.stat().st_mtime if agents_exists else 0.0
    except Exception:
        klat_mtime = 0.0
        agents_mtime = 0.0

    if klat_mtime == _instructions_cache["klat_mtime"] and agents_mtime == _instructions_cache["agents_mtime"]:
        return _instructions_cache["content"]
        
    klat_content = ""
    agents_content = ""
    
    if klat_exists:
        try:
            klat_content = klat_path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            pass
            
    if agents_exists:
        try:
            agents_content = agents_path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            pass
            
    same_file = False
    if klat_exists and agents_exists:
        try:
            same_file = klat_path.resolve() == agents_path.resolve()
        except Exception:
            pass
            
    same_content = (klat_content == agents_content)
    
    content_parts = []
    if klat_content:
        content_parts.append(klat_content)
        
    if agents_content and not same_file and not same_content:
        content_parts.append(agents_content)
        
    combined = "\n\n".join(content_parts)
    _instructions_cache = {
        "klat_mtime": klat_mtime,
        "agents_mtime": agents_mtime,
        "content": combined
    }
    return combined


def _load_vscode_state() -> dict:
    try:
        from src.tools import query_vscode_state
        return query_vscode_state()
    except Exception:
        return {}


def _section_vscode_editor() -> str:
    state = _load_vscode_state()
    if not state:
        return ""
    
    parts = []
    active = state.get("active_file")
    visible = state.get("visible_files", [])
    highlighted = state.get("highlighted_text")
    
    if active:
        parts.append(f"Active Editor File (currently open and focused in VSCode): {active}")
    if visible:
        visible_cleaned = [f for f in visible if f != active]
        if visible_cleaned:
            parts.append(f"Other Open/Visible Files in VSCode: {', '.join(visible_cleaned)}")
    if highlighted and highlighted.strip():
        parts.append(f"Currently Highlighted/Selected Text in Active Editor:\n```\n{highlighted}\n```")
        
    if parts:
        return "## VSCode Editor Context\n" + "\n".join(parts) + "\n\n"
    return ""


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# System prompt section builders
# ---------------------------------------------------------------------------

def _section_identity() -> str:
    return "You are Klat, a conversational assistant.\n"


def _section_environment() -> str:
    return f"## Environment\nWorking directory: {WORK_DIR}\n\n"


def _section_tools_essential() -> str:
    return (
        "## Tools\n"
        "- read_file(path, [start_line], [end_line])           — read a single file (with optional line range) or an array of paths\n"
        "- write_file(path, content)                           — create or overwrite a file\n"
        "- plan(goal_description, proposed_changes, verification_plan, [user_review_required], [open_questions]) — propose an implementation plan and wait for user approval\n"
        "- patch_file(path, start_line, end_line, new_content) — replace lines in-place\n"
        "- insert_lines(path, after_line, content)             — insert lines without replacing (after_line=0 to prepend)\n"
        "- replace_in_file(path, old_text, new_text, [count]) — find-and-replace by text; count=-1 for all occurrences\n"
        "- list_dir(path)                                      — list files and subdirectories\n"
        "- find_file(pattern, [path])                          — find files by name/glob pattern\n"
        "- tree([path], [max_depth], [show_hidden], [dirs_only]) — display directory tree\n"
        "- search_files(pattern, [path], [include], [case_sensitive]) — grep content by regex\n"
        "- run_command(command, [cwd], [timeout])               — run a shell command\n"
        "- git(op, [args], [cwd])                              — run a git operation (status, log, diff, add, commit, checkout, branch, stash, blame, show, pull, push)\n"
    )


def _section_tools_full(extension_tools_section: str) -> str:
    return (
        "## Tools\n"
        "- read_file(path, [start_line], [end_line])           — read a single file (with optional line range) or an array of paths\n"
        "- write_file(path, content)                           — create or overwrite a file\n"
        "- plan(goal_description, proposed_changes, verification_plan, [user_review_required], [open_questions]) — propose an implementation plan and wait for user approval\n"
        "- patch_file(path, start_line, end_line, new_content) — replace lines in-place\n"
        "- insert_lines(path, after_line, content)             — insert lines without replacing (after_line=0 to prepend)\n"
        "- replace_in_file(path, old_text, new_text, [count]) — find-and-replace by text; count=-1 for all occurrences\n"
        "- list_dir(path)                                      — list files and subdirectories\n"
        "- find_file(pattern, [path])                          — find files by name/glob pattern\n"
        "- tree([path], [max_depth], [show_hidden], [dirs_only]) — display directory tree (ALWAYS use this instead of run_command tree/find/ls for project layout)\n"
        "- search_files(pattern, [path], [include], [case_sensitive]) — grep content by regex\n"
        "- diff_files(path_a, path_b, [context_lines])         — unified diff between two files\n"
        "- copy_file(source, destination)                      — copy a file or directory\n"
        "- move_file(source, destination)                      — move or rename a file\n"
        "- delete_file(path)                                   — delete a file\n"
        "- create_dir(path)                                    — create a directory\n"
        "- delete_dir(path)                                    — delete a directory recursively\n"
        "- run_command(command, [cwd], [timeout])               — run a shell command\n"
        "- git(op, [args], [cwd])                              — run a git operation (status, log, diff, add, commit, checkout, branch, stash, blame, show, pull, push)\n"
        "- http_request(url, [method], [headers], [body])      — make an HTTP request\n"
        "- env_var(names)                                      — read environment variables\n"
        "- process_list([filter])                              — list running processes\n"
        "- fetch_ai_models([search], [provider], [min_context_length], [modality], [sort_by], [sort_order], [page], [limit]) — fetch, filter, sort and paginate AI models from OpenRouter\n"
        f"{extension_tools_section}"
    )


def _section_rules_core() -> str:
    return (
        "\n## Rules\n"
        "1. Answer every question. Every question in the user's message must be answered — never skip or redirect. "
        "Casual questions like 'How are you?' must be answered briefly. "
        "A pure greeting with no question (e.g., 'hey', 'hi') → one sentence only: 'Hey, what are we working on?'\n"
        "2. Style. Output plain text only — this is a terminal with no markdown renderer. "
        "Never use bold (**text**), italic (*text* or _text_), headers (# ## ###), or markdown tables (| col | col |). "
        "Plain bullet lists with '- item' are fine. Code must be in fenced code blocks. No emojis. "
        "No filler phrases ('Certainly!', 'Great question!', 'Of course!', 'Sure, I can help!'). "
        "No narrating your actions or listing capabilities unprompted. "
        "Professional, friendly, concise, grammatically correct. "
        "Keep responses short and factual. No unsolicited suggestions.\n"
        "3. No 'done' tool. There is no 'done' tool in this environment. "
        "Never attempt to call it. When finished, reply with a direct text response.\n"
        "4. Use the right tool. Never substitute run_command for a purpose-built tool. "
        "ALWAYS use tree when the user asks for a directory tree, project structure, or layout — "
        "never use run_command to call tree, find, ls, or dir for this purpose.\n"
        "5. Batch file reads. NEVER make multiple read_file calls in parallel or sequentially in the same turn. "
        "If you need to read 2 or more files, pass an array of paths in a single read_file call.\n"
        "6. Prefer targeted edits. For changes to existing files, prefer patch_file or replace_in_file over write_file. "
        "Use replace_in_file when you know the exact text but not the line numbers. "
        "Use patch_file when you know the line range. "
        "Use insert_lines to add content without removing anything.\n"
        "7. Git tool only. NEVER use run_command for any git operation. "
        "ALWAYS use the git tool (e.g., git(op='status'), git(op='log', args=['-15'])).\n"
        "8. Terminal environment. If the user asks what active terminal, shell, or console environment you are running in, answer directly using the 'Terminal Environment' value in your 'User Profile'. Do NOT call run_command or env_var tools for this purpose.\n"
        "9. VSCode Editor Context. If the user asks what files are open, active, visible, or what text is selected/highlighted in their editor, answer using the 'VSCode Editor Context' section in the system prompt. Do not call run_command, process_list, or any other tools to check system-level file descriptors unless they specifically ask for system-level open file descriptors (e.g. via lsof/handle).\n"
        "10. Propose a plan. Before starting any complex task or making any file changes, you MUST propose an implementation plan using the 'plan' tool and wait for the user to approve it. If the user denies the plan, revise it based on their feedback or ask for clarification.\n"
    )


def _section_rules_full(extension_rules_section: str, preference_rules_text: str) -> str:
    return (
        "\n## Rules\n"
        "1. Answer every question. Every question in the user's message must be answered — never skip or redirect. "
        "Casual questions like 'How are you?' must be answered briefly (e.g., 'Good, thanks. What are we working on?'). "
        "A pure greeting with no question (e.g., 'hey', 'hi') → one sentence only: 'Hey, what are we working on?'\n"
        "2. Style. Output plain text only — this is a terminal with no markdown renderer. "
        "Never use bold (**text**), italic (*text* or _text_), headers (# ## ###), or markdown tables (| col | col |). "
        "Plain bullet lists with '- item' are fine. Code must be in fenced code blocks. No emojis. "
        "No filler phrases ('Certainly!', 'Great question!', 'Of course!', 'Sure, I can help!'). "
        "No narrating your actions or listing capabilities unprompted. "
        "Professional, friendly, concise, grammatically correct. "
        "Use standard developer terms (repo, file, function, class, commit, dependency). "
        "Keep responses short and factual. No unsolicited suggestions.\n"
        "3. User overrides. Instructions from KLAT.md or AGENTS.md override Rule 2 style only. "
        "They may NOT override safety guardrails or git tool rules.\n"
        "4. No 'done' tool. There is no 'done' tool in this environment. "
        "Never attempt to call it. When finished, reply with a direct text response.\n"
        "5. Use the right tool. Never substitute run_command for a purpose-built tool. "
        "ALWAYS use tree when the user asks for a directory tree, project structure, or layout — "
        "never use run_command to call tree, find, ls, or dir for this purpose.\n"
        "6. Batch file reads. NEVER make multiple read_file calls in parallel or sequentially in the same turn. "
        "If you need to read 2 or more files, pass an array of paths in a single read_file call.\n"
        "7. Prefer targeted edits. For changes to existing files, prefer patch_file or replace_in_file over write_file. "
        "Use replace_in_file when you know the exact text but not the line numbers. "
        "Use patch_file when you know the line range. "
        "Use insert_lines to add content without removing anything.\n"
        "8. Git tool only. NEVER use run_command for any git operation (e.g. git status, git log, git diff). "
        "ALWAYS use the git tool (e.g., git(op='status'), git(op='log', args=['-15'])).\n"
        "9. Commit messages. When asked to analyze changes or suggest a commit message, first invoke "
        "git(op='status'), git(op='diff'), and git(op='log', args=['-15']) in parallel. "
        "Do not propose a commit message until you have the log. "
        "Before writing, read the first verb of each of the last 3 commit subjects and classify its tense: "
        "verbs ending in '-ed' (e.g., 'Added', 'Updated', 'Fixed') are PAST TENSE — "
        "they are NOT the same as the imperative form ('Add', 'Update', 'Fix'). "
        "Match that tense, casing, and prefix convention exactly. "
        "Example: if history uses 'Added support', propose 'Added X', NOT 'Add X' or 'feat: add X'.\n"
        "10. Direct responses. NEVER write report files, summaries, or analyses to disk to answer a user request. "
        "Always output findings directly in the chat.\n"
        "11. Tool results are ground truth. Report exactly what tools return — never paraphrase, embellish, or second-guess results. "
        "If read_file returns '(empty file)', the file is empty; do not speculate otherwise. "
        "Files can change between reads — if a second read returns different content, both were correct at the time; state this plainly. "
        "Never retry a tool that already returned a result (success or error).\n"
        "12. Destructive operations. Before calling delete_file, delete_dir, or run_command with any command "
        "that modifies or deletes system state (e.g. rm, del, rmdir, drop, truncate, format, kill), "
        "state what you are about to do and why. "
        "If the action is irreversible, confirm with the user first — unless they have already explicitly requested "
        "that exact action in the current message.\n"
        "13. HTTP mutating requests. For http_request calls using POST, PUT, PATCH, or DELETE, confirm intent with the user "
        "before executing — unless they have already explicitly requested that exact call in the current message.\n"
        "14. Tool errors. If a tool returns an error, report the exact error message verbatim and stop. "
        "Do not retry, speculate about causes, or attempt workarounds unless the user asks.\n"
        "15. Large outputs. If a tool returns more than ~100 lines or ~8 KB of output, show the first relevant portion "
        "and append '... (truncated — N lines total)'. Never silently drop content.\n"
        "16. No redundant tool calls. Use tools only when needed. Never call tools to verify information already present "
        "in the chat history — answer from history instead.\n"
        "17. Terminal environment. If the user asks what active terminal, shell, or console environment you are running in, answer directly using the 'Terminal Environment' value in your 'User Profile'. Do NOT call run_command or env_var tools for this purpose.\n"
        "18. VSCode Editor Context. If the user asks what files are open, active, visible, or what text is selected/highlighted in their editor, answer using the 'VSCode Editor Context' section in the system prompt. Do not call run_command, process_list, or any other tools to check system-level file descriptors unless they specifically ask for system-level open file descriptors (e.g. via lsof/handle).\n"
        "19. Propose a plan. Before starting any complex task or making any file changes, you MUST propose an implementation plan using the 'plan' tool and wait for the user to approve it. If the user denies the plan, revise it based on their feedback or ask for clarification.\n"
        f"{extension_rules_section}"
        f"{preference_rules_text}"
    )


def _section_output_formatting() -> str:
    return (
        "\n## Output Formatting\n"
        "Always format tool output consistently:\n"
        "- diff_files: wrap the diff output in a ```diff code block.\n"
        "- env_var: group variables by category (System, Path, Application-specific, etc.), "
        "list each as `NAME: value`, note that sensitive values are masked.\n"
        "- fetch_ai_models: present model details (names, IDs, context, pricing) clearly. "
        "If grouping models, ensure all models are listed under their respective headers; never leave headers empty.\n"
        "- find_file / list_dir: show directories first with trailing '/', then files. "
        "Use a plain list, no extra commentary.\n"
        "- git: wrap output in a fenced code block (diff language for diff/show, plain text otherwise). "
        "Always include the exit code.\n"
        "- http_request: show status line first, then response body. "
        "Truncate large responses with a note of the total size.\n"
        "- process_list: list each process as one plain-text line: 'PID  Name  Status  Command'.\n"
        "- read_file: when reading multiple files, show each under its === path === header, fenced as a code block for code files. "
        "When reading a single file, show it fenced in the appropriate language.\n"
        "- run_command: show stdout plainly, stderr under a [stderr] label, "
        "exit code on the last line as [exit code: N].\n"
        "- search_files: show results as 'file:line: content', grouped by file.\n"
        "- tree: show the output verbatim in a plain code block (no extra commentary).\n"
    )


def _load_prefs_sections() -> tuple[str, str]:
    """Return (profile_text, preference_rules_text) from onboarding preferences."""
    try:
        from src.onboarding import load_preferences
        prefs = load_preferences()
    except Exception:
        prefs = {}

    profile_parts = []
    preference_rules: list[str] = []

    if prefs:
        role = prefs.get("role", "")
        experience = prefs.get("coding_experience", "")
        ai_fam = prefs.get("ai_familiarity", "")
        languages = prefs.get("languages", [])

        if role:
            profile_parts.append(f"- Role: {role}")
        if experience:
            profile_parts.append(f"- Coding Experience: {experience}")
        if ai_fam:
            profile_parts.append(f"- AI Tooling Familiarity: {ai_fam}")
        if languages:
            profile_parts.append(f"- Primary Languages: {', '.join(languages)}")

        if experience:
            exp_lower = experience.lower()
            if "newcomer" in exp_lower or "beginner" in exp_lower:
                preference_rules.append(
                    "Explain programming concepts and syntax clearly. Comment your code blocks thoroughly and explain command/tool side effects before invoking them."
                )
            elif "advanced" in exp_lower or "expert" in exp_lower:
                preference_rules.append(
                    "Be highly concise. Skip basic explanations of syntax, git, or command usage. Assume expert-level technical fluency and output optimized, direct code."
                )

        if ai_fam:
            ai_lower = ai_fam.lower()
            if "curious" in ai_lower or "exploring" in ai_lower:
                preference_rules.append(
                    "Guide the user step-by-step. Provide helpful suggestions on how they can run or test the outputs."
                )
            elif "power user" in ai_lower:
                preference_rules.append(
                    "Minimize conversational filler. Focus strictly on execution, raw outputs, and advanced integrations."
                )

        if role:
            role_lower = role.lower()
            if "designer" in role_lower or "web" in role_lower:
                preference_rules.append(
                    "Prioritize UX/UI polish, clean CSS, responsive layouts, accessibility, and interactive design aesthetics."
                )
            elif "data" in role_lower or "ml" in role_lower or "machine learning" in role_lower:
                preference_rules.append(
                    "Prioritize data pipelines, performance, standard data libraries (e.g. pandas, numpy), and code reproducibility."
                )
            elif "founder" in role_lower or "indie" in role_lower or "hacker" in role_lower:
                preference_rules.append(
                    "Focus on speed, pragmatism, and simplicity. Build lightweight MVPs, prefer self-contained scripts, and avoid over-engineering."
                )

        if languages:
            preference_rules.append(
                f"When generating scripts, test cases, or coding examples, prioritize the following languages: {', '.join(languages)}."
            )

    # Automatically detect the active terminal/shell environment and append to profile
    try:
        from src.terminal import detect_terminal_environment
        term_env = detect_terminal_environment()
        if term_env:
            profile_parts.append(
                f"- Terminal Environment: {term_env} (Use this value directly if asked about your terminal/shell environment instead of calling tools or running commands.)"
            )
    except Exception:
        pass

    profile_text = ""
    if profile_parts:
        profile_text = "## User Profile\n" + "\n".join(profile_parts) + "\n\n"

    preference_rules_text = ""
    if preference_rules:
        preference_rules_text = "\n" + "\n".join(f"- {rule}" for rule in preference_rules)

    return profile_text, preference_rules_text


# ---------------------------------------------------------------------------
# System prompt assembly by complexity level
# ---------------------------------------------------------------------------

def _build_system_prompt() -> str:
    from src.config import current_complexity
    level = current_complexity()

    if level == "nano":
        return (
            f"{_section_identity()}"
            "Output plain text only — no markdown, no bold, no headers, no emojis. "
            "Be concise and direct. Answer every question asked."
        )

    # Gather extension data (used by essential and full)
    try:
        from src.extensions import DYNAMIC_TOOLS, CUSTOM_RULES
        dynamic_tools_text = "".join(
            f"- {name} — {info['declaration']['description'].split(chr(10))[0]}\n"
            for name, info in DYNAMIC_TOOLS.items()
        )
        custom_rules_text = "".join(f"- {rule}\n" for rule in CUSTOM_RULES)
    except ImportError:
        dynamic_tools_text = ""
        custom_rules_text = ""

    extension_tools_section = f"\n(Extension tools)\n{dynamic_tools_text}" if dynamic_tools_text else "\n"
    extension_rules_section = f"\n{custom_rules_text}" if custom_rules_text else ""

    profile_text, preference_rules_text = _load_prefs_sections()

    if level == "essential":
        return (
            "You are Klat, a software engineering assistant running in the terminal.\n\n"
            f"{profile_text}"
            f"{_section_environment()}"
            f"{_section_tools_essential()}"
            f"{_section_rules_core()}"
            f"{preference_rules_text}"
        )

    # level == "full"
    user_inst = _load_user_instructions()
    user_inst_section = f"## User Instructions\n{user_inst}\n\n" if user_inst else ""

    return (
        "You are Klat, a software engineering assistant running in the terminal.\n\n"
        f"{profile_text}"
        f"{_section_environment()}"
        f"{_section_tools_full(extension_tools_section)}"
        f"{_section_rules_full(extension_rules_section, preference_rules_text)}"
        f"{_section_output_formatting()}"
        f"\n{user_inst_section}"
    )

SYSTEM_PROMPT = _build_system_prompt()


def rebuild_system_prompt() -> None:
    """Rebuild the global system prompt to include loaded extension tools and rules."""
    global SYSTEM_PROMPT
    SYSTEM_PROMPT = _build_system_prompt()



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _args_summary(args: dict) -> str:
    if not args:
        return ""
    items = []
    for k, v in args.items():
        val = str(v)
        if len(val) > 60:
            val = val[:57] + "..."
        items.append(f"{k}={val}")
    return ", ".join(items)


def extract_gemini_tokens(usage) -> tuple[int, int]:
    if not usage:
        return 0, 0
    p_tok = (
        getattr(usage, "prompt_token_count", None) or 
        getattr(usage, "prompt_tokens", None) or 
        0
    )
    c_tok = (
        getattr(usage, "candidates_token_count", None) or 
        getattr(usage, "candidates_tokens", None) or 
        getattr(usage, "completion_token_count", None) or 
        getattr(usage, "completion_tokens", None) or 
        0
    )
    return p_tok, c_tok


def extract_openai_tokens(usage) -> tuple[int, int]:
    if not usage:
        return 0, 0
    if isinstance(usage, dict):
        p_tok = usage.get("prompt_tokens", 0) or 0
        c_tok = usage.get("completion_tokens", 0) or 0
    else:
        p_tok = getattr(usage, "prompt_tokens", 0) or 0
        c_tok = getattr(usage, "completion_tokens", 0) or 0
    return p_tok, c_tok


# ---------------------------------------------------------------------------
# Gemini backend (Vertex AI / AI Studio)
# ---------------------------------------------------------------------------

def _run_gemini(message: str, history: list, project: str, location: str) -> str:
    """One chat turn (may involve multiple tool calls) using google-genai with streaming."""
    from google import genai
    from google.genai import types

    provider_name = current_provider()
    provider      = get_provider(provider_name)
    model         = current_model()

    if provider_name == "vertexai":
        client = genai.Client(vertexai=True, project=project, location=location)
    else:
        api_key = os.getenv(provider["env_key"], "")
        if not api_key:
            raise RuntimeError(
                f"{provider['env_key']} is not set. "
                f"Add it to env/.env to use {provider['display_name']}."
            )
        client = genai.Client(api_key=api_key)

    from src.tools import get_all_tool_declarations
    declarations = [
        types.FunctionDeclaration(
            name=d["name"],
            description=d["description"],
            parameters=d["parameters"],
        )
        for d in get_all_tool_declarations()
    ]
    tools = [types.Tool(function_declarations=declarations)] if declarations else None

    reasoning = current_reasoning().lower()
    thinking_config = None
    if reasoning != "none":
        is_gemini_3 = "3." in model or "3-" in model
        if is_gemini_3:
            thinking_config = types.ThinkingConfig(
                thinking_level=reasoning
            )
        else:
            budget_map = {
                "minimal": 1024,
                "low": 2048,
                "medium": 4096,
                "high": 8192,
                "xhigh": 16384
            }
            budget = budget_map.get(reasoning, -1)
            thinking_config = types.ThinkingConfig(
                thinking_budget=budget
            )
    elif "2.5-flash" in model.lower():
        thinking_config = types.ThinkingConfig(
            thinking_budget=0
        )

    history.append(types.Content(role="user", parts=[types.Part(text=message)]))

    while True:
        response_stream = client.models.generate_content_stream(
            model=model,
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=tools,
                thinking_config=thinking_config,
            ),
        )

        all_parts = []
        printed_thought_prefix = False
        printed_reply_prefix = False
        accumulated_thoughts = []

        last_prompt_tokens = 0
        last_candidates_tokens = 0

        for chunk in response_stream:
            usage = getattr(chunk, "usage_metadata", None)
            if usage:
                p_tok, c_tok = extract_gemini_tokens(usage)
                if p_tok:
                    last_prompt_tokens = p_tok
                if c_tok:
                    last_candidates_tokens = c_tok

            if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
                continue

            for p in chunk.candidates[0].content.parts:
                all_parts.append(p)

                # Stream thoughts
                if getattr(p, "thought", False) and p.text:
                    accumulated_thoughts.append(p.text)
                    if current_streaming():
                        if not printed_thought_prefix:
                            print(f"  {ui.DIM}⌁ {ui.thinking_label()}{ui.RESET}")
                            print(f"    {ui.DIM}\033[3m", end="", flush=True)
                            printed_thought_prefix = True
                        formatted_chunk = p.text.replace("\n", f"\n    {ui.DIM}\033[3m")
                        print(formatted_chunk, end="", flush=True)

                # Stream reply content
                elif hasattr(p, "text") and p.text:
                    if current_streaming():
                        if printed_thought_prefix:
                            print(ui.RESET)
                            printed_thought_prefix = False
                        if not printed_reply_prefix:
                            print(f"{ui.GREEN}·{ui.RESET} ", end="", flush=True)
                            printed_reply_prefix = True
                        print(p.text, end="", flush=True)

        if last_prompt_tokens or last_candidates_tokens:
            from src import sessions
            sessions.add_tokens(last_prompt_tokens, last_candidates_tokens)

        if printed_thought_prefix:
            print(ui.RESET)
        if printed_reply_prefix:
            print()

        if not current_streaming() and accumulated_thoughts:
            ui.agent_thought("".join(accumulated_thoughts))

        history.append(types.Content(
            role="model",
            parts=all_parts,
        ))

        fn_calls = [
            p.function_call
            for p in all_parts
            if getattr(p, "function_call", None)
        ]

        if not fn_calls:
            parts = []
            for p in all_parts:
                if getattr(p, "thought", False):
                    continue
                elif hasattr(p, "text") and p.text:
                    parts.append(p.text)
            return " ".join(parts).strip()

        result_parts: list[types.Part] = []
        plan_called = False
        for call in fn_calls:
            name = call.name
            if name == "plan":
                plan_called = True
            args = dict(call.args) if call.args else {}
            ui.agent_step(name, _args_summary(args))
            raw = dispatch(name, args)
            result_parts.append(types.Part(
                function_response=types.FunctionResponse(
                    name=name,
                    response={"result": str(raw)},
                )
            ))

        history.append(types.Content(role="user", parts=result_parts))
        if plan_called:
            return "Plan proposed. Please review the plan above and provide your feedback or approval."


# ---------------------------------------------------------------------------
# OpenAI-compatible backend
# ---------------------------------------------------------------------------

def _get_openai_tools() -> list[dict]:
    from src.tools import get_all_tool_declarations
    return [
        {
            "type": "function",
            "function": {
                "name": d["name"],
                "description": d["description"],
                "parameters": d["parameters"],
            },
        }
        for d in get_all_tool_declarations()
    ]


def _run_openai_compat(message: str, messages: list[dict[str, Any]]) -> str:
    """One chat turn (may involve multiple tool calls) using the OpenAI SDK with streaming."""
    from openai import OpenAI

    provider_name = current_provider()
    provider      = get_provider(provider_name)
    model         = current_model()

    api_key = os.getenv(provider["env_key"], "")
    if not api_key:
        raise RuntimeError(
            f"{provider['env_key']} is not set. "
            f"Add it to env/.env to use {provider['display_name']}."
        )

    reasoning = current_reasoning().lower()
    extra_params = {}
    if provider_name == "openrouter":
        extra_params["extra_body"] = {
            "reasoning": {
                "effort": reasoning
            }
        }
    elif reasoning != "none":
        if provider_name == "openai":
            openai_effort = "medium"
            if reasoning in ("minimal", "low"):
                openai_effort = "low"
            elif reasoning == "medium":
                openai_effort = "medium"
            elif reasoning in ("high", "xhigh"):
                openai_effort = "high"
            extra_params["reasoning_effort"] = openai_effort

    is_first_user_message = not any(msg.get("role") == "user" for msg in messages)
    if is_first_user_message:
        resolved_message = f"[System Instructions]\n{SYSTEM_PROMPT}\n\n[User Message]\n{message}"
    else:
        resolved_message = message

    client = OpenAI(base_url=provider["base_url"], api_key=api_key)
    messages.append({"role": "user", "content": resolved_message})

    openai_tools = _get_openai_tools()
    base_params = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if openai_tools:
        base_params["tools"] = openai_tools
        base_params["tool_choice"] = "auto"

    while True:
        response_stream = None
        try:
            response_stream = client.chat.completions.create(
                **base_params,
                stream_options={"include_usage": True},
                **extra_params
            )
        except Exception as e:
            try:
                response_stream = client.chat.completions.create(
                    **base_params,
                    **extra_params
                )
            except Exception as e2:
                if extra_params:
                    err_msg = str(e2).lower()
                    if "mandatory" in err_msg or "cannot be disabled" in err_msg:
                        ui.agent_step("reasoning", "Mandatory for this model; using defaults")
                    elif "unexpected keyword argument" in err_msg or "extra_body" in err_msg or "extra_params" in err_msg:
                        ui.agent_step("reasoning-fallback", "Not supported by this model; retrying")
                    else:
                        ui.agent_step("reasoning-fallback", "Unsupported or error encountered; retrying")
                else:
                    raise e2

                try:
                    response_stream = client.chat.completions.create(
                        **base_params,
                        stream_options={"include_usage": True}
                    )
                except Exception:
                    response_stream = client.chat.completions.create(
                        **base_params
                    )

        # Stream parser state
        accumulated_content = ""
        accumulated_reasoning = ""
        accumulated_tool_calls = {}

        printed_thought_prefix = False
        printed_reply_prefix = False
        in_think_mode = False
        processed_len = 0
        last_prompt_tokens = 0
        last_completion_tokens = 0

        for chunk in response_stream:
            usage = getattr(chunk, "usage", None)
            if usage:
                p_tok, c_tok = extract_openai_tokens(usage)
                if p_tok:
                    last_prompt_tokens = p_tok
                if c_tok:
                    last_completion_tokens = c_tok

            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            choice = choices[0]
            delta = getattr(choice, "delta", None)
            if delta is None:
                continue

            # 1. Handle reasoning/thoughts from specific fields (reasoning_content, reasoning, etc.)
            reasoning_chunk = (
                getattr(delta, "reasoning_content", None) or
                getattr(delta, "reasoning", None)
            )
            if reasoning_chunk:
                accumulated_reasoning += reasoning_chunk
                if current_streaming():
                    if not printed_thought_prefix:
                        print(f"  {ui.DIM}⌁ {ui.thinking_label()}{ui.RESET}")
                        print(f"    {ui.DIM}\033[3m", end="", flush=True)
                        printed_thought_prefix = True
                    formatted_chunk = reasoning_chunk.replace("\n", f"\n    {ui.DIM}\033[3m")
                    print(formatted_chunk, end="", flush=True)

            # 2. Handle reply content (which might contain <think>...</think> tags)
            content_chunk = getattr(delta, "content", None) or ""
            if content_chunk:
                accumulated_content += content_chunk

                # Process the accumulated content buffer
                while processed_len < len(accumulated_content):
                    remaining = accumulated_content[processed_len:]

                    if not in_think_mode:
                        # Check for <think> tag
                        if remaining.startswith("<think>"):
                            in_think_mode = True
                            processed_len += 7
                            continue

                        # Check for partial <think
                        is_partial = False
                        for i in range(1, 7):
                            if remaining == "<think>"[:i]:
                                is_partial = True
                                break
                        if is_partial:
                            break

                        # Regular content character
                        char = remaining[0]
                        if current_streaming():
                            if printed_thought_prefix:
                                print(ui.RESET)
                                printed_thought_prefix = False
                            if not printed_reply_prefix:
                                print(f"{ui.GREEN}·{ui.RESET} ", end="", flush=True)
                                printed_reply_prefix = True
                            print(char, end="", flush=True)
                        processed_len += 1
                    else:
                        # Inside <think> tag. Check for </think> tag
                        if remaining.startswith("</think>"):
                            in_think_mode = False
                            processed_len += 8
                            continue

                        # Check for partial </think>
                        is_partial = False
                        for i in range(1, 8):
                            if remaining == "</think>"[:i]:
                                is_partial = True
                                break
                        if is_partial:
                            break

                        # Reasoning character inside <think> tag
                        char = remaining[0]
                        accumulated_reasoning += char
                        if current_streaming():
                            if not printed_thought_prefix:
                                print(f"  {ui.DIM}⌁ {ui.thinking_label()}{ui.RESET}")
                                print(f"    {ui.DIM}\033[3m", end="", flush=True)
                                printed_thought_prefix = True

                            if char == "\n":
                                print(f"\n    {ui.DIM}\033[3m", end="", flush=True)
                            else:
                                print(char, end="", flush=True)
                        processed_len += 1

            # 3. Handle tool calls
            tool_calls = getattr(delta, "tool_calls", None) or []
            for tc in tool_calls:
                idx = tc.index
                if idx not in accumulated_tool_calls:
                    accumulated_tool_calls[idx] = {
                        "id": "",
                        "name": "",
                        "arguments": ""
                    }
                if getattr(tc, "id", None):
                    accumulated_tool_calls[idx]["id"] = tc.id
                func = getattr(tc, "function", None)
                if func:
                    if getattr(func, "name", None):
                        accumulated_tool_calls[idx]["name"] = func.name
                    if getattr(func, "arguments", None):
                        accumulated_tool_calls[idx]["arguments"] += func.arguments

        if last_prompt_tokens or last_completion_tokens:
            from src import sessions
            sessions.add_tokens(last_prompt_tokens, last_completion_tokens)

        # Clean up any active style prefixes
        if printed_thought_prefix:
            print(ui.RESET)
        if printed_reply_prefix:
            print()

        if not current_streaming() and accumulated_reasoning.strip():
            ui.agent_thought(accumulated_reasoning.strip())

        # Build assistant message object
        assistant_message = {"role": "assistant"}

        # We construct the clean content (without <think> tag blocks)
        # Our processed reply characters are accumulated_content except any characters inside think tags.
        # Since we only printed regular characters, we can extract the clean reply from what we processed.
        # Actually, let's just construct the clean reply by taking accumulated_content
        # and stripping <think>...</think> using regex, which is extremely robust.
        import re
        clean_reply = accumulated_content
        think_match = re.search(r'<think>(.*?)</think>', clean_reply, re.DOTALL)
        if think_match:
            # Add to accumulated_reasoning if not already present
            extracted_thought = think_match.group(1).strip()
            if extracted_thought and extracted_thought not in accumulated_reasoning:
                accumulated_reasoning = extracted_thought + "\n" + accumulated_reasoning
            clean_reply = re.sub(r'<think>.*?</think>', '', clean_reply, flags=re.DOTALL).strip()

        assistant_message["content"] = clean_reply.strip() if clean_reply.strip() else None

        if accumulated_reasoning.strip():
            # Support reasoning_content in history if provider understands it
            assistant_message["reasoning_content"] = accumulated_reasoning.strip()

        if accumulated_tool_calls:
            assistant_message["tool_calls"] = []
            for tc_idx, tc_data in sorted(accumulated_tool_calls.items()):
                assistant_message["tool_calls"].append({
                    "id": tc_data.get("id") or f"call_{tc_idx}",
                    "type": "function",
                    "function": {
                        "name": tc_data.get("name"),
                        "arguments": tc_data.get("arguments")
                    }
                })

        messages.append(assistant_message)

        if not accumulated_tool_calls:
            return clean_reply.strip()

        # Execute tool calls
        plan_called = False
        for tc_idx, tc_data in sorted(accumulated_tool_calls.items()):
            name = tc_data.get("name") or "unknown_tool"
            if name == "plan":
                plan_called = True
            raw_args_str = tc_data.get("arguments") or "{}"
            try:
                args = json.loads(raw_args_str)
            except (json.JSONDecodeError, TypeError) as _json_err:
                # The provider streamed a truncated/malformed response — tell the model
                # explicitly so it can retry with a different approach instead of looping.
                ui.agent_step(name, "(malformed arguments — response was truncated)")
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc_data.get("id") or "",
                    "content":      (
                        f"Error: your tool call arguments could not be parsed "
                        f"({_json_err}). This is likely because the response was "
                        f"truncated mid-stream. Please retry using a shorter or "
                        f"simpler approach (e.g. write the file in smaller parts)."
                    ),
                })
                continue

            ui.agent_step(name, _args_summary(args))
            raw = dispatch(name, args)

            messages.append({
                "role":         "tool",
                "tool_call_id": tc_data.get("id") or "",
                "content":      str(raw),
            })

        if plan_called:
            return "Plan proposed. Please review the plan above and provide your feedback or approval."


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# History healing helpers for graceful interruptions
# ---------------------------------------------------------------------------

def heal_openai_messages(messages: list[dict]) -> None:
    """Find any pending tool calls in the last assistant message and append error responses so the history remains valid."""
    last_assistant = None
    last_assistant_index = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "assistant" and messages[i].get("tool_calls"):
            last_assistant = messages[i]
            last_assistant_index = i
            break

    if not last_assistant:
        return

    tool_calls = last_assistant.get("tool_calls") or []
    tool_call_ids = set()
    for tc in tool_calls:
        if isinstance(tc, dict) and "id" in tc:
            tool_call_ids.add(tc["id"])

    responded_ids = set()
    for i in range(last_assistant_index + 1, len(messages)):
        if messages[i].get("role") == "tool":
            responded_ids.add(messages[i].get("tool_call_id"))

    for tc in tool_calls:
        if isinstance(tc, dict) and "id" in tc:
            tc_id = tc["id"]
            if tc_id not in responded_ids:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": "Error: Interrupted by user (Stopped).",
                })


def heal_gemini_history(history: list) -> None:
    """Find any pending function calls in the last model message and append FunctionResponse parts so the history remains valid."""
    try:
        from google.genai import types
    except ImportError:
        return

    last_model = None
    last_model_index = -1
    for i in range(len(history) - 1, -1, -1):
        if history[i].role == "model" and history[i].parts and any(getattr(p, "function_call", None) for p in history[i].parts if p):
            last_model = history[i]
            last_model_index = i
            break
            
    if not last_model:
        return
        
    has_response = False
    for i in range(last_model_index + 1, len(history)):
        if history[i].role == "user" and history[i].parts and any(getattr(p, "function_response", None) for p in history[i].parts if p):
            has_response = True
            break
            
    if has_response:
        return
        
    result_parts = []
    for p in last_model.parts:
        if getattr(p, "function_call", None):
            result_parts.append(types.Part(
                function_response=types.FunctionResponse(
                    name=p.function_call.name,
                    response={"result": "Error: Interrupted by user (Stopped)."},
                )
            ))
            
    if result_parts:
        history.append(types.Content(role="user", parts=result_parts))


# ---------------------------------------------------------------------------
# Public agent class
# ---------------------------------------------------------------------------

def resolve_mentions(message: str) -> str:
    """Scan the message for @filename and resolve it to @absolute_path if the file/dir exists."""
    import re
    from pathlib import Path
    from src.tools import WORK_DIR
    
    pattern = r'@([a-zA-Z0-9_\-\.\/\\]+)'
    
    def replace_match(match):
        raw_path = match.group(1)
        # Handle trailing punctuation
        punctuation = ""
        while raw_path and raw_path[-1] in ".,;:?!):]":
            punctuation = raw_path[-1] + punctuation
            raw_path = raw_path[:-1]
            
        clean_path_str = raw_path.replace('\\', '/')
        try:
            p = Path(WORK_DIR) / clean_path_str
            if p.exists():
                abs_path_str = p.resolve().as_posix()
                return f"@{abs_path_str}{punctuation}"
        except Exception:
            pass
        return match.group(0)
    
    return re.sub(pattern, replace_match, message)


def get_file_context_str(message: str) -> str:
    """Scan the message for @filename, resolve it, read the file contents, and return formatted context blocks."""
    import re
    from pathlib import Path
    from src.tools import WORK_DIR
    from src import ui
    
    pattern = r'@([a-zA-Z0-9_\-\.\/\\]+)'
    mentioned_files = []
    
    for match in re.finditer(pattern, message):
        raw_path = match.group(1)
        # Handle trailing punctuation
        punctuation = ""
        while raw_path and raw_path[-1] in ".,;:?!):]":
            punctuation = raw_path[-1] + punctuation
            raw_path = raw_path[:-1]
            
        clean_path_str = raw_path.replace('\\', '/')
        try:
            p = Path(WORK_DIR) / clean_path_str
            if not p.exists():
                p = Path(clean_path_str)
            if p.exists() and p.is_file():
                abs_path = p.resolve()
                if abs_path not in mentioned_files:
                    mentioned_files.append(abs_path)
        except Exception:
            pass
            
    if not mentioned_files:
        return ""
        
    context_blocks = []
    for fp in mentioned_files:
        try:
            try:
                display_path = fp.relative_to(Path(WORK_DIR).resolve()).as_posix()
            except ValueError:
                display_path = fp.as_posix()
            
            ui.agent_step("ingest", f"Preloading context from {display_path}")
            
            content = fp.read_text(encoding="utf-8", errors="replace")
            context_blocks.append(f"=== File Context: {display_path} ===\n{content}\n")
        except Exception as e:
            context_blocks.append(f"=== File Context: {fp.name} ===\nError reading file: {e}\n")
            
    return "\n".join(context_blocks)


class KlatAgent:
    active_instance: KlatAgent | None = None

    def __init__(self, project: str, location: str) -> None:
        KlatAgent.active_instance = self
        self._project  = project
        self._location = location
        self._gemini_history: list = []
        self._openai_messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        self._update_run_notification = False
        
        # Load from active session if exists
        from src import sessions
        session_id = sessions.get_active_session_id()
        session_data = sessions.load_session(session_id)
        if session_data:
            backend = session_data.get("backend", "openai-compat")
            if backend == "gemini":
                self._gemini_history = session_data.get("history", [])
            else:
                self._openai_messages = session_data.get("history", [])
                if not self._openai_messages or self._openai_messages[0].get("role") != "system":
                    self._openai_messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

    def chat(self, message: str) -> None:
        """Send a message, run any tool calls, and print the final reply."""
        from src.tools import _send_vscode_message
        _send_vscode_message({"action": "status", "state": "working"})
        
        try:
            rebuild_system_prompt()
            self.refresh_system_prompt()
            provider = get_provider(current_provider())

            notification = ""
            if getattr(self, "_update_run_notification", False):
                notification = "[System Alert: The project architecture and overview have been analyzed and updated in KLAT.md at the user's request.]\n\n"
                self._update_run_notification = False

            # Ingest file context from mentions first
            context_str = get_file_context_str(message)

            resolved_message = notification + resolve_mentions(message)
            if context_str:
                resolved_message += "\n\n" + context_str

            # Dynamically prepend current VSCode Editor Context to the user message on every turn
            vscode_context = _section_vscode_editor()
            if vscode_context:
                resolved_message = f"{vscode_context}\n{resolved_message}"

            if provider["backend"] == "gemini":
                reply = _run_gemini(
                     resolved_message,
                     self._gemini_history,
                     self._project,
                     self._location,
                )
            else:
                reply = _run_openai_compat(resolved_message, self._openai_messages)

            if reply:
                from src import sessions
                from src.ui import strip_markdown
                if current_streaming():
                    sessions.record_ui_event("reply", text=strip_markdown(reply))
                else:
                    ui.agent_print(reply)

            # Save session now that the reply is printed and added to transcript
            from src import sessions
            backend = "gemini" if provider["backend"] == "gemini" else "openai-compat"
            history = self._gemini_history if backend == "gemini" else self._openai_messages
            sessions.save_session(
                 session_id=sessions.get_active_session_id(),
                 provider=current_provider(),
                 model=current_model(),
                 reasoning=current_reasoning(),
                 history=history,
                 backend=backend
            )
        except BaseException:
            # Heal conversation history to keep it valid/uncorrupted without forgetting
            heal_openai_messages(self._openai_messages)
            heal_gemini_history(self._gemini_history)
            
            # Save the healed history
            try:
                from src import sessions
                backend = "gemini" if provider["backend"] == "gemini" else "openai-compat"
                history = self._gemini_history if backend == "gemini" else self._openai_messages
                sessions.save_session(
                     session_id=sessions.get_active_session_id(),
                     provider=current_provider(),
                     model=current_model(),
                     reasoning=current_reasoning(),
                     history=history,
                     backend=backend
                )
            except Exception:
                pass
            raise
        finally:
            _send_vscode_message({"action": "status", "state": "done"})


    def refresh_system_prompt(self) -> None:
        """Refresh the system prompt inside the session history."""
        if self._openai_messages and self._openai_messages[0]["role"] == "system":
            self._openai_messages[0]["content"] = SYSTEM_PROMPT

    def reset(self) -> None:
        """Clear conversation history."""
        self._gemini_history = []
        self._openai_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        from src import sessions
        sessions.clear_transcript()
        provider = get_provider(current_provider())
        backend = "gemini" if provider["backend"] == "gemini" else "openai-compat"
        history = self._gemini_history if backend == "gemini" else self._openai_messages
        sessions.save_session(
             session_id=sessions.get_active_session_id(),
             provider=current_provider(),
             model=current_model(),
             reasoning=current_reasoning(),
             history=history,
             backend=backend
        )


# ---------------------------------------------------------------------------
# Project Analysis Support
# ---------------------------------------------------------------------------

ANALYSIS_SYSTEM_PROMPT = (
    "You are an expert software architect analyzing a codebase.\n"
    "Your goal is to produce a comprehensive, dense, and highly structured reference document (KLAT.md) for this project.\n"
    "This document will be loaded directly into another AI assistant's system instructions.\n\n"
    "CRITICAL OUTPUT FORMATTING RULES:\n"
    "- Output ONLY the raw Markdown content. DO NOT wrap the entire output in a markdown code block (e.g. fenced with ```markdown and ```).\n"
    "- DO NOT write any conversational prefix, introductory text, or concluding remarks. Start directly with the main heading.\n\n"
    "STRICT TEMPLATE STRUCTURE:\n"
    "You must format your response exactly using this template structure:\n\n"
    "# KLAT.md — Project Knowledge Base\n\n"
    "## 1. Project Overview\n"
    "[Provide a concise summary, tech stack, and primary entrypoints here]\n\n"
    "## 2. Core Architecture & Flow\n"
    "[Explain components, runtime sequences, data flow, and design patterns here]\n\n"
    "## 3. Key Components & Files\n"
    "[Provide a Markdown table mapping key files to their roles here]\n\n"
    "## 4. Developer Workflows\n"
    "[Provide setup, run, configuration, and testing workflows here]\n\n"
    "## 5. Developer & Agent Guidelines\n"
    "[Specify path rules, constraints, session details, and safety parameters here]\n\n"
    "## 6. Project Conventions & Gotchas\n"
    "[Highlight command syntax, fallbacks, SDK limits, or coloring here]"
)

def _gather_project_context() -> str:
    from src.tools import _tree, _read_file
    from pathlib import Path
    
    context = []
    
    # 1. Project Directory Structure
    context.append("### Project Structure")
    try:
        structure = _tree(path=".", max_depth=4, show_hidden=False, dirs_only=False)
        context.append(structure)
    except Exception as e:
        context.append(f"Error gathering structure: {e}")
        
    # 2. Key configuration and meta files
    key_files = [
        "README.md",
        "requirements.txt",
        "package.json",
        "go.mod",
        "Cargo.toml",
        "setup.py",
        "pyproject.toml",
        "main.py",
        "app.py"
    ]
    
    for filename in key_files:
        p = Path(WORK_DIR) / filename
        if p.is_file():
            context.append(f"### File: {filename}")
            try:
                content = _read_file(filename, start_line=1, end_line=300)
                context.append(content)
            except Exception as e:
                context.append(f"Error reading file {filename}: {e}")
                
    return "\n\n".join(context)

def run_single_completion(prompt: str, system_prompt: str) -> str:
    """Run a single-turn completion (no history) using the active provider/model and return the reply."""
    from google import genai
    from google.genai import types
    from openai import OpenAI
    from src.config import ensure_env
    
    provider_name = current_provider()
    provider      = get_provider(provider_name)
    model         = current_model()
    
    if provider["backend"] == "gemini":
        project, location = ensure_env()
        if provider_name == "vertexai":
            client = genai.Client(vertexai=True, project=project, location=location)
        else:
            api_key = os.getenv(provider["env_key"], "")
            if not api_key:
                raise RuntimeError(f"{provider['env_key']} is not set. Add it to env/.env to use {provider['display_name']}.")
            client = genai.Client(api_key=api_key)
            
        response = client.models.generate_content(
            model=model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
            ),
        )
        usage = getattr(response, "usage_metadata", None)
        if usage:
            p_tok, c_tok = extract_gemini_tokens(usage)
            from src import sessions
            sessions.add_tokens(p_tok, c_tok)

        parts = []
        for p in response.candidates[0].content.parts:
            if hasattr(p, "text") and p.text:
                parts.append(p.text)
        return " ".join(parts).strip()
    else:
        api_key = os.getenv(provider["env_key"], "")
        if not api_key:
            raise RuntimeError(f"{provider['env_key']} is not set. Add it to env/.env to use {provider['display_name']}.")
        client = OpenAI(base_url=provider["base_url"], api_key=api_key)
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        usage = getattr(response, "usage", None)
        if usage:
            p_tok, c_tok = extract_openai_tokens(usage)
            from src import sessions
            sessions.add_tokens(p_tok, c_tok)

        return (response.choices[0].message.content or "").strip()
