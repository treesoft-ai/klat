"""
extensions.py — extension loader and SDK provider for Klat.
"""

import sys
import os
import json
import zipfile
import shutil
import importlib.util
from types import ModuleType, SimpleNamespace
from pathlib import Path
from src import ui

def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        text = text.replace("✓", "[ok]").replace("→", "->").replace("·", "*")
        print(text)

# ---------------------------------------------------------------------------
# Virtual 'klat' SDK Module Injection
# ---------------------------------------------------------------------------

CUSTOM_RULES: list[str] = []
DYNAMIC_TOOLS: dict[str, dict] = {}

def _log(msg: str) -> None:
    """Extension log message."""
    _safe_print(f"  {ui.DIM}[ext log]{ui.RESET} {msg}")


def _say(msg: str) -> None:
    """Allows extensions to directly outputs messages as Klat."""
    ui.agent_print(msg)

def _add_rule(rule: str) -> None:
    """Adds a dynamic rule to Klat's system prompt."""
    if rule not in CUSTOM_RULES:
        CUSTOM_RULES.append(rule)
        # Force rebuild system prompt if agent is loaded
        from src import agent
        agent.rebuild_system_prompt()

# Setup virtual module
klat_mod = ModuleType("klat")
klat_mod.log = _log
klat_mod.ai = SimpleNamespace(say=_say)
klat_mod.system_prompt = SimpleNamespace(add_rule=_add_rule)
klat_mod.ui = SimpleNamespace(
    print_accent=lambda msg: _safe_print(f"  {ui.GREEN}{msg}{ui.RESET}"),
    print_dim=lambda msg: _safe_print(f"  {ui.DIM}{msg}{ui.RESET}"),
)

sys.modules["klat"] = klat_mod

# Paths
# ---------------------------------------------------------------------------

EXTENSIONS_DIR = Path.home() / ".klat" / "extensions"


# Create extension
# ---------------------------------------------------------------------------

def create_extension(folder_path_str: str) -> str:
    """Generate a boilerplate extension directory containing manifest.json and main.py."""
    folder_path = Path(folder_path_str).resolve()
    if folder_path.exists():
        if any(folder_path.iterdir() if folder_path.is_dir() else ()):
            raise FileExistsError(f"Destination folder already exists and is not empty: {folder_path_str}")
    
    # Extract standard name from path
    ext_name = folder_path.name
    # Strip any invalid extension characters just in case
    clean_name = "".join(c for c in ext_name if c.isalnum() or c in "_-")
    if not clean_name:
        clean_name = "my_extension"
        
    folder_path.mkdir(parents=True, exist_ok=True)
    
    manifest_path = folder_path / "manifest.json"
    main_path = folder_path / "main.py"
    
    manifest_data = {
        "name": clean_name,
        "version": "1.0.0",
        "description": f"Boilerplate extension for {clean_name}",
        "tools": [
            {
                "name": f"{clean_name}_hello",
                "description": "A starter hello world tool for this extension",
                "entrypoint": "hello_world",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the person to greet"
                        }
                    },
                    "required": ["name"]
                }
            }
        ]
    }
    
    main_code = f'''"""
Boilerplate logic for extension: {clean_name}
"""
import klat

def hello_world(name: str) -> str:
    """
    Greets the user and demonstrates virtual SDK logging and UI outputs.
    """
    klat.log(f"hello_world tool executed for name: {{name}}")
    klat.ui.print_accent(f"Greeting {{name}} from the {clean_name} extension!")
    return f"Hello, {{name}}! Welcome to the {clean_name} extension."
'''
    
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    main_path.write_text(main_code, encoding="utf-8")
    
    return str(folder_path)


# Export extension
# ---------------------------------------------------------------------------

