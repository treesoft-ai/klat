"""
tools.py — file and shell tools for Klat.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

# Working directory captured once at startup — all relative paths resolve here.
WORK_DIR = Path.cwd()


# ---------------------------------------------------------------------------
# Tool declarations (JSON-schema, provider-agnostic)
# ---------------------------------------------------------------------------

TOOL_DECLARATIONS = [
    {
        "name": "read_file",
        "description": (
            "Read a file's contents. Optionally restrict to a line range by providing "
            "start_line and/or end_line (1-indexed, inclusive). "
            "Returns the file contents (or the requested slice) as a string."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to return (1-indexed). Omit to start from the beginning.",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to return (1-indexed, inclusive). Omit to read to end of file.",
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
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve(path: str) -> Path:
    """Resolve a path relative to WORK_DIR (unless it is already absolute)."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = WORK_DIR / p
    return p.resolve()


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------

def _read_file(path: str, start_line: int | None, end_line: int | None) -> str:
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
            out = result.stdout.strip()
            return out if out else "(no matches)"
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
        targets = [f for f in base.glob(glob) if f.is_file()]

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
            parts.append(result.stdout.rstrip())
        if result.stderr.strip():
            parts.append(f"[stderr]\n{result.stderr.rstrip()}")
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
        if name == "read_file":
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

