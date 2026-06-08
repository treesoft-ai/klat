"""
Terminal and shell environment detection for Klat.

Detects the active shell (e.g. PowerShell, CMD, Bash) and terminal emulator
(e.g. VSCode, Windows Terminal, iTerm2) in a cross-platform manner using
in-memory process hierarchy traversal and environment variable inspections.
"""

import os
import subprocess
import sys
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Windows Native APIs (ctypes) for in-memory process resolution
# ---------------------------------------------------------------------------
if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_QUERY_INFORMATION = 0x0400

    class PROCESS_BASIC_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("ExitStatus", ctypes.c_ulong),
            ("PebBaseAddress", ctypes.c_void_p),
            ("AffinityMask", ctypes.c_void_p),
            ("BasePriority", ctypes.c_long),
            ("UniqueProcessId", ctypes.c_void_p),
            ("InheritedFromUniqueProcessId", ctypes.c_void_p),
        ]


def _get_windows_process_name(pid: int) -> str:
    """Retrieve the process name for a given PID on Windows using QueryFullProcessImageNameW."""
    if os.name != "nt":
        return ""
    try:
        kernel32 = ctypes.windll.kernel32
        hProcess = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not hProcess:
            hProcess = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
        if hProcess:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(hProcess, 0, buf, ctypes.byref(size)):
                kernel32.CloseHandle(hProcess)
                return os.path.basename(buf.value)
            kernel32.CloseHandle(hProcess)
    except Exception:
        pass
    return ""


def _get_windows_parent_pid(pid: int) -> int:
    """Retrieve the parent PID for a given PID on Windows using NtQueryInformationProcess."""
    if os.name != "nt":
        return 0
    try:
        PROCESS_QUERY_INFORMATION = 0x0400
        hProcess = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
        if not hProcess:
            return 0
        pbi = PROCESS_BASIC_INFORMATION()
        size = ctypes.c_ulong()
        status = ctypes.windll.ntdll.NtQueryInformationProcess(
            hProcess,
            0,  # ProcessBasicInformation
            ctypes.byref(pbi),
            ctypes.sizeof(pbi),
            ctypes.byref(size)
        )
        ctypes.windll.kernel32.CloseHandle(hProcess)
        if status == 0:
            return int(pbi.InheritedFromUniqueProcessId or 0)
    except Exception:
        pass
    return 0


# ---------------------------------------------------------------------------
# Linux Native procfs helpers
# ---------------------------------------------------------------------------
def _get_linux_process_name(pid: int) -> str:
    """Retrieve the process name for a given PID on Linux via /proc."""
    try:
        with open(f"/proc/{pid}/comm", "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        pass
    return ""


def _get_linux_parent_pid(pid: int) -> int:
    """Retrieve the parent PID for a given PID on Linux via /proc."""
    try:
        with open(f"/proc/{pid}/status", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("PPid:"):
                    return int(line.split()[1])
    except Exception:
        pass
    return 0


# ---------------------------------------------------------------------------
# macOS / general POSIX fallback using 'ps'
# ---------------------------------------------------------------------------
def _get_unix_process_info_via_ps(pid: int) -> Tuple[str, int]:
    """Retrieve process name and parent PID on macOS/Unix using ps command line."""
    try:
        # -o comm= gets command name, -o ppid= gets parent PID
        out = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "comm=,ppid="],
            stderr=subprocess.DEVNULL
        )
        parts = out.decode("utf-8", errors="ignore").strip().split()
        if len(parts) >= 2:
            ppid = int(parts[-1])
            name = os.path.basename(" ".join(parts[:-1]))
            return name, ppid
    except Exception:
        pass
    return "", 0


# ---------------------------------------------------------------------------
# Main Logic
# ---------------------------------------------------------------------------
def get_process_chain() -> List[str]:
    """Traverse up the process hierarchy and return a list of process names (lowercase)."""
    chain: List[str] = []
    try:
        pid = os.getpid()
    except Exception:
        return chain

    if os.name == "nt":
        for _ in range(6):
            if pid <= 0:
                break
            name = _get_windows_process_name(pid)
            if name:
                chain.append(name.lower())
            pid = _get_windows_parent_pid(pid)
    else:
        for _ in range(6):
            if pid <= 0:
                break
            name = _get_linux_process_name(pid)
            ppid = _get_linux_parent_pid(pid)
            if not name or ppid == 0:
                name, ppid = _get_unix_process_info_via_ps(pid)
            if name:
                chain.append(name.lower())
            pid = ppid

    return chain


