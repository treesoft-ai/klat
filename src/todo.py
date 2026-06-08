"""
To-Do/Tasks list management for Klat sessions.
"""

from pathlib import Path
import json
from src.sessions import get_sessions_dir

TODO_FILE_NAME: str = "todo.json"

def get_todo_file_path(session_id: str) -> Path:
    """Return the absolute Path to the session's to-do list JSON file."""
    if not session_id:
        raise ValueError("session_id must not be empty")
    return get_sessions_dir() / session_id / TODO_FILE_NAME

def load_todo_list(session_id: str) -> list[dict[str, str]]:
    """Load the to-do list for a given session. Return an empty list if it does not exist."""
    path = get_todo_file_path(session_id)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                raise TypeError("To-do list data must be a JSON array")
            return data
    except (json.JSONDecodeError, OSError, TypeError) as e:
        raise IOError(f"Failed to load to-do list for session {session_id}: {e}") from e

def save_todo_list(session_id: str, todo_list: list[dict[str, str]]) -> None:
    """Save the to-do list for a given session."""
    if not isinstance(todo_list, list):
        raise TypeError("todo_list must be a list")
    path = get_todo_file_path(session_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(todo_list, f, indent=2)
    except OSError as e:
        raise IOError(f"Failed to save to-do list for session {session_id}: {e}") from e

def add_task(session_id: str, text: str) -> None:
    """Add a new task to the session's to-do list."""
    if not text or not text.strip():
        raise ValueError("Task description text must not be empty")
    todo_list = load_todo_list(session_id)
    todo_list.append({"text": text.strip(), "status": "todo"})
    save_todo_list(session_id, todo_list)

def add_tasks(session_id: str, texts: list[str]) -> None:
    """Add multiple tasks to the session's to-do list."""
    if not isinstance(texts, list):
        raise TypeError("texts must be a list of strings")
    todo_list = load_todo_list(session_id)
    for text in texts:
        if not isinstance(text, str):
            raise TypeError("each task description must be a string")
        if text and text.strip():
            todo_list.append({"text": text.strip(), "status": "todo"})
    save_todo_list(session_id, todo_list)

def update_task_status(session_id: str, index: int, status: str) -> None:
    """Update status of a task by 1-based index. Valid status: 'todo', 'in_progress', 'done'."""
    valid_statuses = {"todo", "in_progress", "done"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Must be one of {valid_statuses}")
    todo_list = load_todo_list(session_id)
    if index < 1 or index > len(todo_list):
        raise IndexError(f"Task index {index} out of range (1-{len(todo_list)})")
    todo_list[index - 1]["status"] = status
    save_todo_list(session_id, todo_list)

def update_tasks_status(session_id: str, indices: list[int], status: str) -> None:
    """Update status of multiple tasks by their 1-based indices. Valid status: 'todo', 'in_progress', 'done'."""
    valid_statuses = {"todo", "in_progress", "done"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Must be one of {valid_statuses}")
    if not isinstance(indices, list):
        raise TypeError("indices must be a list of integers")
    todo_list = load_todo_list(session_id)
    for index in indices:
        if not isinstance(index, int):
            raise TypeError("each index must be an integer")
        if index < 1 or index > len(todo_list):
            raise IndexError(f"Task index {index} out of range (1-{len(todo_list)})")
        todo_list[index - 1]["status"] = status
    save_todo_list(session_id, todo_list)

def remove_task(session_id: str, index: int) -> None:
    """Remove a task from the session's to-do list by 1-based index."""
    todo_list = load_todo_list(session_id)
    if index < 1 or index > len(todo_list):
        raise IndexError(f"Task index {index} out of range (1-{len(todo_list)})")
    todo_list.pop(index - 1)
    save_todo_list(session_id, todo_list)

def remove_tasks(session_id: str, indices: list[int]) -> None:
    """Remove multiple tasks by their 1-based indices. Handles shifting correctly by removing in descending order."""
    if not isinstance(indices, list):
        raise TypeError("indices must be a list of integers")
    todo_list = load_todo_list(session_id)
    for index in indices:
        if not isinstance(index, int):
            raise TypeError("each index must be an integer")
        if index < 1 or index > len(todo_list):
            raise IndexError(f"Task index {index} out of range (1-{len(todo_list)})")
    
    sorted_indices = sorted(list(set(indices)), reverse=True)
    for index in sorted_indices:
        todo_list.pop(index - 1)
    save_todo_list(session_id, todo_list)

def clear_tasks(session_id: str, only_completed: bool = True) -> None:
    """Clear completed tasks, or all tasks if only_completed is False."""
    if only_completed:
        todo_list = load_todo_list(session_id)
        filtered = [item for item in todo_list if item.get("status") != "done"]
        save_todo_list(session_id, filtered)
    else:
        save_todo_list(session_id, [])

def format_todo_list_text(todo_list: list[dict[str, str]], numbered: bool = True) -> str:
    """Format the to-do list into a readable string representation using status markers."""
    lines = []
    status_markers = {
        "todo": "[ ]",
        "in_progress": "[/]",
        "done": "[x]"
    }
    for i, item in enumerate(todo_list, 1):
        status = item.get("status", "todo")
        marker = status_markers.get(status, "[ ]")
        text = item.get("text", "")
        if numbered:
            lines.append(f"{marker} {i}. {text}")
        else:
            lines.append(f"- {marker} {text}")
    return "\n".join(lines)
