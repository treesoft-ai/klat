"""
Global installation utility for Klat.
Generates wrapper scripts and configures the system PATH.
"""

import os
import sys
import shutil
from pathlib import Path

# Identify Klat repository root directory
KLAT_ROOT = Path(__file__).parent.parent.resolve()
BIN_DIR = Path.home() / ".klat" / "bin"


def get_python_interpreter() -> Path:
    """
    Resolve the best Python interpreter for Klat.
    Prefers the local .venv virtual environment to ensure dependencies are resolved.
    """
    if sys.platform == "win32":
        venv_python = KLAT_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = KLAT_ROOT / ".venv" / "bin" / "python"

    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def install_windows_wrappers(python_path: Path, main_path: Path) -> bool:
    """
    Generate cmd and ps1 wrappers on Windows.
    Appends the target bin directory to the user environment Registry path.
    """
    import winreg
    import ctypes

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    cmd_path = BIN_DIR / "klat.cmd"
    ps1_path = BIN_DIR / "klat.ps1"

    # Write CMD wrapper
    cmd_content = f'@echo off\n"{python_path}" "{main_path}" %*\n'
    cmd_path.write_text(cmd_content, encoding="utf-8")

    # Write PowerShell wrapper
    ps1_content = f'& "{python_path}" "{main_path}" $args\n'
    ps1_path.write_text(ps1_content, encoding="utf-8")

    # Update Registry PATH variable
    path_to_add = str(BIN_DIR)
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
        try:
            current_path, value_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_path = ""
            value_type = winreg.REG_EXPAND_SZ

        # Normalize paths for comparison
        existing_paths = [p.strip().lower() for p in current_path.split(";") if p.strip()]
        if path_to_add.lower() not in existing_paths:
            new_path = current_path
            if new_path and not new_path.endswith(";"):
                new_path += ";"
            new_path += path_to_add
            winreg.SetValueEx(key, "Path", 0, value_type, new_path)
            
            # Broadcast the environment update across the Windows OS
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment")
        
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"  Error updating Windows User Registry PATH: {e}")
        return False


def install_unix_wrappers(python_path: Path, main_path: Path) -> bool:
    """
    Generate bash wrapper on Unix and add target bin directory to shell startup scripts.
    """
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    wrapper_path = BIN_DIR / "klat"

    # Write Bash wrapper script
    bash_content = f'#!/bin/sh\nexec "{python_path}" "{main_path}" "$@"\n'
    wrapper_path.write_text(bash_content, encoding="utf-8")
    
    # Mark executable
    os.chmod(wrapper_path, 0o755)

    # Configure shell profiles if bin dir not in active PATH
    path_to_add = str(BIN_DIR)
    current_path = os.environ.get("PATH", "")
    if path_to_add not in current_path.split(":"):
        home = Path.home()
        export_line = f'\n# Klat Global Wrapper PATH\nexport PATH="{path_to_add}:$PATH"\n'
        
        profiles = [home / ".bashrc", home / ".zshrc", home / ".profile"]
        updated_any = False
        for profile in profiles:
            if profile.exists():
                try:
                    content = profile.read_text(encoding="utf-8", errors="replace")
                    if path_to_add not in content:
                        profile.write_text(content + export_line, encoding="utf-8")
                        updated_any = True
                except Exception as e:
                    print(f"  Error updating profile {profile}: {e}")
        
        if not updated_any:
            # Let the user know they need to configure it manually
            return False
    return True


def install_global() -> bool:
    """
    Executes the wrapper generation and system configuration.
    """
    python_path = get_python_interpreter()
    main_path = KLAT_ROOT / "main.py"

    if not main_path.exists():
        print(f"  Error: Klat entry point not found at: {main_path}")
        return False

    print(f"  Target directory: {BIN_DIR}")
    print(f"  Selected Python:  {python_path}")

    if sys.platform == "win32":
        success = install_windows_wrappers(python_path, main_path)
    else:
        success = install_unix_wrappers(python_path, main_path)

    if success:
        print(f"\n  ✓ Successfully generated global wrappers.")
        if sys.platform == "win32":
            print("  ✓ Environment updated. Please restart active terminals to apply PATH changes.")
        else:
            print("  ✓ PATH configuration applied to shell profiles. Run: source ~/.bashrc (or ~/.zshrc).")
    else:
        print("\n  ! Wrapper generated, but failed to update environment configuration automatically.")
        if sys.platform == "win32":
            print(f"  Manual action: Add '{BIN_DIR}' to your User PATH variable.")
        else:
            print(f"  Manual action: Append 'export PATH=\"{BIN_DIR}:$PATH\"' to your ~/.bashrc or ~/.zshrc.")

    return success
