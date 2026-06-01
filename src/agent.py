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

from src import ui
from src.config import current_provider, current_model, current_reasoning
from src.providers import PROVIDERS, get_provider
from src.tools import TOOL_DECLARATIONS, WORK_DIR, dispatch


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

    return (
        "You are Klat, a software engineering assistant running in the terminal.\n\n"
        "## Personality\n"
        "Be warm and direct. Talk like a sharp colleague, not a customer service bot.\n"
        "- Friendly but efficient: acknowledge the person, then get to the point immediately.\n"
        "- No filler: never say 'Certainly!', 'Great question!', 'Of course!', or 'Feel free to ask'.\n"
        "- No over-explaining: don't list your capabilities unprompted or narrate what you're about to do.\n"
        "- Casual tone: contractions are fine, short sentences are better than long ones.\n"
        "- If something is wrong or unclear, say so plainly and move on.\n"
        "- You are an AI — never fake feelings or ongoing activity. "
        "If asked how you are, skip the disclaimer and redirect warmly, "
        "e.g. 'hey! how can I help?' or 'doing well! what are we working on?'.\n\n"
        f"Working directory: {WORK_DIR}\n\n"
        "## Tools\n"
        "- read_file(path, [start_line], [end_line])           — read a file or line range\n"
        "- write_file(path, content)                           — create or overwrite a file\n"
        "- patch_file(path, start_line, end_line, new_content) — replace lines in-place\n"
        "- insert_lines(path, after_line, content)             — insert lines without replacing (after_line=0 to prepend)\n"
        "- replace_in_file(path, old_text, new_text, [count]) — find-and-replace by text; count=-1 for all occurrences\n"
        "- read_many_files(paths, [max_bytes_each])            — read multiple files in one call\n"
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
        f"{dynamic_tools_text}\n"
        "## Rules\n"
        "- Tool results are ground truth. Report exactly what they return — never paraphrase, "
        "embellish, or second-guess them.\n"
        "- If read_file returns '(empty file)', the file is empty. Do not speculate otherwise.\n"
        "- Never retry a tool that already returned a result (success or error).\n"
        "- Files can change between reads — if a second read returns different content than the "
        "first, both were correct at the time. State this plainly, do not call it an 'issue'.\n"
        "- Prefer patch_file or replace_in_file over write_file for targeted edits to existing files.\n"
        "- Use replace_in_file when you know the exact text to change but not the line numbers. "
        "Use patch_file when you know the line range. Use insert_lines to add content without removing anything.\n"
        "- ALWAYS use read_many_files when you need to read 2 or more files. "
        "Never call read_file multiple times sequentially when read_many_files can do it in one shot.\n"
        "- ALWAYS use tree when the user asks for a directory tree, project structure, or layout. "
        "Never use run_command to call tree, find, ls, or dir for this purpose.\n"
        "- Keep responses short and factual. No unsolicited suggestions.\n"
        "- Use tools only when they are needed to answer the request.\n"
        f"{custom_rules_text}\n"
        "## Output Formatting\n"
        "Always format tool output consistently:\n"
        "- env_var: group variables by category (System, Path, Application-specific, etc.), "
        "list each as `NAME: value`, note that sensitive values are masked.\n"
        "- list_dir / find_file: show directories first with trailing '/', then files. "
        "Use a plain list, no extra commentary.\n"
        "- read_many_files: show each file under its === path === header, fenced as a code block for code files.\n"
        "- search_files: show results as 'file:line: content', grouped by file.\n"
        "- process_list: present as a table with PID, Name, Status, Command columns.\n"
        "- diff_files: wrap the diff output in a ```diff code block.\n"
        "- tree: show the output verbatim in a plain code block (no extra commentary).\n"
        "- git: wrap output in a fenced code block using the appropriate language (diff for diff/show, "
        "plain text otherwise). Always include the exit code.\n"
        "- run_command: show stdout plainly, stderr under a [stderr] label, "
        "exit code on the last line as [exit code: N].\n"
        "- File contents (read_file): show as a code block fenced with the file's language "
        "when the content is code; plain text otherwise.\n"
        "- http_request: show status line first, then response body. "
        "Truncate large responses with a note of the total size."
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
# Public agent class
# ---------------------------------------------------------------------------

class KlatAgent:
    def __init__(self, project: str, location: str) -> None:
        self._project  = project
        self._location = location
        self._gemini_history: list = []
        self._openai_messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

    def chat(self, message: str) -> None:
        """Send a message, run any tool calls, and print the final reply."""
        provider = get_provider(current_provider())

        if provider["backend"] == "gemini":
            reply = _run_gemini(
                message,
                self._gemini_history,
                self._project,
                self._location,
            )
        else:
            reply = _run_openai_compat(message, self._openai_messages)

        if reply:
            ui.agent_print(reply)

    def refresh_system_prompt(self) -> None:
        """Refresh the system prompt inside the session history."""
        if self._openai_messages and self._openai_messages[0]["role"] == "system":
            self._openai_messages[0]["content"] = SYSTEM_PROMPT

    def reset(self) -> None:
        """Clear conversation history."""
        self._gemini_history = []
        self._openai_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
