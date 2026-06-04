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
    - /bench start [task_id]
    - /bench submit
    """
    parts = args_str.strip().split(None, 1)
    if not parts:
        klat.ui.print_accent("Klat Bench Command Interface")
        print("  /bench create [name] [num]       Initialize a new benchmark version structure")
        print("  /bench select [name] [num]       Switch the active benchmark workspace")
        print("  /bench start [task_id]           Load a task and start execution")
        print("  /bench submit                    Submit completed task for evaluation")
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
    elif subcmd == "submit":
        _bench_submit(agent)
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

def _bench_start(task_id: str, agent: Any) -> Any:
    from src.agent import KlatAgent
    from src.config import ensure_env
    from src import sessions
    
    if not task_id:
        klat.ui.print_accent("Usage: /bench start [task_id]")
        return None
        
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
            
    # 2.5 Save active blacklist if present
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
            
    # 3. Reset/Clear active Klat session and start a new session named bench_<task_id>
    sessions.clear_transcript()
    sessions.set_active_session_id(f"bench_{task_id}")
    
    # Re-initialize the agent
    project, location = ensure_env()
    new_agent = KlatAgent(project, location)
    new_agent.reset()
    
    klat.ui.print_accent(f"Session reset. Session ID: bench_{task_id}")
    klat.ui.print_accent(f"Injecting organic prompt: {organic_prompt}")
    
    # Trigger first chat turn on the new agent
    new_agent.chat(organic_prompt)
    
    return new_agent

def _bench_submit(agent: Any) -> None:
    from src import sessions
    from src.agent import KlatAgent
    
    session_id = sessions.get_active_session_id()
    
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
        klat.log("Error: No active benchmark version configured. Run /bench version [name] [number] first.")
        return
        
    results_dir = bench_dir / active_version / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    active_agent = agent if agent else KlatAgent.active_instance
    if not active_agent:
        # Load from disk
        session_data = sessions.load_session(session_id)
        if not session_data:
            klat.log("Error: Active session data could not be found.")
            return
        history = session_data.get("history", [])
        backend = session_data.get("backend", "openai-compat")
        provider = session_data.get("provider", "openai")
        model = session_data.get("model", "")
        reasoning = session_data.get("reasoning", "none")
    else:
        from src.config import current_provider, current_model, current_reasoning
        from src.providers import get_provider
        provider = current_provider()
        model = current_model()
        reasoning = current_reasoning()
        p = get_provider(provider)
        backend = "gemini" if p["backend"] == "gemini" else "openai-compat"
        history = active_agent._gemini_history if backend == "gemini" else active_agent._openai_messages
        
    # Helper to get field from part (supporting both object attribute and dict key)
    def get_field(obj, name):
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)
        
    # Extract ALL tool calls along with their results from history
    exported_tool_calls = []
    if backend == "gemini":
        pending_calls = []
        for content in history:
            role = get_field(content, "role")
            parts = get_field(content, "parts") or []
            if role == "model":
                for part in parts:
                    fcall = get_field(part, "function_call") or get_field(part, "functionCall")
                    if fcall:
                        name = get_field(fcall, "name")
                        args = get_field(fcall, "args") or {}
                        if hasattr(args, "model_dump"):
                            args = args.model_dump()
                        elif not isinstance(args, dict):
                            args = dict(args) if args else {}
                        call_info = {"name": name, "args": args, "result": None}
                        exported_tool_calls.append(call_info)
                        pending_calls.append(call_info)
            elif role == "user":
                for part in parts:
                    fresp = get_field(part, "function_response") or get_field(part, "functionResponse")
                    if fresp:
                        name = get_field(fresp, "name")
                        resp = get_field(fresp, "response") or {}
                        result = get_field(resp, "result") if isinstance(resp, dict) else getattr(resp, "result", None)
                        for call in pending_calls:
                            if call["name"] == name and call["result"] is None:
                                call["result"] = result
                                pending_calls.remove(call)
                                break
    else:
        # openai-compat
        calls_by_id = {}
        for msg in history:
            role = get_field(msg, "role")
            if role == "assistant":
                tcalls = get_field(msg, "tool_calls") or []
                for tc in tcalls:
                    tc_id = get_field(tc, "id")
                    func = get_field(tc, "function") or {}
                    name = get_field(func, "name")
                    args_raw = get_field(func, "arguments") or "{}"
                    if isinstance(args_raw, str):
                        try:
                            args = json.loads(args_raw)
                        except Exception:
                            args = {}
                    elif isinstance(args_raw, dict):
                        args = args_raw
                    else:
                        args = {}
                    call_info = {"name": name, "args": args, "result": None}
                    exported_tool_calls.append(call_info)
                    if tc_id:
                        calls_by_id[tc_id] = call_info
            elif role == "tool":
                tc_id = get_field(msg, "tool_call_id")
                content = get_field(msg, "content")
                if tc_id and tc_id in calls_by_id:
                    calls_by_id[tc_id]["result"] = content
                    
    files_read = set()
    files_modified = set()
    simulated_files = {}
    backup_dir = Path.home() / ".klat" / "bench" / "active_backup"
    
    def resolve_rel(path_str):
        p = Path(path_str).expanduser()
        if p.is_absolute():
            try:
                return p.relative_to(Path.cwd())
            except ValueError:
                return Path(p.name)
        return p
        
    for tc in exported_tool_calls:
        name = tc["name"]
        args = tc["args"]
        
        if name == "read_file":
            path_arg = args.get("path")
            if isinstance(path_arg, list):
                for p in path_arg:
                    files_read.add(str(resolve_rel(p)))
            elif path_arg:
                files_read.add(str(resolve_rel(path_arg)))
                
        elif name == "write_file":
            path_arg = args.get("path")
            if path_arg:
                rel = resolve_rel(path_arg)
                files_modified.add(str(rel))
                simulated_files[str(rel)] = args.get("content", "")
                
        elif name == "patch_file":
            path_arg = args.get("path")
            if path_arg:
                rel = resolve_rel(path_arg)
                files_modified.add(str(rel))
                if str(rel) not in simulated_files:
                    backup_file = backup_dir / rel
                    if backup_file.exists():
                        simulated_files[str(rel)] = backup_file.read_text(encoding="utf-8")
                    else:
                        simulated_files[str(rel)] = ""
                content = simulated_files[str(rel)]
                lines = content.splitlines(keepends=True)
                start_line = int(args.get("start_line", 1))
                end_line = int(args.get("end_line", start_line))
                new_content = args.get("new_content", "")
                
                lo = max(0, start_line - 1)
                hi = min(len(lines), end_line)
                
                replacement = new_content
                if lines and lines[0].endswith("\n") and not replacement.endswith("\n"):
                    replacement += "\n"
                lines[lo:hi] = replacement.splitlines(keepends=True)
                simulated_files[str(rel)] = "".join(lines)
                
        elif name == "insert_lines":
            path_arg = args.get("path")
            if path_arg:
                rel = resolve_rel(path_arg)
                files_modified.add(str(rel))
                if str(rel) not in simulated_files:
                    backup_file = backup_dir / rel
                    if backup_file.exists():
                        simulated_files[str(rel)] = backup_file.read_text(encoding="utf-8")
                    else:
                        simulated_files[str(rel)] = ""
                content = simulated_files[str(rel)]
                lines = content.splitlines(keepends=True)
                after_line = int(args.get("after_line", 0))
                new_content = args.get("content", "")
                
                if not new_content.endswith("\n"):
                    new_content += "\n"
                idx = max(0, min(len(lines), after_line))
                lines.insert(idx, new_content)
                simulated_files[str(rel)] = "".join(lines)
                
        elif name == "replace_in_file":
            path_arg = args.get("path")
            if path_arg:
                rel = resolve_rel(path_arg)
                files_modified.add(str(rel))
                if str(rel) not in simulated_files:
                    backup_file = backup_dir / rel
                    if backup_file.exists():
                        simulated_files[str(rel)] = backup_file.read_text(encoding="utf-8")
                    else:
                        simulated_files[str(rel)] = ""
                content = simulated_files[str(rel)]
                old_text = args.get("old_text", "")
                new_text = args.get("new_text", "")
                count = int(args.get("count", 1))
                if count == -1:
                    simulated_files[str(rel)] = content.replace(old_text, new_text)
                else:
                    simulated_files[str(rel)] = content.replace(old_text, new_text, count)
                    
        elif name == "delete_file":
            path_arg = args.get("path")
            if path_arg:
                rel = resolve_rel(path_arg)
                files_modified.add(str(rel))
                if str(rel) in simulated_files:
                    del simulated_files[str(rel)]
                else:
                    simulated_files[str(rel)] = None
                    
        elif name == "move_file":
            src_arg = args.get("source")
            dst_arg = args.get("destination")
            if src_arg and dst_arg:
                src_rel = resolve_rel(src_arg)
                dst_rel = resolve_rel(dst_arg)
                files_modified.add(str(src_rel))
                files_modified.add(str(dst_rel))
                
                if str(src_rel) in simulated_files:
                    src_content = simulated_files[str(src_rel)]
                else:
                    backup_file = backup_dir / src_rel
                    if backup_file.exists():
                        src_content = backup_file.read_text(encoding="utf-8")
                    else:
                        src_content = ""
                simulated_files[str(dst_rel)] = src_content
                simulated_files[str(src_rel)] = None
                
        elif name == "copy_file":
            src_arg = args.get("source")
            dst_arg = args.get("destination")
            if src_arg and dst_arg:
                src_rel = resolve_rel(src_arg)
                dst_rel = resolve_rel(dst_arg)
                files_modified.add(str(dst_rel))
                
                if str(src_rel) in simulated_files:
                    src_content = simulated_files[str(src_rel)]
                else:
                    backup_file = backup_dir / src_rel
                    if backup_file.exists():
                        src_content = backup_file.read_text(encoding="utf-8")
                    else:
                        src_content = ""
                simulated_files[str(dst_rel)] = src_content
 
    klat.ui.print_accent("Auditing active session telemetry...")
    klat.ui.print_dim(f"  Session ID: {session_id}")
    klat.ui.print_dim(f"  Backend: {backend}")
    klat.ui.print_dim(f"  Model: {model}")
    klat.ui.print_dim(f"  Files Read: {len(files_read)}")
    klat.ui.print_dim(f"  Files Modified: {len(files_modified)}")
    
    # Export before/after versions of every modified file
    before_dir = results_dir / "before"
    after_dir = results_dir / "after"
    
    if before_dir.exists():
        shutil.rmtree(before_dir)
    if after_dir.exists():
        shutil.rmtree(after_dir)
        
    before_dir.mkdir(parents=True, exist_ok=True)
    after_dir.mkdir(parents=True, exist_ok=True)
    
    file_changes = {}
    klat.ui.print_accent(f"Writing verified file modifications (before/after) to results directory: {results_dir}")
    
    for rel_str in sorted(files_modified):
        backup_file = backup_dir / rel_str
        
        # Determine "before" content
        if backup_file.exists() and backup_file.is_file():
            try:
                before_content = backup_file.read_text(encoding="utf-8")
            except Exception:
                before_content = ""
        else:
            before_content = None
            
        # Determine "after" content
        after_content = simulated_files.get(rel_str)
        
        file_changes[rel_str] = {
            "before": before_content,
            "after": after_content
        }
        
        before_state = "exists" if before_content is not None else "new"
        after_state = "exists" if after_content is not None else "deleted"
        klat.ui.print_dim(f"  Modified file: {rel_str} (before: {before_state}, after: {after_state})")
        
        # Write physical copies
        if before_content is not None:
            before_dest = before_dir / rel_str
            before_dest.parent.mkdir(parents=True, exist_ok=True)
            before_dest.write_text(before_content, encoding="utf-8")
            
        if after_content is not None:
            after_dest = after_dir / rel_str
            after_dest.parent.mkdir(parents=True, exist_ok=True)
            after_dest.write_text(after_content, encoding="utf-8")
            
    serializable_history = []
    for item in history:
        if hasattr(item, "model_dump"):
            try:
                serializable_history.append(item.model_dump())
            except Exception:
                serializable_history.append(str(item))
        else:
            serializable_history.append(item)
            
    log_data = {
        "session_id": session_id,
        "provider": provider,
        "model": model,
        "reasoning": reasoning,
        "backend": backend,
        "files_read": list(files_read),
        "files_modified": list(files_modified),
        "tool_calls": exported_tool_calls,
        "file_changes": file_changes,
        "transcript": sessions.get_transcript(),
        "history": serializable_history
    }
    
    log_path = results_dir / "telemetry_log.json"
    try:
        with open(log_path, "w", encoding="utf-8") as lf:
            json.dump(log_data, lf, indent=2)
        klat.ui.print_accent(f"Evaluation telemetry log written to: {log_path}")
    except Exception as e:
        klat.log(f"Error writing telemetry log: {e}")
        
    # Clean up active blacklist file if it exists
    blacklist_file = Path.home() / ".klat" / "bench" / "active_blacklist.json"
    if blacklist_file.exists():
        try:
            blacklist_file.unlink()
        except Exception:
            pass
            
    klat.ui.print_accent("Benchmark submission completed successfully!")
