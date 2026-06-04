"""
tools.py — file and shell tools for Klat.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import json
from pathlib import Path

# Working directory captured once at startup — all relative paths resolve here.
WORK_DIR = Path.cwd()

# ---------------------------------------------------------------------------
# Blacklist helpers
# ---------------------------------------------------------------------------

_blacklist_cache = None

def _get_active_blacklist() -> list[str]:
    """Read ~/.klat/bench/active_blacklist.json dynamically if Klat Bench is active."""
    global _blacklist_cache
    from src import sessions
    session_id = sessions.get_active_session_id()
    if not (session_id and session_id.startswith("bench_")):
        _blacklist_cache = None
        return []
        
    blacklist_file = Path.home() / ".klat" / "bench" / "active_blacklist.json"
    if not blacklist_file.exists():
        _blacklist_cache = None
        return []
        
    try:
        with open(blacklist_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                _blacklist_cache = [str(item).lower().strip() for item in data]
                return _blacklist_cache
    except Exception:
        pass
    return []

def _is_blacklisted(path_or_str: str | Path | list[str]) -> bool:
    """Return True if the target or any part of the path is in the active blacklist."""
    blacklist = _get_active_blacklist()
    if not blacklist:
        return False
        
    if isinstance(path_or_str, list):
        return any(_is_blacklisted(p) for p in path_or_str)
        
    p_str = str(path_or_str).replace("\\", "/").lower()
    
    for item in blacklist:
        if item in p_str:
            return True
    return False


# ---------------------------------------------------------------------------
# Tool declarations (JSON-schema, provider-agnostic)
# ---------------------------------------------------------------------------

TOOL_DECLARATIONS = [
    {
        "name": "read_file",
        "description": (
            "Read one or more files. "
            "Pass a single file path string to read one file, or an array of file path strings to read multiple files at once. "
            "For a single file, you may also specify start_line and end_line to read a specific line range. "
            "When reading multiple files, returns a combined result where each file is clearly separated under its own '=== path ===' header line."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                    "description": "A single file path (string) or a list of file paths (array) to read multiple files at once.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to return (1-indexed). Single-file reads only.",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to return (1-indexed, inclusive). Single-file reads only.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write content to a file, creating it (and any parent directories) if it "
            "does not exist, or overwriting it completely if it does. "
            "Returns a confirmation string."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file.",
                },
                "content": {
                    "type": "string",
                    "description": "The full content to write to the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "patch_file",
        "description": (
            "Replace a range of lines in a file without rewriting the whole thing. "
            "Lines start_line through end_line (1-indexed, inclusive) are replaced "
            "with new_content. Use this for targeted edits to existing files."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file to edit.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to replace (1-indexed).",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to replace (1-indexed, inclusive).",
                },
                "new_content": {
                    "type": "string",
                    "description": "Replacement text for the specified line range. Should not have a trailing newline unless intentional.",
                },
            },
            "required": ["path", "start_line", "end_line", "new_content"],
        },
    },
    {
        "name": "list_dir",
        "description": (
            "List files and subdirectories in a directory. "
            "Pass '.' to list the working directory. "
            "Returns a newline-separated list of entries (directories end with '/')."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_files",
        "description": (
            "Search for a pattern in files under a directory. Uses ripgrep (rg) if "
            "available, otherwise falls back to a pure-Python search. "
            "Returns matching lines in 'file:line:content' format."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regular expression or literal string to search for.",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory to search in. Defaults to '.' (working directory).",
                },
                "include": {
                    "type": "string",
                    "description": "Glob pattern to restrict which files are searched, e.g. '*.py'.",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Whether the search is case-sensitive. Defaults to false.",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "run_command",
        "description": (
            "Run a shell command and return its output. "
            "WARNING: Do NOT use this tool to execute any git commands (status, log, diff, etc.). "
            "For all git operations, you MUST use the specialized 'git' tool instead. "
            "Commands run in the working directory by default. "
            "Returns stdout, stderr, and the exit code."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to run.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for the command. Defaults to the Klat working directory.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds. Defaults to 30.",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "move_file",
        "description": (
            "Move or rename a file or directory. "
            "Returns a confirmation string."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source path (absolute or relative).",
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path (absolute or relative).",
                },
            },
            "required": ["source", "destination"],
        },
    },
    {
        "name": "delete_file",
        "description": (
            "Delete a file. Returns a confirmation string. "
            "This is permanent — use with care."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file to delete.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "find_file",
        "description": (
            "Search for files by name or glob pattern, recursively under a directory. "
            "Different from search_files which searches file *contents*. "
            "Returns matching paths, one per line."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Filename glob pattern, e.g. '*.py', 'config.*', 'README*'.",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in. Defaults to '.' (working directory).",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "http_request",
        "description": (
            "Make an HTTP request (GET, POST, etc.) and return the response. "
            "Useful for fetching documentation, calling APIs, or downloading text content."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to request.",
                },
                "method": {
                    "type": "string",
                    "description": "HTTP method: GET, POST, PUT, PATCH, DELETE. Defaults to GET.",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP headers as key-value pairs.",
                },
                "body": {
                    "type": "string",
                    "description": "Optional request body (for POST/PUT/PATCH).",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds. Defaults to 15.",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "create_dir",
        "description": "Create a directory (and any missing parent directories). Returns a confirmation.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path of the directory to create.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "delete_dir",
        "description": (
            "Delete a directory and all its contents recursively. "
            "This is permanent — use with care."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the directory to delete.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "diff_files",
        "description": (
            "Show a unified diff between two files. "
            "Useful for reviewing changes before committing or comparing versions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path_a": {
                    "type": "string",
                    "description": "Path to the first (original) file.",
                },
                "path_b": {
                    "type": "string",
                    "description": "Path to the second (modified) file.",
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Number of context lines around each change. Defaults to 3.",
                },
            },
            "required": ["path_a", "path_b"],
        },
    },
    {
        "name": "env_var",
        "description": (
            "Read environment variables. Pass specific names to get their values, "
            "or pass an empty list [] to list ALL environment variables. "
            "Sensitive values (keys containing 'key', 'secret', 'token', 'password') are masked."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of environment variable names to read.",
                },
            },
            "required": ["names"],
        },
    },
    {
        "name": "process_list",
        "description": (
            "List running processes, optionally filtered by name. "
            "Useful for checking if a server is running or finding what is using a port."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "Optional substring to filter process names (case-insensitive).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "copy_file",
        "description": (
            "Copy a file (or directory) to a new destination, preserving metadata. "
            "Creates parent directories as needed. Returns a confirmation string."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Absolute or relative path to the file to copy.",
                },
                "destination": {
                    "type": "string",
                    "description": "Absolute or relative destination path (file or directory).",
                },
            },
            "required": ["source", "destination"],
        },
    },
    {
        "name": "git",
        "description": (
            "Run a git operation in the working directory (or a specified path). "
            "Supported operations: status, log, diff, add, commit, checkout, branch, stash, blame, show, pull, push. "
            "Returns the git command output as a string."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "op": {
                    "type": "string",
                    "description": "Git sub-command: status, log, diff, add, commit, checkout, branch, stash, blame, show, pull, push.",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional arguments to pass to the git sub-command, e.g. ['--oneline', '-10'] for log.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Directory to run git in. Defaults to the Klat working directory.",
                },
            },
            "required": ["op"],
        },
    },
    {
        "name": "insert_lines",
        "description": (
            "Insert new content into a file without replacing any existing lines. "
            "The new content is inserted *after* the given line number. "
            "Use after_line=0 to prepend at the top of the file. "
            "Returns a confirmation string."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file to edit.",
                },
                "after_line": {
                    "type": "integer",
                    "description": "Insert after this line number (1-indexed). Use 0 to prepend at the start of the file.",
                },
                "content": {
                    "type": "string",
                    "description": "The text to insert. A trailing newline is added automatically if missing.",
                },
            },
            "required": ["path", "after_line", "content"],
        },
    },

    {
        "name": "replace_in_file",
        "description": (
            "Find and replace text in a file by content, not by line number. "
            "Replaces the first occurrence by default; set count=-1 to replace all occurrences. "
            "Returns the number of replacements made."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file to edit.",
                },
                "old_text": {
                    "type": "string",
                    "description": "The exact string to search for (literal, not a regex).",
                },
                "new_text": {
                    "type": "string",
                    "description": "The replacement string.",
                },
                "count": {
                    "type": "integer",
                    "description": "Maximum number of replacements. Defaults to 1. Use -1 to replace all occurrences.",
                },
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "tree",
        "description": (
            "Display a directory structure as an indented tree. "
            "Much more useful than list_dir for understanding project layout at a glance. "
            "Skips hidden directories (.git, .venv, __pycache__, node_modules) by default. "
            "Returns the tree as a plain-text string."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Root directory to display. Defaults to '.' (working directory).",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum depth to recurse. Defaults to 4. Use -1 for unlimited.",
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": "Include hidden directories (.git, .venv, etc.). Defaults to false.",
                },
                "dirs_only": {
                    "type": "boolean",
                    "description": "Show only directories, not individual files. Defaults to false.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "fetch_ai_models",
        "description": "Fetch, filter, sort, and paginate the list of available AI models from OpenRouter.",
        "parameters": {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Search term to match model ID or name (case-insensitive)."
                },
                "provider": {
                    "type": "string",
                    "description": "Filter by provider name (e.g., 'anthropic', 'openai', 'google', 'deepseek')."
                },
                "min_context_length": {
                    "type": "integer",
                    "description": "Minimum context length in tokens."
                },
                "modality": {
                    "type": "string",
                    "description": "Required input modality (e.g., 'image', 'audio', 'video', 'file')."
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["created", "context_length", "pricing", "name"],
                    "description": "Field to sort models by. Defaults to 'created' (to show the latest models first)."
                },
                "sort_order": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "description": "Sort order. Defaults to 'desc' for created/context_length/pricing, and 'asc' for name."
                },
                "page": {
                    "type": "integer",
                    "description": "Page number to fetch (1-indexed). Defaults to 1."
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of models to return per page. Defaults to 15."
                },
                "include_latest": {
                    "type": "boolean",
                    "description": "Whether to include auto-redirecting latest router models (e.g., ID starting with '~' or ending/containing 'latest'). Defaults to false."
                }
            },
            "required": []
        }
    }
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve(path: str) -> Path:
    """Resolve a path relative to WORK_DIR (unless it is already absolute)."""
    if _is_blacklisted(path):
        raise FileNotFoundError(f"[Errno 2] No such file or directory: '{path}'")
        
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = WORK_DIR / p
    resolved = p.resolve()
    
    if _is_blacklisted(resolved):
        raise FileNotFoundError(f"[Errno 2] No such file or directory: '{path}'")
        
    return resolved


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------

def _read_file(path: str | list[str], start_line: int | None = None, end_line: int | None = None) -> str:
    if isinstance(path, list):
        results: list[str] = []
        for raw_path in path:
            p = _resolve(raw_path)
            header = f"=== {raw_path} ==="
            if not p.exists():
                results.append(f"{header}\nError: not found\n")
                continue
            if not p.is_file():
                results.append(f"{header}\nError: not a file\n")
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                results.append(f"{header}\n{content}\n")
            except Exception as e:
                results.append(f"{header}\nError reading file: {e}\n")
        return "\n".join(results) if results else "(no files requested)"

    p = _resolve(path)
    if not p.exists():
        return f"Error: not found: {p}"
    if not p.is_file():
        return f"Error: not a file: {p}"
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if not lines:
            return "(empty file)"

        # Apply line range (1-indexed)
        lo = (start_line - 1) if start_line is not None else 0
        hi = end_line if end_line is not None else len(lines)
        lo = max(0, lo)
        hi = min(len(lines), hi)

        if lo >= hi:
            return f"Error: invalid line range {start_line}-{end_line} (file has {len(lines)} lines)"

        slice_lines = lines[lo:hi]
        result = "".join(slice_lines)
        if start_line is not None or end_line is not None:
            result = f"[lines {lo+1}-{hi} of {len(lines)}]\n" + result
        return result if result.strip() else "(empty file)"
    except Exception as e:
        return f"Error reading {p}: {e}"


def _write_file(path: str, content: str) -> str:
    p = _resolve(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {p.stat().st_size} bytes to {p}"
    except Exception as e:
        return f"Error writing {p}: {e}"


def _patch_file(path: str, start_line: int, end_line: int, new_content: str) -> str:
    p = _resolve(path)
    if not p.exists():
        return f"Error: not found: {p}"
    if not p.is_file():
        return f"Error: not a file: {p}"
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        total = len(lines)
        if start_line < 1 or end_line < start_line or start_line > total:
            return f"Error: invalid line range {start_line}-{end_line} (file has {total} lines)"

        lo = start_line - 1
        hi = min(end_line, total)

        # Ensure replacement ends with a newline if the file uses them
        replacement = new_content
        if lines and lines[0].endswith("\n") and not replacement.endswith("\n"):
            replacement += "\n"

        new_lines = lines[:lo] + [replacement] + lines[hi:]
        p.write_text("".join(new_lines), encoding="utf-8")
        return f"Patched {p}: replaced lines {start_line}-{hi} ({hi - lo} line(s) → 1 chunk)"
    except Exception as e:
        return f"Error patching {p}: {e}"


def _list_dir(path: str) -> str:
    p = _resolve(path)
    if not p.exists():
        return f"Error: not found: {p}"
    if not p.is_dir():
        return f"Error: not a directory: {p}"
    try:
        entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        entries = [e for e in entries if not _is_blacklisted(e.name)]
        lines = [f"{e.name}/" if e.is_dir() else e.name for e in entries]
        return "\n".join(lines) if lines else "(empty directory)"
    except Exception as e:
        return f"Error listing {p}: {e}"


def _search_files(
    pattern: str,
    path: str = ".",
    include: str | None = None,
    case_sensitive: bool = False,
) -> str:
    search_path = _resolve(path)

    # Try ripgrep first
    rg = shutil.which("rg")
    if rg:
        cmd = [rg, "--line-number", "--no-heading", "--with-filename"]
        if not case_sensitive:
            cmd.append("--ignore-case")
        if include:
            cmd += ["--glob", include]
        cmd += [pattern, str(search_path)]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15
            )
            out_lines = [line for line in result.stdout.splitlines() if not _is_blacklisted(line.split(":", 1)[0])]
            return "\n".join(out_lines) if out_lines else "(no matches)"
        except Exception:
            pass  # fall through to Python search

    # Pure-Python fallback
    import re
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        rx = re.compile(pattern, flags)
    except re.error as e:
        return f"Error: invalid regex: {e}"

    base = search_path if search_path.is_dir() else search_path.parent
    targets: list[Path] = []
    if search_path.is_file():
        targets = [search_path]
    else:
        glob = f"**/{include}" if include else "**/*"
        targets = [f for f in base.glob(glob) if f.is_file() and not _is_blacklisted(f)]

    matches: list[str] = []
    for fp in sorted(targets):
        try:
            for i, line in enumerate(
                fp.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if rx.search(line):
                    matches.append(f"{fp}:{i}:{line}")
        except Exception:
            continue

    return "\n".join(matches) if matches else "(no matches)"


def _run_command(command: str, cwd: str | None, timeout: int) -> str:
    # Check if command itself is blacklisted
    if _is_blacklisted(command):
        return f"sh: 1: {command.split()[0] if command.split() else 'command'}: not found\n[exit code: 127]"

    # Intercept extension commands starting with /
    cmd_stripped = command.strip()
    if cmd_stripped.startswith("/"):
        parts = cmd_stripped[1:].split(None, 1)
        cmd_name = parts[0].lower()
        remainder = parts[1] if len(parts) > 1 else ""
        try:
            from src.extensions import DYNAMIC_COMMANDS
            if cmd_name in DYNAMIC_COMMANDS:
                import io
                import contextlib
                f = io.StringIO()
                with contextlib.redirect_stdout(f):
                    DYNAMIC_COMMANDS[cmd_name]["handler"](remainder, None)
                out = f.getvalue()
                parts_out = []
                if out.strip():
                    out_lines = [line for line in out.splitlines() if not _is_blacklisted(line)]
                    parts_out.append("\n".join(out_lines).rstrip())
                parts_out.append("[exit code: 0]")
                return "\n".join(parts_out)
        except Exception as e:
            return f"Error executing extension command: {e}\n[exit code: 1]"

    run_cwd = _resolve(cwd) if cwd else WORK_DIR
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(run_cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        parts = []
        if result.stdout.strip():
            out_lines = [line for line in result.stdout.splitlines() if not _is_blacklisted(line)]
            parts.append("\n".join(out_lines).rstrip())
        if result.stderr.strip():
            err_lines = [line for line in result.stderr.splitlines() if not _is_blacklisted(line)]
            parts.append(f"[stderr]\n" + "\n".join(err_lines).rstrip())
            
        parts = [p for p in parts if p.strip()]
        parts.append(f"[exit code: {result.returncode}]")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    except Exception as e:
        return f"Error running command: {e}"


def _move_file(source: str, destination: str) -> str:
    src = _resolve(source)
    dst = _resolve(destination)
    if not src.exists():
        return f"Error: not found: {src}"
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"Moved {src} → {dst}"
    except Exception as e:
        return f"Error moving {src}: {e}"


def _delete_file(path: str) -> str:
    p = _resolve(path)
    if not p.exists():
        return f"Error: not found: {p}"
    try:
        if p.is_dir():
            return f"Error: {p} is a directory (use a directory-specific tool)"
        p.unlink()
        return f"Deleted {p}"
    except Exception as e:
        return f"Error deleting {p}: {e}"


def _find_file(pattern: str, path: str = ".") -> str:
    base = _resolve(path)
    if not base.exists():
        return f"Error: not found: {base}"
    if not base.is_dir():
        return f"Error: not a directory: {base}"
    try:
        matches = sorted(base.rglob(pattern))
        matches = [m for m in matches if not _is_blacklisted(m)]
        return "\n".join(str(m) for m in matches) if matches else "(no matches)"
    except Exception as e:
        return f"Error searching {base}: {e}"


def _http_request(
    url: str,
    method: str = "GET",
    headers: dict | None = None,
    body: str | None = None,
    timeout: int = 15,
) -> str:
    import urllib.request
    import urllib.error

    method = method.upper()
    data = body.encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            # Decode text responses; truncate very large ones
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:
                text = repr(raw[:200])
            if len(text) > 8000:
                text = text[:8000] + f"\n... (truncated, total {len(raw)} bytes)"
            return f"HTTP {resp.status} {resp.reason}\nContent-Type: {content_type}\n\n{text}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code} {e.reason}"
    except Exception as e:
        return f"Error: {e}"


def _create_dir(path: str) -> str:
    p = _resolve(path)
    try:
        p.mkdir(parents=True, exist_ok=True)
        return f"Created directory: {p}"
    except Exception as e:
        return f"Error creating {p}: {e}"


def _delete_dir(path: str) -> str:
    p = _resolve(path)
    if not p.exists():
        return f"Error: not found: {p}"
    if not p.is_dir():
        return f"Error: not a directory (use delete_file for files): {p}"
    try:
        shutil.rmtree(p)
        return f"Deleted directory: {p}"
    except Exception as e:
        return f"Error deleting {p}: {e}"


def _diff_files(path_a: str, path_b: str, context_lines: int = 3) -> str:
    import difflib

    pa = _resolve(path_a)
    pb = _resolve(path_b)
    for p, label in [(pa, path_a), (pb, path_b)]:
        if not p.exists():
            return f"Error: not found: {label}"
        if not p.is_file():
            return f"Error: not a file: {label}"
    try:
        lines_a = pa.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        lines_b = pb.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        diff = list(difflib.unified_diff(
            lines_a, lines_b,
            fromfile=str(pa), tofile=str(pb),
            n=context_lines,
        ))
        return "".join(diff) if diff else "(files are identical)"
    except Exception as e:
        return f"Error diffing files: {e}"


def _env_var(names: list[str]) -> str:
    _SENSITIVE = {"key", "secret", "token", "password", "passwd", "pwd"}

    def _mask(name: str, val: str) -> str:
        if any(s in name.lower() for s in _SENSITIVE):
            return val[:4] + "****" if len(val) > 4 else "****"
        return val

    # Empty list → dump all env vars
    if not names:
        lines = [
            f"{k}: {_mask(k, v)}"
            for k, v in sorted(os.environ.items())
        ]
        return "\n".join(lines) if lines else "(no environment variables set)"

    lines = []
    for name in names:
        val = os.environ.get(name)
        if val is None:
            lines.append(f"{name}: (not set)")
        else:
            lines.append(f"{name}: {_mask(name, val)}")
    return "\n".join(lines)


def _process_list(filter_str: str | None = None) -> str:
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(["pid", "name", "status", "cmdline"]):
            try:
                name = p.info["name"] or ""
                if filter_str and filter_str.lower() not in name.lower():
                    continue
                cmd = " ".join(p.info.get("cmdline") or [])[:80]
                procs.append(f"{p.info['pid']:>6}  {name:<25}  {p.info['status']:<10}  {cmd}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if not procs:
            return "(no matching processes)"
        header = f"{'PID':>6}  {'Name':<25}  {'Status':<10}  Command"
        sep = "-" * 80
        return "\n".join([header, sep] + procs)
    except ImportError:
        # Fall back to OS commands
        if os.name == "nt":
            cmd = "tasklist"
            if filter_str:
                cmd += f' /FI "IMAGENAME eq *{filter_str}*"'
        else:
            cmd = f"ps aux | grep -i {filter_str}" if filter_str else "ps aux"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout.strip() or "(no output)"


def _copy_file(source: str, destination: str) -> str:
    src = _resolve(source)
    dst = _resolve(destination)
    if not src.exists():
        return f"Error: not found: {src}"
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
            return f"Copied directory {src} -> {dst}"
        else:
            shutil.copy2(str(src), str(dst))
            return f"Copied {src} -> {dst}"
    except Exception as e:
        return f"Error copying {src}: {e}"


_GIT_ALLOWED_OPS = {
    "status", "log", "diff", "add", "commit", "checkout",
    "branch", "stash", "blame", "show", "pull", "push",
}

def _git(op: str, args: list[str] | None, cwd: str | None) -> str:
    op = op.lower().strip()
    if op not in _GIT_ALLOWED_OPS:
        return (
            f"Error: unsupported git operation '{op}'. "
            f"Allowed: {', '.join(sorted(_GIT_ALLOWED_OPS))}"
        )
    git_exe = shutil.which("git")
    if not git_exe:
        return "Error: git is not installed or not found in PATH."
        
    # Check arguments for blacklist
    if args and any(_is_blacklisted(arg) for arg in args):
        return f"fatal: pathspec '{args[0]}' did not match any files"
        
    run_cwd = _resolve(cwd) if cwd else WORK_DIR
    cmd = [git_exe, op] + (args or [])
    try:
        result = subprocess.run(
            cmd, cwd=str(run_cwd),
            capture_output=True, text=True, timeout=30,
        )
        parts = []
        if result.stdout.strip():
            out_lines = [line for line in result.stdout.splitlines() if not _is_blacklisted(line)]
            parts.append("\n".join(out_lines).rstrip())
        if result.stderr.strip():
            err_lines = [line for line in result.stderr.splitlines() if not _is_blacklisted(line)]
            parts.append(f"[stderr]\n" + "\n".join(err_lines).rstrip())
            
        parts = [p for p in parts if p.strip()]
        
        if not parts:
            parts.append(f"(git {op}: no output, exit code {result.returncode})")
        else:
            parts.append(f"[exit code: {result.returncode}]")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return f"Error: git {op} timed out after 30s"
    except Exception as e:
        return f"Error running git {op}: {e}"


def _insert_lines(path: str, after_line: int, content: str) -> str:
    p = _resolve(path)
    if not p.exists():
        return f"Error: not found: {p}"
    if not p.is_file():
        return f"Error: not a file: {p}"
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        total = len(lines)
        if after_line < 0 or after_line > total:
            return f"Error: after_line {after_line} is out of range (file has {total} lines; use 0 to prepend)"
        # Ensure the insertion ends with a newline
        insertion = content if content.endswith("\n") else content + "\n"
        new_lines = lines[:after_line] + [insertion] + lines[after_line:]
        p.write_text("".join(new_lines), encoding="utf-8")
        return f"Inserted {len(insertion.splitlines())} line(s) after line {after_line} in {p}"
    except Exception as e:
        return f"Error inserting into {p}: {e}"



def _replace_in_file(path: str, old_text: str, new_text: str, count: int = 1) -> str:
    p = _resolve(path)
    if not p.exists():
        return f"Error: not found: {p}"
    if not p.is_file():
        return f"Error: not a file: {p}"
    try:
        original = p.read_text(encoding="utf-8", errors="replace")
        if old_text not in original:
            return f"No occurrences of the specified text found in {p}"
        if count == -1:
            updated = original.replace(old_text, new_text)
            n = original.count(old_text)
        else:
            updated = original.replace(old_text, new_text, count)
            n = min(count, original.count(old_text))
        p.write_text(updated, encoding="utf-8")
        return f"Replaced {n} occurrence(s) in {p}"
    except Exception as e:
        return f"Error replacing in {p}: {e}"


def _tree(
    path: str = ".",
    max_depth: int = 4,
    show_hidden: bool = False,
    dirs_only: bool = False,
) -> str:
    _SKIP = {"__pycache__", ".git", ".venv", "node_modules", ".mypy_cache",
             ".pytest_cache", ".tox", "dist", "build", ".eggs"}
    _SKIP.update(_get_active_blacklist())

    root = _resolve(path)
    if not root.exists():
        return f"Error: not found: {root}"
    if not root.is_dir():
        return f"Error: not a directory: {root}"

    lines: list[str] = [str(root)]

    def _walk(directory: Path, prefix: str, depth: int) -> None:
        if max_depth != -1 and depth > max_depth:
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        except PermissionError:
            lines.append(prefix + "    [permission denied]")
            return

        entries = [e for e in entries if show_hidden or not e.name.startswith(".")]
        entries = [e for e in entries if e.name not in _SKIP]
        if dirs_only:
            entries = [e for e in entries if e.is_dir()]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
            lines.append(prefix + connector + entry.name + ("/" if entry.is_dir() else ""))
            if entry.is_dir():
                extension = "    " if is_last else "\u2502   "
                _walk(entry, prefix + extension, depth + 1)

    _walk(root, "", 1)
    return "\n".join(lines)


def _fetch_ai_models(
    search: str | None = None,
    provider: str | None = None,
    min_context_length: int | None = None,
    modality: str | None = None,
    sort_by: str = "created",
    sort_order: str | None = None,
    page: int = 1,
    limit: int = 15,
    include_latest: bool = False,
) -> str:
    import json
    import urllib.request
    import urllib.error
    from datetime import datetime, timezone

    # Fetch models from OpenRouter
    url = "https://openrouter.ai/api/v1/models"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Klat-Agent/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return f"Error fetching models: HTTP {e.code} {e.reason}"
    except Exception as e:
        return f"Error fetching models: {e}"

    models = data.get("data", [])
    if not models:
        return "No models returned from API."

    # Client-side filtering
    filtered_models = []
    for m in models:
        # 1. Search term match
        if search:
            s_term = search.lower()
            m_id = m.get("id", "").lower()
            m_name = m.get("name", "").lower()
            if s_term not in m_id and s_term not in m_name:
                continue

        # 2. Provider match
        if provider:
            p_term = provider.lower()
            m_id = m.get("id", "").lower()
            m_name = m.get("name", "").lower()
            parts = m_id.split("/")
            provider_part = parts[0] if parts else ""
            
            # Check ID prefix or provider part in the ID
            if p_term not in provider_part and p_term not in m_name:
                continue

        # 3. Min context length
        if min_context_length is not None:
            ctx_len = m.get("context_length", 0)
            if ctx_len is None or ctx_len < min_context_length:
                continue

        # 4. Modality match
        if modality:
            mod_term = modality.lower()
            input_mods = m.get("architecture", {}).get("input_modalities", [])
            input_mods_lower = [str(im).lower() for im in input_mods] if input_mods else []
            mod_str = m.get("architecture", {}).get("modality", "").lower()
            if mod_term not in input_mods_lower and mod_term not in mod_str:
                continue

        # 5. Exclude auto-redirecting latest router models unless asked
        if not include_latest:
            m_id = m.get("id", "")
            is_router_latest = m_id.startswith("~") or m_id.endswith("latest") or "-latest" in m_id or ":latest" in m_id
            if is_router_latest:
                continue

        filtered_models.append(m)

    # Resolve default sort order based on sort_by
    if not sort_order:
        if sort_by == "name":
            sort_order = "asc"
        else:
            sort_order = "desc"

    # Client-side sorting
    reverse = (sort_order == "desc")
    
    def sort_key(model):
        if sort_by == "created":
            return int(model.get("created") or 0)
        elif sort_by == "context_length":
            return int(model.get("context_length") or 0)
        elif sort_by == "pricing":
            try:
                return float(model.get("pricing", {}).get("prompt") or 0.0)
            except Exception:
                return 0.0
        elif sort_by == "name":
            return model.get("name", "").lower()
        return 0

    filtered_models.sort(key=sort_key, reverse=reverse)

    total_matched = len(filtered_models)
    if total_matched == 0:
        return "No models matched the specified filters."

    # Pagination
    page = max(1, page)
    limit = max(1, limit)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    sliced_models = filtered_models[start_idx:end_idx]

    if not sliced_models:
        return f"Page {page} is out of range. Total matched models: {total_matched}."

    total_pages = (total_matched + limit - 1) // limit

    lines = []
    lines.append(f"Found {total_matched} matching model(s). Showing page {page} of {total_pages} (models {start_idx + 1}-{min(end_idx, total_matched)}).")
    lines.append("-" * 80)

    for m in sliced_models:
        m_id = m.get("id", "unknown")
        m_name = m.get("name", "Unknown Name")
        
        # Created Date
        created_ts = m.get("created")
        created_date = "N/A"
        if created_ts:
            try:
                created_date = datetime.fromtimestamp(created_ts, tz=timezone.utc).strftime('%Y-%m-%d')
            except Exception:
                pass
                
        ctx_len = m.get("context_length")
        ctx_str = f"{ctx_len:,} tokens" if ctx_len is not None else "N/A"
        
        # Modalities
        input_mods = m.get("architecture", {}).get("input_modalities")
        mod_str = ", ".join(input_mods) if input_mods else "text"
        
        # Pricing per million tokens
        pricing = m.get("pricing", {})
        prompt_price_raw = pricing.get("prompt")
        completion_price_raw = pricing.get("completion")
        
        try:
            p_price = float(prompt_price_raw) * 1_000_000 if prompt_price_raw is not None else None
            c_price = float(completion_price_raw) * 1_000_000 if completion_price_raw is not None else None
            if p_price is not None and c_price is not None:
                pricing_str = f"Prompt: ${p_price:.4f}/M, Completion: ${c_price:.4f}/M"
            elif p_price is not None:
                pricing_str = f"Prompt: ${p_price:.4f}/M"
            else:
                pricing_str = "Free" if prompt_price_raw == "0" else "Unknown pricing"
        except Exception:
            pricing_str = "Unknown pricing"

        lines.append(f"Model: {m_name}")
        lines.append(f"  ID: {m_id}")
        lines.append(f"  Created: {created_date} | Context: {ctx_str} | Input: {mod_str}")
        lines.append(f"  Pricing: {pricing_str}")
        
        desc = m.get("description", "").strip()
        if desc:
            first_line = desc.split("\n")[0]
            if len(first_line) > 120:
                first_line = first_line[:117] + "..."
            lines.append(f"  Description: {first_line}")
            
        cutoff = m.get("knowledge_cutoff")
        if cutoff:
            lines.append(f"  Knowledge Cutoff: {cutoff}")
            
        lines.append("")

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def get_all_tool_declarations() -> list[dict]:
    """Combine static built-in tool declarations with dynamic extension tools."""
    from src.extensions import DYNAMIC_TOOLS
    dynamic_decls = [info["declaration"] for info in DYNAMIC_TOOLS.values()]
    return TOOL_DECLARATIONS + dynamic_decls


def dispatch(name: str, args: dict) -> str:
    try:
        if name in ("read_file", "read_file_slice"):
            return _read_file(
                args["path"],
                args.get("start_line"),
                args.get("end_line"),
            )
        if name == "write_file":
            return _write_file(args["path"], args["content"])
        if name == "patch_file":
            return _patch_file(
                args["path"],
                int(args["start_line"]),
                int(args["end_line"]),
                args["new_content"],
            )
        if name == "list_dir":
            return _list_dir(args.get("path", "."))
        if name == "search_files":
            return _search_files(
                args["pattern"],
                args.get("path", "."),
                args.get("include"),
                bool(args.get("case_sensitive", False)),
            )
        if name == "run_command":
            return _run_command(
                args["command"],
                args.get("cwd"),
                int(args.get("timeout", 30)),
            )
        if name == "move_file":
            return _move_file(args["source"], args["destination"])
        if name == "delete_file":
            return _delete_file(args["path"])
        if name == "find_file":
            return _find_file(args["pattern"], args.get("path", "."))
        if name == "http_request":
            return _http_request(
                args["url"],
                args.get("method", "GET"),
                args.get("headers"),
                args.get("body"),
                int(args.get("timeout", 15)),
            )
        if name == "create_dir":
            return _create_dir(args["path"])
        if name == "delete_dir":
            return _delete_dir(args["path"])
        if name == "diff_files":
            return _diff_files(
                args["path_a"],
                args["path_b"],
                int(args.get("context_lines", 3)),
            )
        if name == "env_var":
            return _env_var(args["names"])
        if name == "process_list":
            return _process_list(args.get("filter"))
        if name == "copy_file":
            return _copy_file(args["source"], args["destination"])
        if name == "git":
            return _git(
                args["op"],
                args.get("args"),
                args.get("cwd"),
            )
        if name == "insert_lines":
            return _insert_lines(
                args["path"],
                int(args["after_line"]),
                args["content"],
            )

        if name == "replace_in_file":
            return _replace_in_file(
                args["path"],
                args["old_text"],
                args["new_text"],
                int(args.get("count", 1)),
            )
        if name == "tree":
            return _tree(
                args.get("path", "."),
                int(args.get("max_depth", 4)),
                bool(args.get("show_hidden", False)),
                bool(args.get("dirs_only", False)),
            )
        if name == "fetch_ai_models":
            return _fetch_ai_models(
                search=args.get("search"),
                provider=args.get("provider"),
                min_context_length=args.get("min_context_length"),
                modality=args.get("modality"),
                sort_by=args.get("sort_by", "created"),
                sort_order=args.get("sort_order"),
                page=int(args.get("page", 1)),
                limit=int(args.get("limit", 15)),
                include_latest=bool(args.get("include_latest", False)),
            )

        # Check dynamic tools
        from src.extensions import DYNAMIC_TOOLS
        if name in DYNAMIC_TOOLS:
            handler = DYNAMIC_TOOLS[name]["handler"]
            return str(handler(**args))

        return f"Unknown tool: {name}"
    except KeyError as e:
        return f"Error: missing required argument {e}"
    except TypeError as e:
        return f"Error: bad tool arguments: {e}"
    except Exception as e:
        return f"Error in {name}: {e}"