def export_extension(folder_path_str: str) -> str:
    """Validate and package a folder into a .ke file."""
    folder_path = Path(folder_path_str).resolve()
    if not folder_path.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder_path_str}")

    manifest_path = folder_path / "manifest.json"
    main_path = folder_path / "main.py"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing required manifest.json in {folder_path_str}")
    if not main_path.exists():
        raise FileNotFoundError(f"Missing required main.py in {folder_path_str}")

    # Validate manifest json
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid manifest.json: {e}")

    # Validate minimal fields
    required = ["name", "version", "description", "tools"]
    for field in required:
        if field not in manifest:
            raise KeyError(f"Manifest missing required field: '{field}'")

    ext_name = manifest["name"].strip()
    if not ext_name or any(c in ext_name for c in "/\\ <>:|?*"):
        raise ValueError(f"Invalid extension name in manifest: '{ext_name}'")

    # Verify functions exist in main.py
    main_code = main_path.read_text(encoding="utf-8")
    for tool in manifest.get("tools", []):
        entrypoint = tool.get("entrypoint")
        if not entrypoint:
            raise KeyError(f"Tool in manifest missing 'entrypoint'")
        if f"def {entrypoint}" not in main_code:
            # Simple static check; we could also import it but static check is safer at pack-time
            raise AttributeError(f"Function 'def {entrypoint}' not found in main.py")

    # Pack zip
    zip_filename = f"{ext_name}.ke"
    zip_path = Path.cwd() / zip_filename

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(manifest_path, "manifest.json")
        zip_file.write(main_path, "main.py")

    return str(zip_path)

# ---------------------------------------------------------------------------
# Import extension
# ---------------------------------------------------------------------------

def import_extension(file_path_str: str) -> str:
    """Import and unzip a .ke file into the extensions directory."""
    file_path = Path(file_path_str).resolve()
    if not file_path.exists() or file_path.is_dir():
        raise FileNotFoundError(f"Extension file not found: {file_path_str}")

    if not zipfile.is_zipfile(file_path):
        raise ValueError(f"File {file_path_str} is not a valid Klat extension (.ke)")

    # Read manifest from zip to get the name
    with zipfile.ZipFile(file_path, "r") as zip_ref:
        names = zip_ref.namelist()
        if "manifest.json" not in names:
            raise ValueError("Extension archive is missing manifest.json")
        if "main.py" not in names:
            raise ValueError("Extension archive is missing main.py")

        manifest_data = zip_ref.read("manifest.json").decode("utf-8")
        try:
            manifest = json.loads(manifest_data)
        except Exception as e:
            raise ValueError(f"Invalid manifest.json inside archive: {e}")

        ext_name = manifest.get("name", "").strip()
        if not ext_name:
            raise ValueError("Extension manifest missing name")

        # Warn user
        _safe_print(f"\n{ui.GREEN}! SECURITY WARNING{ui.RESET}")
        _safe_print(f"  Extension '{ext_name}' contains Python code that will run on your machine.")
        confirm = input(f"  Are you sure you want to import this extension? (y/N): ").strip().lower()
        if confirm not in ("y", "yes"):
            raise PermissionError("Extension import cancelled by user.")

        # Extract
        dest_dir = EXTENSIONS_DIR / ext_name
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        zip_ref.extractall(dest_dir)

    return ext_name

# ---------------------------------------------------------------------------
# Load extensions
# ---------------------------------------------------------------------------

