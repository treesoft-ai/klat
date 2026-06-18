"""
Klat Bench extension — zero-evaluator sandbox benchmarking runner.
"""
import os
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import klat

def handle_bench(args_str: str, agent: Any = None) -> Any:
    """
    Control Klat Benchmarking operations:
    - /bench create [name] [num]
    - /bench select [name] [num]
    - /bench start [task_id]   (omit task_id to run all tasks in order)
    - /bench clean             Clean the results of the active benchmark, keeping tasks
    """
    parts = args_str.strip().split(None, 1)
    if not parts:
        klat.ui.print_accent("Klat Bench Command Interface")
        print("  /bench create [name] [num]       Initialize a new benchmark version structure")
        print("  /bench select [name] [num]       Switch the active benchmark workspace")
        print("  /bench start [task_id]           Run a task (omit task_id to run all in order)")
        print("  /bench clean                     Clean the results of the active benchmark, keeping tasks")
        return None

    subcmd = parts[0].lower()
    remainder = parts[1].strip() if len(parts) > 1 else ""

    if subcmd == "create":
        _bench_create(remainder)
        return None
    elif subcmd == "select":
        _bench_select(remainder)
        return None
    elif subcmd == "start":
        return _bench_start(remainder, agent)
    elif subcmd == "clean":
        _bench_clean()
        return None
    else:
        klat.log(f"Unknown bench subcommand: {subcmd}")
        klat.ui.print_dim("Type /bench for help.")
        return None

def _bench_create(remainder: str) -> None:
    parts = remainder.strip().split()
    if len(parts) < 2:
        klat.ui.print_accent("Usage: /bench create [name] [number] (e.g. /bench create standard 1)")
        return
        
    name, num = parts[0], parts[1]
    version = f"{name}-{num}"
    bench_dir = Path.home() / ".klat" / "bench" / version
    tasks_dir = bench_dir / "tasks"
    results_dir = bench_dir / "results"
    
    try:
        tasks_dir.mkdir(parents=True, exist_ok=True)
        results_dir.mkdir(parents=True, exist_ok=True)
        klat.ui.print_accent(f"Initialized benchmark version structure at: {bench_dir}")
    except Exception as e:
        klat.log(f"Failed to create benchmark structure: {e}")

def _bench_select(remainder: str) -> None:
    parts = remainder.strip().split()
    bench_dir = Path.home() / ".klat" / "bench"
    config_file = bench_dir / "config.json"
    
    if not parts:
        # Show active version
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    active = cfg.get("active_version")
                    if active:
                        klat.ui.print_accent(f"Active benchmark workspace: {active}")
                        return
            except Exception:
                pass
        klat.ui.print_accent("No active benchmark workspace set. Use: /bench select [name] [number]")
        return
        
    if len(parts) < 2:
        klat.ui.print_accent("Usage: /bench select [name] [number] (e.g. /bench select standard 1)")
        return
        
    name, num = parts[0], parts[1]
    version_name = f"{name}-{num}"
    version_dir = bench_dir / version_name
    
    # Switch active version in config
    bench_dir.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
            
    cfg["active_version"] = version_name
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        klat.ui.print_accent(f"Active benchmark workspace switched to: {version_name}")
        if not version_dir.exists():
            klat.ui.print_dim(f"Warning: Workspace directory {version_dir} does not exist yet. Run '/bench create {name} {num}' to initialize it.")
    except Exception as e:
        klat.log(f"Failed to switch benchmark version: {e}")

def _bench_clean() -> None:
    bench_dir = Path.home() / ".klat" / "bench"
    config_file = bench_dir / "config.json"
    active_version = None

    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                active_version = cfg.get("active_version")
        except Exception:
            pass

    if not active_version:
        klat.ui.print_accent("Error: No active benchmark version configured. Run /bench select [name] [number] first.")
        return

    version_dir = bench_dir / active_version
    results_dir = version_dir / "results"
    if not results_dir.exists():
        klat.ui.print_accent(f"Results directory for {active_version} does not exist: {results_dir}")
        return

    try:
        shutil.rmtree(results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)
        klat.ui.print_accent(f"Successfully cleaned results for active benchmark: {active_version}")
    except Exception as e:
        klat.log(f"Failed to clean results: {e}")

