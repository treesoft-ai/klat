import os
import json
import shutil
from pathlib import Path
from typing import Any

SESSIONS_DIR = Path.home() / ".klat" / "sessions"
ACTIVE_SESSION_FILE = Path.home() / ".klat" / "settings" / "config.json"

# In-memory transcript to keep track of current session's UI events
_current_transcript: list[dict[str, Any]] = []
_active_session_id: str | None = None

# Session-wide token tracking
_session_tokens: dict[str, int] = {"input": 0, "output": 0}

def add_tokens(input_tokens: int, output_tokens: int) -> None:
    global _session_tokens
    _session_tokens["input"] += input_tokens
    _session_tokens["output"] += output_tokens

def get_token_usage() -> dict[str, int]:
    return _session_tokens

def reset_session_tokens() -> None:
    global _session_tokens
    _session_tokens = {"input": 0, "output": 0}

def get_sessions_dir() -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR

def set_active_session_id(session_id: str) -> None:
    global _active_session_id
    _active_session_id = session_id
    # Persist in config.json
    config_dir = ACTIVE_SESSION_FILE.parent
    config_dir.mkdir(parents=True, exist_ok=True)
    current_data = {}
    if ACTIVE_SESSION_FILE.exists():
        try:
            with open(ACTIVE_SESSION_FILE, "r", encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception:
            pass
    current_data["active_session"] = session_id
    with open(ACTIVE_SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(current_data, f, indent=2)

def get_active_session_id() -> str:
    global _active_session_id
    if _active_session_id:
        return _active_session_id
    
    # Try reading from config.json
    if ACTIVE_SESSION_FILE.exists():
        try:
            with open(ACTIVE_SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                active = data.get("active_session")
                if active:
                    _active_session_id = active
                    return active
        except Exception:
            pass
            
    # Auto-generate if not found
    from datetime import datetime
    new_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    set_active_session_id(new_id)
    return new_id

def list_sessions() -> list[str]:
    sdir = get_sessions_dir()
    sessions = []
    for p in sdir.iterdir():
        if p.is_dir() and (p / "session.json").exists():
            sessions.append(p.name)
    return sorted(sessions)

def delete_session(session_id: str) -> None:
    sdir = get_sessions_dir() / session_id
    if sdir.exists():
        shutil.rmtree(sdir)

_replaying = False

def record_ui_event(event_type: str, **kwargs) -> None:
    """Record a UI event to the current in-memory transcript."""
    if _replaying:
        return
    event = {"type": event_type}
    event.update(kwargs)
    _current_transcript.append(event)

def get_transcript() -> list[dict[str, Any]]:
    return _current_transcript

def clear_transcript() -> None:
    global _current_transcript
    _current_transcript = []
    reset_session_tokens()

def serialize_history(history: list, backend: str) -> list:
    if backend == "gemini":
        serialized = []
        for content in history:
            if hasattr(content, "model_dump"):
                serialized.append(content.model_dump())
            else:
                serialized.append(content)
        return serialized
    else:
        return history

def deserialize_history(serialized: list, backend: str) -> list:
    if not serialized:
        return []
    if backend == "gemini":
        try:
            from google.genai import types
            return [types.Content.model_validate(item) for item in serialized]
        except Exception as e:
            print(f"Error deserializing Gemini history: {e}")
            return []
    else:
        return serialized

def save_session(session_id: str, provider: str, model: str, reasoning: str, history: list, backend: str) -> None:
    session_path = get_sessions_dir() / session_id
    session_path.mkdir(parents=True, exist_ok=True)
    
    state = {
        "session_id": session_id,
        "provider": provider,
        "model": model,
        "reasoning": reasoning,
        "backend": backend,
        "history": serialize_history(history, backend),
        "transcript": _current_transcript,
        "token_usage": _session_tokens
    }
    
    with open(session_path / "session.json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def load_session(session_id: str) -> dict | None:
    session_file = get_sessions_dir() / session_id / "session.json"
    if not session_file.exists():
        return None
        
    try:
        with open(session_file, "r", encoding="utf-8") as f:
            state = json.load(f)
            
        global _current_transcript
        _current_transcript = state.get("transcript", [])
        
        global _session_tokens
        _session_tokens = state.get("token_usage", {"input": 0, "output": 0})
        
        # Deserialize history
        backend = state.get("backend", "openai-compat")
        state["history"] = deserialize_history(state.get("history", []), backend)
        return state
    except Exception as e:
        print(f"Error loading session: {e}")
        return None


class OutputInterceptor:
    def __init__(self, original_stdout):
        self.original_stdout = original_stdout
        self.captured_text = []

    def write(self, data):
        self.original_stdout.write(data)
        self.captured_text.append(data)

    def flush(self):
        self.original_stdout.flush()


def set_replaying(val: bool) -> None:
    global _replaying
    _replaying = val


def replay_transcript() -> None:
    global _replaying
    from src import ui
    _replaying = True
    try:
        for event in _current_transcript:
            etype = event.get("type")
            if etype in ("user", "command"):
                print(f"{ui.GREEN}>{ui.RESET} {event.get('text', '')}")
            elif etype == "thought":
                ui.agent_thought(event.get("text", ""))
            elif etype == "step":
                ui.agent_step(event.get("action", ""), event.get("detail", ""))
            elif etype == "reply":
                ui.agent_print(event.get("text", ""))
            elif etype == "error":
                ui.agent_error(event.get("text", ""))
            elif etype == "command_output":
                print(event.get("text", ""), end="")
    finally:
        _replaying = False