def classify_terminal_and_shell(chain: List[str]) -> Tuple[str, str]:
    """Classify terminal and shell based on process names and environment variables."""
    terminal = "Unknown Terminal"
    shell = "Unknown Shell"

    # 1. Identify active shell from process chain
    for name in chain:
        if "powershell" in name or "pwsh" in name:
            if "pwsh" in name:
                shell = "PowerShell Core"
            else:
                shell = "Windows PowerShell"
            break
        elif "cmd" in name:
            shell = "CMD (Command Prompt)"
            break
        elif "bash" in name:
            shell = "Bash"
            break
        elif "zsh" in name:
            shell = "Zsh"
            break
        elif "fish" in name:
            shell = "Fish"
            break
        elif name in ("sh", "ash", "dash"):
            shell = name.upper()
            break

    # Fallback to SHELL environment variable if not identified in chain
    if shell == "Unknown Shell":
        env_shell = os.environ.get("SHELL")
        if env_shell:
            base_shell = os.path.basename(env_shell).lower()
            if "zsh" in base_shell:
                shell = "Zsh"
            elif "bash" in base_shell:
                shell = "Bash"
            elif "fish" in base_shell:
                shell = "Fish"
            elif "sh" in base_shell:
                shell = "Sh"

    # 2. Identify terminal emulator using environment variables
    term_program = os.environ.get("TERM_PROGRAM")
    if term_program:
        term_program_lower = term_program.lower()
        if "vscode" in term_program_lower:
            terminal = "VSCode Integrated Terminal"
        elif "iterm" in term_program_lower:
            terminal = "iTerm2"
        elif "apple_terminal" in term_program_lower:
            terminal = "Apple Terminal"
        elif "hyper" in term_program_lower:
            terminal = "Hyper"

    if terminal == "Unknown Terminal":
        if os.environ.get("WT_SESSION") or os.environ.get("WT_PROFILE_ID"):
            terminal = "Windows Terminal"
        elif os.environ.get("ALACRITTY_LOG") or os.environ.get("ALACRITTY_WINDOW_ID"):
            terminal = "Alacritty"
        elif os.environ.get("KITTY_WINDOW_ID"):
            terminal = "Kitty"
        elif os.environ.get("WEZTERM_PANE"):
            terminal = "WezTerm"
        elif os.environ.get("TERMINAL_EMULATOR") == "JetBrains-JediTerm":
            terminal = "JetBrains IDE Terminal"
        elif os.environ.get("TMUX"):
            terminal = "tmux"
        elif os.environ.get("STY"):
            terminal = "GNU Screen"

    # 3. Fallback to process chain if environment variables are not present or ambiguous
    if terminal == "Unknown Terminal":
        for name in chain:
            if "windowsterminal" in name:
                terminal = "Windows Terminal"
                break
            elif "code" in name or "cursor" in name or "windsurf" in name:
                terminal = "VSCode Integrated Terminal"
                break
            elif "iterm" in name:
                terminal = "iTerm2"
                break
            elif "alacritty" in name:
                terminal = "Alacritty"
                break
            elif "kitty" in name:
                terminal = "Kitty"
                break
            elif "wezterm" in name:
                terminal = "WezTerm"
                break
            elif "mintty" in name:
                terminal = "Mintty (Git Bash)"
                break
            elif any(ide in name for ide in ("pycharm", "idea", "clion", "webstorm")):
                terminal = "JetBrains IDE Terminal"
                break
            elif "tmux" in name:
                terminal = "tmux"
                break
            elif "screen" in name:
                terminal = "GNU Screen"
                break
            elif "conhost" in name:
                terminal = "Windows Console Host"
                break
            elif "terminal" in name:
                terminal = "Default Terminal Emulator"
                break

    # Windows Console fallback
    if terminal == "Unknown Terminal" and os.name == "nt":
        if any(sh in chain for sh in ("cmd.exe", "powershell.exe", "pwsh.exe")):
            if any("conhost" in name for name in chain):
                terminal = "Windows Console Host"
            else:
                terminal = "Windows Console"

    return terminal, shell


def detect_terminal_environment() -> str:
    """Detect and format the active terminal and shell environment description."""
    try:
        chain = get_process_chain()
        terminal, shell = classify_terminal_and_shell(chain)
        if terminal != "Unknown Terminal" and shell != "Unknown Shell":
            return f"{terminal} running {shell}"
        elif terminal != "Unknown Terminal":
            return terminal
        elif shell != "Unknown Shell":
            return shell
    except Exception:
        pass
    return "Unknown Environment"