def _bench_start(task_id: str, agent: Any) -> Any:
    from src.agent import KlatAgent
    from src.config import ensure_env
    from src import sessions

    if not task_id:
        return _bench_start_all(agent)

    bench_dir = Path.home() / ".klat" / "bench"
    config_file = bench_dir / "config.json"
    active_version = None
    
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                active_version = cfg.get("active_version")
        except Exception:
            pass
            
    if not active_version:
        klat.log("Error: No active benchmark version configured. Run /bench select [name] [number] first.")
        return None
        
    task_file = bench_dir / active_version / "tasks" / f"{task_id}.json"
    if not task_file.exists():
        klat.log(f"Error: Task file not found at: {task_file}")
        return None
        
    try:
        with open(task_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
    except Exception as e:
        klat.log(f"Error reading task file: {e}")
        return None
        
    organic_prompt = task_data.get("prompt") or task_data.get("organic_prompt")
    if not organic_prompt:
        klat.log("Error: Task file does not contain a 'prompt' or 'organic_prompt' field.")
        return None
        
    klat.ui.print_accent(f"Starting task: {task_id} under benchmark version {active_version}...")
    
    # 1. Setup workspace files from initial_state if provided
    initial_state = task_data.get("initial_state") or {}
    files = initial_state.get("files") or task_data.get("files") or {}
    if files:
        klat.ui.print_accent("Setting up workspace files...")
        for rel_path_str, content in files.items():
            dest = Path.cwd() / rel_path_str
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            klat.ui.print_dim(f"  Setup file: {rel_path_str}")
            
    # 2. Perform workspace backup for deterministic submit verification
    backup_dir = Path.home() / ".klat" / "bench" / "active_backup"
    klat.ui.print_accent("Creating workspace backup for verified evaluation...")
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    for root, dirs, files_in_dir in os.walk(Path.cwd()):
        dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__", "node_modules", ".klat", "klat-bench")]
        for file in files_in_dir:
            src_file = Path(root) / file
            try:
                rel_path = src_file.relative_to(Path.cwd())
            except ValueError:
                continue
            dest_file = backup_dir / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dest_file)
            
    # 2.5 Save active blacklist and allowlist if present
    blacklist = task_data.get("blacklist") or []
    blacklist_file = Path.home() / ".klat" / "bench" / "active_blacklist.json"
    if blacklist:
        try:
            with open(blacklist_file, "w", encoding="utf-8") as bf:
                json.dump(blacklist, bf, indent=2)
            klat.ui.print_accent(f"Active blacklist initialized: {blacklist}")
        except Exception as e:
            klat.log(f"Warning: Failed to save active blacklist: {e}")
    else:
        if blacklist_file.exists():
            try:
                blacklist_file.unlink()
            except Exception:
                pass

    allowlist = task_data.get("allowlist")  # dict[str, bool] or None
    allowlist_file = Path.home() / ".klat" / "bench" / "active_allowlist.json"
    if allowlist and isinstance(allowlist, dict):
        try:
            with open(allowlist_file, "w", encoding="utf-8") as af:
                json.dump(allowlist, af, indent=2)
            blocked = [k for k, v in allowlist.items() if not v]
            if blocked:
                klat.ui.print_accent(f"Active tool restrictions initialized: {blocked}")
        except Exception as e:
            klat.log(f"Warning: Failed to save active allowlist: {e}")
    else:
        if allowlist_file.exists():
            try:
                allowlist_file.unlink()
            except Exception:
                pass

    # 3. Save the original session so we can restore it after the bench task,
    #    then reset/clear and start an isolated bench session.
    original_session_id = sessions.get_active_session_id()
    original_openai_messages = list(agent._openai_messages) if hasattr(agent, "_openai_messages") else []
    original_gemini_history = list(agent._gemini_history) if hasattr(agent, "_gemini_history") else []

    sessions.delete_session(f"bench_{task_id}")
    sessions.clear_transcript()
    sessions.set_active_session_id(f"bench_{task_id}")

    # Re-initialize the agent with a completely fresh context
    project, location = ensure_env()
    new_agent = KlatAgent(project, location)
    new_agent.reset()

    klat.ui.print_accent(f"Session reset. Session ID: bench_{task_id}")
    klat.ui.print_accent(f"Injecting organic prompt: {organic_prompt}")

    # 4. Initialize the live telemetry log before the first tool call
    from src.config import current_provider, current_model, current_reasoning
    from src.providers import get_provider as _get_provider
    _prov = current_provider()
    _model = current_model()
    _reason = current_reasoning()
    _backend = "gemini" if _get_provider(_prov).get("backend") == "gemini" else "openai-compat"

    task_results_dir = bench_dir / active_version / "results" / task_id
    task_results_dir.mkdir(parents=True, exist_ok=True)

    _init_log: dict = {
        "session_id": f"bench_{task_id}",
        "task_id": task_id,
        "provider": _prov,
        "model": _model,
        "reasoning": _reason,
        "backend": _backend,
        "tool_calls": [],
        "files_read": [],
        "files_modified": [],
        "file_changes": {},
        "transcript": None,
        "history": None,
    }
    try:
        with open(task_results_dir / "telemetry.json", "w", encoding="utf-8") as _lf:
            json.dump(_init_log, _lf, indent=2)
    except Exception as _e:
        klat.log(f"Warning: Failed to initialize telemetry log: {_e}")

    # 5. Run the task
    try:
        new_agent.chat(organic_prompt)
    finally:

        # 7. Finalize telemetry now that the agent has finished
        _bench_finalize(new_agent, task_id, task_results_dir, backup_dir)

        # 7. Delete the bench session so it doesn't bleed into the main Klat session
        sessions.delete_session(f"bench_{task_id}")

        # 8. Restore the original session so the main Klat loop is unaffected
        sessions.clear_transcript()
        sessions.set_active_session_id(original_session_id)
        if agent and hasattr(agent, "_openai_messages"):
            agent._openai_messages = original_openai_messages
        if agent and hasattr(agent, "_gemini_history"):
            agent._gemini_history = original_gemini_history
        KlatAgent.active_instance = agent

        # 9. Git revert all changes and wait 2 seconds
        klat.ui.print_accent("Resetting workspace to HEAD and cleaning untracked files...")
        import subprocess
        import time
        try:
            subprocess.run(
                ["git", "reset", "--hard", "HEAD"],
                cwd=str(Path.cwd()),
                capture_output=True,
                text=True,
                timeout=30,
            )
            subprocess.run(
                ["git", "clean", "-fd"],
                cwd=str(Path.cwd()),
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as e:
            klat.log(f"Warning: git reset/clean failed: {e}")

        klat.ui.print_accent("Waiting 2 seconds before continuing...")
        time.sleep(2)

    return new_agent


def _bench_start_all(agent: Any) -> Any:
    """Run every task in the active benchmark that has a 'sort' field, in ascending order.
    After each task the session is auto-submitted and the workspace is reset via git.
    """
    import subprocess

    bench_dir = Path.home() / ".klat" / "bench"
    config_file = bench_dir / "config.json"
    active_version = None

    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                active_version = cfg.get("active_version")
        except Exception:
            pass

    if not active_version:
        klat.log("Error: No active benchmark version configured. Run /bench select [name] [number] first.")
        return None

    tasks_dir = bench_dir / active_version / "tasks"
    if not tasks_dir.is_dir():
        klat.log(f"Error: Tasks directory not found: {tasks_dir}")
        return None

    # Collect tasks that have a 'sort' field
    ordered_tasks: list[tuple[int, str]] = []
    for task_file in tasks_dir.glob("*.json"):
        try:
            with open(task_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            sort_val = data.get("sort")
            if sort_val is not None:
                ordered_tasks.append((int(sort_val), task_file.stem))
        except Exception:
            pass

    if not ordered_tasks:
        klat.log("Error: No tasks with a 'sort' field found in the active benchmark.")
        klat.ui.print_dim("Run 'uv run klat-bench/add_sort_fields.py' to assign sort order to tasks.")
        return None

    ordered_tasks.sort(key=lambda x: x[0])
    total = len(ordered_tasks)

    klat.ui.print_accent(f"Running all {total} tasks in order:")
    for sort_val, tid in ordered_tasks:
        klat.ui.print_dim(f"  [{sort_val:>2}] {tid}")

    last_agent = agent
    for idx, (sort_val, tid) in enumerate(ordered_tasks, start=1):
        sep = "=" * 60
        klat.ui.print_accent(sep)
        klat.ui.print_accent(f"[{idx}/{total}] Starting: {tid}  (difficulty {sort_val})")
        klat.ui.print_accent(sep)

        last_agent = _bench_start(tid, last_agent)
        # (finalization + cleanup + 2s sleep happens inside _bench_start)

    klat.ui.print_accent("All benchmark tasks completed!")
    return last_agent


def _bench_finalize(agent: Any, task_id: str, task_results_dir: Path, backup_dir: Path) -> None:
    """Finalize bench telemetry after the agent completes a task.

    - Replays file operations from tool_calls to produce simulated before/after content.
    - Writes physical before/ and after/ directory trees.
    - Appends transcript and history to the telemetry JSON.
    - Cleans up active blacklist/allowlist files.
    """
    from src import sessions
    from src.agent import KlatAgent

    log_path = task_results_dir / "telemetry.json"
    if not log_path.exists():
        klat.log("Warning: Telemetry log not found; nothing to finalize.")
        return

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            log_data = json.load(f)
    except Exception as e:
        klat.log(f"Error reading telemetry log for finalization: {e}")
        return

    # --- Resolve history from agent ---
    active_agent = agent if agent else KlatAgent.active_instance
    history: list = []
    backend = log_data.get("backend", "openai-compat")
    if active_agent:
        history = (
            active_agent._gemini_history
            if backend == "gemini"
            else active_agent._openai_messages
        )

    # --- Simulate file changes to produce before/after ---
    exported_tool_calls = log_data.get("tool_calls", [])
    simulated_files: dict[str, str | None] = {}
    files_modified: set[str] = set(log_data.get("files_modified") or [])

    def _resolve_rel(path_str: str) -> Path:
        p = Path(path_str).expanduser()
        if p.is_absolute():
            try:
                return p.relative_to(Path.cwd())
            except ValueError:
                return Path(p.name)
        return p

    def _bk_read(rel: Path) -> str:
        bk = backup_dir / rel
        return bk.read_text(encoding="utf-8") if bk.exists() else ""

    for tc in exported_tool_calls:
        name = tc.get("name", "")
        args = tc.get("args") or {}

        if name == "write_file":
            path_arg = args.get("path")
            if path_arg:
                rel = _resolve_rel(path_arg)
                files_modified.add(str(rel))
                simulated_files[str(rel)] = args.get("content", "")

        elif name == "patch_file":
            path_arg = args.get("path")
            if path_arg:
                rel = _resolve_rel(path_arg)
                files_modified.add(str(rel))
                if str(rel) not in simulated_files:
                    simulated_files[str(rel)] = _bk_read(rel)
                lines = simulated_files[str(rel)].splitlines(keepends=True)
                s = max(0, int(args.get("start_line", 1)) - 1)
                e = min(len(lines), int(args.get("end_line", s + 1)))
                nc = args.get("new_content", "")
                if lines and lines[0].endswith("\n") and not nc.endswith("\n"):
                    nc += "\n"
                lines[s:e] = nc.splitlines(keepends=True)
                simulated_files[str(rel)] = "".join(lines)

        elif name == "insert_lines":
            path_arg = args.get("path")
            if path_arg:
                rel = _resolve_rel(path_arg)
                files_modified.add(str(rel))
                if str(rel) not in simulated_files:
                    simulated_files[str(rel)] = _bk_read(rel)
                lines = simulated_files[str(rel)].splitlines(keepends=True)
                nc = args.get("content", "")
                if not nc.endswith("\n"):
                    nc += "\n"
                idx = max(0, min(len(lines), int(args.get("after_line", 0))))
                lines.insert(idx, nc)
                simulated_files[str(rel)] = "".join(lines)

        elif name == "replace_in_file":
            path_arg = args.get("path")
            if path_arg:
                rel = _resolve_rel(path_arg)
                files_modified.add(str(rel))
                if str(rel) not in simulated_files:
                    simulated_files[str(rel)] = _bk_read(rel)
                old_t = args.get("old_text", "")
                new_t = args.get("new_text", "")
                cnt = int(args.get("count", 1))
                content = simulated_files[str(rel)]
                simulated_files[str(rel)] = (
                    content.replace(old_t, new_t) if cnt == -1
                    else content.replace(old_t, new_t, cnt)
                )

        elif name == "delete_file":
            path_arg = args.get("path")
            if path_arg:
                rel = _resolve_rel(path_arg)
                files_modified.add(str(rel))
                simulated_files[str(rel)] = None

        elif name == "move_file":
            src_arg, dst_arg = args.get("source"), args.get("destination")
            if src_arg and dst_arg:
                src_rel, dst_rel = _resolve_rel(src_arg), _resolve_rel(dst_arg)
                files_modified.update([str(src_rel), str(dst_rel)])
                src_content = simulated_files.get(str(src_rel), _bk_read(src_rel))
                simulated_files[str(dst_rel)] = src_content
                simulated_files[str(src_rel)] = None

        elif name == "copy_file":
            src_arg, dst_arg = args.get("source"), args.get("destination")
            if src_arg and dst_arg:
                src_rel, dst_rel = _resolve_rel(src_arg), _resolve_rel(dst_arg)
                files_modified.add(str(dst_rel))
                simulated_files[str(dst_rel)] = simulated_files.get(
                    str(src_rel), _bk_read(src_rel)
                )

    # --- Write before/after physical files ---
    before_dir = task_results_dir / "before"
    after_dir = task_results_dir / "after"
    for _d in (before_dir, after_dir):
        if _d.exists():
            shutil.rmtree(_d)
        _d.mkdir(parents=True, exist_ok=True)

    file_changes: dict[str, dict] = {}
    for rel_str in sorted(files_modified):
        bk = backup_dir / rel_str
        before_content = bk.read_text(encoding="utf-8") if (bk.exists() and bk.is_file()) else None
        after_content = simulated_files.get(rel_str)
        file_changes[rel_str] = {"before": before_content, "after": after_content}

        if before_content is not None:
            bd = before_dir / rel_str
            bd.parent.mkdir(parents=True, exist_ok=True)
            bd.write_text(before_content, encoding="utf-8")
        if after_content is not None:
            ad = after_dir / rel_str
            ad.parent.mkdir(parents=True, exist_ok=True)
            ad.write_text(after_content, encoding="utf-8")

    # --- Serialize history ---
    serializable_history: list = []
    for item in history:
        if hasattr(item, "model_dump"):
            try:
                serializable_history.append(item.model_dump())
            except Exception:
                serializable_history.append(str(item))
        else:
            serializable_history.append(item)

    # --- Write final telemetry ---
    log_data["files_modified"] = sorted(files_modified)
    log_data["file_changes"] = file_changes
    log_data["transcript"] = sessions.get_transcript()
    log_data["history"] = serializable_history

    try:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2)
        klat.ui.print_accent(f"Telemetry finalized: {log_path}")
    except Exception as e:
        klat.log(f"Error writing final telemetry: {e}")

    # --- Clean up sandbox control files ---
    for _cleanup in (
        Path.home() / ".klat" / "bench" / "active_blacklist.json",
        Path.home() / ".klat" / "bench" / "active_allowlist.json",
    ):
        if _cleanup.exists():
            try:
                _cleanup.unlink()
            except Exception:
                pass

    klat.ui.print_accent(f"Benchmark task '{task_id}' completed.")


def suggest_bench(remainder: str, document: Any = None) -> str | None:
    """
    Suggest subcommands, names/versions, or task IDs for Klat Benchmarking operations:
    - /bench create [name] [num]
    - /bench select [name] [num]
    - /bench start [task_id]
    - /bench clean
    """
    if " " not in remainder:
        for sc in ["create", "select", "start", "clean"]:
            if sc.startswith(remainder) and sc != remainder:
                return sc[len(remainder):]
        return None

    # Parse subcommand and subcommand argument
    parts = remainder.split(None, 1)
    subcmd = parts[0].lower()
    sub_arg = parts[1] if len(parts) > 1 else ""

    if subcmd in ("select", "create"):
        sub_parts = sub_arg.split()
        # If we are completing the benchmark name
        if len(sub_parts) == 0 or (len(sub_parts) == 1 and not sub_arg.endswith(" ")):
            name_prefix = sub_parts[0] if sub_parts else ""
            names = _get_benchmark_names()
            for name in names:
                if name.startswith(name_prefix) and name != name_prefix:
                    return name[len(name_prefix):]
        # If we are completing the benchmark version number
        elif len(sub_parts) == 1 or (len(sub_parts) == 2 and not sub_arg.endswith(" ")):
            name = sub_parts[0]
            num_prefix = sub_parts[1] if len(sub_parts) > 1 else ""
            nums = _get_benchmark_nums(name)
            for num in nums:
                if num.startswith(num_prefix) and num != num_prefix:
                    return num[len(num_prefix):]
        return None

    if subcmd == "start":
        tasks = _get_benchmark_tasks()
        for task in tasks:
            if task.startswith(sub_arg) and task != sub_arg:
                return task[len(sub_arg):]
        return None

    return None

def _get_benchmark_names() -> list[str]:
    bench_dir = Path.home() / ".klat" / "bench"
    if not bench_dir.is_dir():
        return []
    try:
        names = set()
        for entry in bench_dir.iterdir():
            if entry.is_dir() and entry.name not in ("active_backup", "backup"):
                name, _, _ = entry.name.rpartition('-')
                if name:
                    names.add(name)
                else:
                    names.add(entry.name)
        return sorted(list(names))
    except Exception:
        return []

def _get_benchmark_nums(name: str) -> list[str]:
    bench_dir = Path.home() / ".klat" / "bench"
    if not bench_dir.is_dir():
        return []
    try:
        nums = []
        for entry in bench_dir.iterdir():
            if entry.is_dir() and entry.name not in ("active_backup", "backup"):
                b_name, _, b_num = entry.name.rpartition('-')
                if b_name == name and b_num:
                    nums.append(b_num)
        return sorted(nums)
    except Exception:
        return []

def _get_benchmark_tasks() -> list[str]:
    bench_dir = Path.home() / ".klat" / "bench"
    config_file = bench_dir / "config.json"
    if not config_file.exists():
        return []
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            active_version = cfg.get("active_version")
        if not active_version:
            return []
        tasks_dir = bench_dir / active_version / "tasks"
        if not tasks_dir.is_dir():
            return []
        tasks = []
        for entry in tasks_dir.iterdir():
            if entry.is_file() and entry.suffix == ".json":
                tasks.append(entry.stem)
        return sorted(tasks)
    except Exception:
        return []