def load_extensions(silent: bool = True) -> int:
    """Scans and dynamically imports all extensions. Returns count of loaded extensions."""
    if not EXTENSIONS_DIR.exists():
        return 0

    count = 0
    for entry in EXTENSIONS_DIR.iterdir():
        # Only load if it's a directory and NOT disabled (ends with .disabled)
        if entry.is_dir() and not entry.name.endswith(".disabled"):
            manifest_path = entry / "manifest.json"
            main_path = entry / "main.py"

            if manifest_path.exists() and main_path.exists():
                try:
                    # Read manifest
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    ext_name = manifest["name"]

                    # Load module dynamically
                    spec = importlib.util.spec_from_file_location(f"ext_{ext_name}", main_path)
                    if spec is None or spec.loader is None:
                        continue
                    mod = importlib.util.module_from_spec(spec)
                    
                    # Add to sys.modules under ext_<name>
                    sys.modules[f"ext_{ext_name}"] = mod
                    spec.loader.exec_module(mod)

                    # Register tools
                    for tool in manifest.get("tools", []):
                        name = tool["name"]
                        entrypoint = tool["entrypoint"]
                        handler = getattr(mod, entrypoint, None)
                        if handler is None:
                            if not silent:
                                _safe_print(f"  {ui.GREEN}!{ui.RESET} Tool '{name}' entrypoint '{entrypoint}' not found in {ext_name}'s main.py")
                            continue

                        # Register the tool declaration and its handler
                        DYNAMIC_TOOLS[name] = {
                            "declaration": {
                                "name": name,
                                "description": tool["description"],
                                "parameters": tool["parameters"]
                            },
                            "handler": handler
                        }

                    count += 1
                    if not silent:
                        _safe_print(f"  {ui.GREEN}✓{ui.RESET} Loaded extension: {ext_name} (version {manifest.get('version', '1.0.0')})")
                except Exception as e:
                    if not silent:
                        _safe_print(f"  {ui.GREEN}!{ui.RESET} Failed to load extension from {entry.name}: {e}")
    return count


# ---------------------------------------------------------------------------
# Extension Management commands
# ---------------------------------------------------------------------------

def list_extensions() -> list[dict]:
    """Scan EXTENSIONS_DIR and return metadata and status of all extensions."""
    if not EXTENSIONS_DIR.exists():
        return []

    results = []
    for entry in EXTENSIONS_DIR.iterdir():
        if entry.is_dir():
            # Check if disabled
            is_disabled = entry.name.endswith(".disabled")
            clean_name = entry.name.replace(".disabled", "")
            
            manifest_path = entry / "manifest.json"
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    results.append({
                        "name": manifest.get("name", clean_name),
                        "version": manifest.get("version", "1.0.0"),
                        "description": manifest.get("description", ""),
                        "enabled": not is_disabled,
                        "folder_name": entry.name
                    })
                except Exception:
                    # corrupted manifest
                    results.append({
                        "name": clean_name,
                        "version": "unknown",
                        "description": "Failed to read manifest.json",
                        "enabled": not is_disabled,
                        "folder_name": entry.name
                    })
    return results


def enable_extension(name: str) -> None:
    """Enable a disabled extension by renaming its folder."""
    disabled_path = EXTENSIONS_DIR / f"{name}.disabled"
    enabled_path = EXTENSIONS_DIR / name

    if enabled_path.exists():
        # Already enabled
        return

    if not disabled_path.exists():
        raise FileNotFoundError(f"Extension '{name}' not found.")

    disabled_path.rename(enabled_path)


def disable_extension(name: str) -> None:
    """Disable an enabled extension by renaming its folder."""
    enabled_path = EXTENSIONS_DIR / name
    disabled_path = EXTENSIONS_DIR / f"{name}.disabled"

    if disabled_path.exists():
        # Already disabled
        return

    if not enabled_path.exists():
        raise FileNotFoundError(f"Extension '{name}' not found.")

    # Remove active dynamic tools associated with it before renaming
    manifest_path = enabled_path / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for tool in manifest.get("tools", []):
                tool_name = tool["name"]
                if tool_name in DYNAMIC_TOOLS:
                    del DYNAMIC_TOOLS[tool_name]
        except Exception:
            pass

    enabled_path.rename(disabled_path)


def remove_extension(name: str) -> None:
    """Remove (delete) an extension from storage completely."""
    enabled_path = EXTENSIONS_DIR / name
    disabled_path = EXTENSIONS_DIR / f"{name}.disabled"

    target_path = None
    if enabled_path.exists():
        target_path = enabled_path
    elif disabled_path.exists():
        target_path = disabled_path

    if not target_path:
        raise FileNotFoundError(f"Extension '{name}' not found.")

    # Clean active tools
    manifest_path = target_path / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for tool in manifest.get("tools", []):
                tool_name = tool["name"]
                if tool_name in DYNAMIC_TOOLS:
                    del DYNAMIC_TOOLS[tool_name]
        except Exception:
            pass

    shutil.rmtree(target_path)
