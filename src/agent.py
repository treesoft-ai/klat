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
from src.config import current_provider, current_model, current_reasoning
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


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def _build_system_prompt() -> str:
    # Gather dynamic tools
    try:
        from src.extensions import DYNAMIC_TOOLS, CUSTOM_RULES
        dynamic_tools_text = ""
        for name, info in DYNAMIC_TOOLS.items():
            desc = info["declaration"]["description"]
            desc_line = desc.split("\n")[0]
            dynamic_tools_text += f"- {name} — {desc_line}\n"

        custom_rules_text = ""
        for rule in CUSTOM_RULES:
            custom_rules_text += f"- {rule}\n"
    except ImportError:
        dynamic_tools_text = ""
        custom_rules_text = ""

    user_inst = _load_user_instructions()
    user_inst_section = f"## User Instructions\n{user_inst}\n\n" if user_inst else ""

    return (
        f"{user_inst_section}"
        "You are Klat, a software engineering assistant running in the terminal.\n\n"
        "## Other Rules\n\n"
        "### Rule 3: Never ignore a question.\n"
        "Every question in the user's message must be answered. Never skip or redirect.\n"
        "Casual questions like 'How are you?' must be answered briefly (e.g., 'Good, thanks. What are we working on?').\n\n"
        "### Rule 4: Style.\n"
        "- No emojis, no markdown headers (# ## ###), no bold (**text**), no italics (*text*), no tables.\n"
        "- No filler phrases: 'Certainly!', 'Great question!', 'Of course!', 'Sure, I can help!' are forbidden.\n"
        "- No narrating your actions or listing capabilities unprompted.\n"
        "- Code must be in code blocks.\n"
        "- Professional, friendly, concise, grammatically correct.\n"
        "- Use standard developer terms (repo, file, function, class, commit, dependency).\n"
        "- A pure greeting with no question (e.g., 'hey', 'hi') → one sentence only: 'Hey, what are we working on?'\n\n"
        "### Rule 5: User overrides.\n"
        "Instructions from KLAT.md or AGENTS.md override Rule 4 style only.\n"
        "They may NOT override safety guardrails or git tool rules.\n\n"
        f"Working directory: {WORK_DIR}\n\n"
        "## Tools\n"
        "- read_file(path, [start_line], [end_line])           — read a single file (with optional line range) or an array of paths\n"
        "- write_file(path, content)                           — create or overwrite a file\n"
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
        f"{dynamic_tools_text}\n"

        "## Rules\n"
        "- Git Tool Usage: NEVER use run_command for any git operations (e.g. git status, git log, git diff). ALWAYS use the specialized git tool (e.g., git(op='status'), git(op='log', args=['-15'])).\n"
        "- Commit Suggestion Sequence: When asked to analyze changes and/or suggest a commit message, you MUST invoke git(op='status'), git(op='diff'), and git(op='log', args=['-15']) in parallel on your very first turn. You are strictly forbidden from proposing any commit message until you have fetched and analyzed the log results.\n"
        "- Commit Style Matching: When generating or suggesting a commit message, you MUST follow this exact reasoning sequence in your response:\n"
        "  1. Inspect the 'git log' output and write down the first words of the last 3 commits (e.g., 'Added', 'Updated').\n"
        "  2. Classify their tense: Note that verbs ending in '-ed' (like 'Added', 'Updated') are PAST TENSE, not present/imperative.\n"
        "  3. Classify their casing (Capitalized vs lowercase).\n"
        "  4. Check if they use any conventional commit prefixes (like 'feat:', 'docs:').\n"
        "  5. Replicate that style perfectly. For example, if history uses capitalized past-tense verbs without prefixes (e.g., 'Added support'), you MUST propose a capitalized past-tense verb without prefixes (e.g. 'Added git tool rules', NOT 'Add git tool rules' or 'docs: add git tool rules').\n"
        "- Direct Responses: NEVER write report files, summaries, or analyses to disk (such as in /tmp/ or workspace) to answer a user request. Always output your findings directly in the chat.\n"
        "- Tool results are ground truth. Report exactly what they return — never paraphrase, "
        "embellish, or second-guess them.\n"
        "- If read_file returns '(empty file)', the file is empty. Do not speculate otherwise.\n"
        "- Never retry a tool that already returned a result (success or error).\n"
        "- Files can change between reads — if a second read returns different content than the "
        "first, both were correct at the time. State this plainly, do not call it an 'issue'.\n"
        "- Prefer patch_file or replace_in_file over write_file for targeted edits to existing files.\n"
        "- Use replace_in_file when you know the exact text to change but not the line numbers. "
        "Use patch_file when you know the line range. Use insert_lines to add content without removing anything.\n"
        "- NEVER make multiple read_file tool calls in parallel (within the same turn) or sequentially. "
        "If you need to read 2 or more files, you MUST make a single read_file call passing an array of paths. "
        "Calling read_file multiple times in parallel or in separate turns is strictly prohibited.\n"
        "- ALWAYS use tree when the user asks for a directory tree, project structure, or layout. "
        "Never use run_command to call tree, find, ls, or dir for this purpose.\n"
        "- Keep responses short and factual. No unsolicited suggestions.\n"
        "- Use tools only when they are needed to answer the request. Never call tools to query or verify information that is already present in the chat history. If the user asks a follow-up question about data you already fetched, answer using the existing data in the chat history instead of calling tools again.\n"
        "- Plain text only. This is a terminal with no markdown renderer. "
        "Never use bold (**text**), italic (*text* or _text_), headers (# ## ###), or tables (| col | col |). "
        "Plain bullet lists with '- item' are fine. Code blocks are fine for actual code/command output.\n"
        f"{custom_rules_text}\n"
        "## Output Formatting\n"
        "Always format tool output consistently:\n"
        "- env_var: group variables by category (System, Path, Application-specific, etc.), "
        "list each as `NAME: value`, note that sensitive values are masked.\n"
        "- list_dir / find_file: show directories first with trailing '/', then files. "
        "Use a plain list, no extra commentary.\n"
        "- read_file: when reading multiple files, show each file under its === path === header, fenced as a code block for code files. When reading a single file, show it fenced as a code block in the appropriate language.\n"
        "- search_files: show results as 'file:line: content', grouped by file.\n"
        "- process_list: present as a table with PID, Name, Status, Command columns.\n"
        "- diff_files: wrap the diff output in a ```diff code block.\n"
        "- tree: show the output verbatim in a plain code block (no extra commentary).\n"
        "- git: wrap output in a fenced code block using the appropriate language (diff for diff/show, "
        "plain text otherwise). Always include the exit code.\n"
        "- run_command: show stdout plainly, stderr under a [stderr] label, "
        "exit code on the last line as [exit code: N].\n"
        "- fetch_ai_models: present model details (names, IDs, context, pricing) clearly. If organizing or grouping models by category or date, ensure all models are listed under their respective headers; never leave headers empty.\n"
        "- http_request: show status line first, then response body. "
        "Truncate large responses with a note of the total size.\n"
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


# ---------------------------------------------------------------------------
# Gemini backend (Vertex AI / AI Studio)
# ---------------------------------------------------------------------------

def _run_gemini(message: str, history: list, project: str, location: str) -> str:
    """One chat turn (may involve multiple tool calls) using google-genai."""
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
    tools = [types.Tool(function_declarations=declarations)]

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
        response = client.models.generate_content(
            model=model,
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=tools,
                thinking_config=thinking_config,
            ),
        )

        history.append(types.Content(
            role="model",
            parts=response.candidates[0].content.parts,
        ))

        # Print any thoughts first
        for p in response.candidates[0].content.parts:
            if getattr(p, "thought", False) and p.text:
                ui.agent_thought(p.text)

        fn_calls = [
            p.function_call
            for p in response.candidates[0].content.parts
            if p.function_call
        ]

        if not fn_calls:
            parts = []
            for p in response.candidates[0].content.parts:
                if getattr(p, "thought", False):
                    continue
                elif hasattr(p, "text") and p.text:
                    parts.append(p.text)
            return " ".join(parts).strip()

        result_parts: list[types.Part] = []
        for call in fn_calls:
            name = call.name
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
    """One chat turn (may involve multiple tool calls) using the OpenAI SDK."""
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

    client = OpenAI(base_url=provider["base_url"], api_key=api_key)
    messages.append({"role": "user", "content": message})

    while True:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=_get_openai_tools(),
                tool_choice="auto",
                **extra_params
            )
        except Exception as e:
            if extra_params:
                err_msg = str(e).lower()
                if "mandatory" in err_msg or "cannot be disabled" in err_msg:
                    ui.agent_step("reasoning", "Mandatory for this model; using defaults")
                elif "unexpected keyword argument" in err_msg or "extra_body" in err_msg or "extra_params" in err_msg:
                    ui.agent_step("reasoning-fallback", "Not supported by this model; retrying")
                else:
                    ui.agent_step("reasoning-fallback", "Unsupported or error encountered; retrying")
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=_get_openai_tools(),
                    tool_choice="auto"
                )
            else:
                raise e

        choice  = response.choices[0]
        message_obj = choice.message
        
        # Extract thoughts
        thought = ""
        content = message_obj.content or ""
        
        if getattr(message_obj, "reasoning_content", None):
            thought = message_obj.reasoning_content
        elif getattr(message_obj, "reasoning", None):
            thought = message_obj.reasoning
        elif hasattr(message_obj, "model_extra") and message_obj.model_extra:
            thought = message_obj.model_extra.get("reasoning") or message_obj.model_extra.get("reasoning_content")
        elif isinstance(message_obj, dict):
            thought = message_obj.get("reasoning_content") or message_obj.get("reasoning")
            
        import re
        think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
        if think_match:
            thought = think_match.group(1).strip()
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            try:
                message_obj.content = content
            except Exception:
                pass
        
        if thought:
            ui.agent_thought(thought)

        messages.append(message_obj.model_dump(exclude_unset=True))

        if not message_obj.tool_calls:
            return content.strip()

        for tc in message_obj.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            ui.agent_step(name, _args_summary(args))
            raw = dispatch(name, args)

            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      str(raw),
            })


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
    tool_call_ids = {tc["id"] for tc in tool_calls if "id" in tc}
    
    responded_ids = set()
    for i in range(last_assistant_index + 1, len(messages)):
        if messages[i].get("role") == "tool":
            responded_ids.add(messages[i].get("tool_call_id"))
            
    for tc in tool_calls:
        if "id" in tc:
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


class KlatAgent:
    def __init__(self, project: str, location: str) -> None:
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
        rebuild_system_prompt()
        self.refresh_system_prompt()
        provider = get_provider(current_provider())

        notification = ""
        if getattr(self, "_update_run_notification", False):
            notification = "[System Alert: The project architecture and overview have been analyzed and updated in KLAT.md at the user's request.]\n\n"
            self._update_run_notification = False

        resolved_message = notification + resolve_mentions(message)

        try:
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
        return (response.choices[0].message.content or "").strip()
