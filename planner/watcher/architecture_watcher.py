# planner/watcher/architecture_watcher.py
import sys
import os
import time
import asyncio
from pathlib import Path
import json
from watchfiles import awatch

# Import generate_diagrams
from planner.agents.architecture_diagram_agent import generate_diagrams
from planner.watcher.heartbeat import write_heartbeat

DEBOUNCE_SECONDS = 0.8
_last_write_time = 0.0
_pending_regen = False

async def wait_for_lock_clear(project_path: Path):
    """Wait for .graph_running lock file to clear."""
    lock_file = project_path / ".graph_running"
    while lock_file.exists():
        await asyncio.sleep(1.0)
    # Wait an extra 2 seconds after lock clears to reduce rate limit collision
    await asyncio.sleep(2.0)

async def regenerate_all_diagrams(project_path: Path):
    """Regenerate architecture diagrams. Writes STALE header on failure."""
    write_heartbeat(project_path, "running")
    
    loop = asyncio.get_event_loop()
    try:
        # Run synchronous generate_diagrams in a thread pool to avoid blocking async loop
        await loop.run_in_executor(None, generate_diagrams, str(project_path))
        write_heartbeat(project_path, "idle", last_regen=time.time())
    except Exception as exc:
        # LLM failure or other error during generation
        write_heartbeat(project_path, "error")
        # Prepend STALE header to existing diagrams
        diagrams_dir = project_path / "ARCHITECTURE_DIAGRAMS"
        if diagrams_dir.exists():
            from datetime import datetime
            time_str = datetime.now().strftime("%H:%M")
            stale_header = f"[STALE — regeneration failed at {time_str}]\n\n"
            for diag_file in ["SystemArchitecture.md", "SystemDesign.md", "FolderStructure.md", "DataFlow.md"]:
                path = diagrams_dir / diag_file
                if path.exists():
                    try:
                        content = path.read_text(encoding="utf-8")
                        if not content.startswith("[STALE —"):
                            path.write_text(stale_header + content, encoding="utf-8")
                    except Exception:
                        pass

async def _debounced_regen(project_path: Path):
    global _last_write_time, _pending_regen
    while True:
        await asyncio.sleep(DEBOUNCE_SECONDS)
        if time.monotonic() - _last_write_time >= DEBOUNCE_SECONDS:
            break
    _pending_regen = False

    # Check lock file
    if (project_path / ".graph_running").exists():
        await wait_for_lock_clear(project_path)

    await regenerate_all_diagrams(project_path)

async def main(project_path_str: str):
    project_path = Path(project_path_str)
    
    # Initialize heartbeat
    write_heartbeat(project_path, "idle")
    
    # Start periodic heartbeat loop task
    async def heartbeat_loop():
        while True:
            await asyncio.sleep(5.0)
            try:
                # Read current status to preserve it
                status = "idle"
                hb_path = project_path / ".watcher_heartbeat"
                if hb_path.exists():
                    data = json.loads(hb_path.read_text(encoding="utf-8"))
                    status = data.get("status", "idle")
                write_heartbeat(project_path, status)
            except Exception:
                pass

    asyncio.create_task(heartbeat_loop())

    # Watchfiles main loop
    # We watch the PLANNER/ directory itself, but ignore changes in ARCHITECTURE_DIAGRAMS/
    # and ignore changes to the heartbeat/lock files.
    global _last_write_time, _pending_regen
    
    ignore_files = {".watcher_heartbeat", ".graph_running", ".state.json"}
    
    async for changes in awatch(project_path):
        # Filter changes
        relevant_change = False
        for change_type, filepath_str in changes:
            filepath = Path(filepath_str)
            # Ignore if inside ARCHITECTURE_DIAGRAMS/
            if "ARCHITECTURE_DIAGRAMS" in filepath.parts:
                continue
            # Ignore ignored files
            if filepath.name in ignore_files:
                continue
            # Ignore non-markdown files
            if filepath.suffix != ".md":
                continue
            
            relevant_change = True
            break
            
        if relevant_change:
            _last_write_time = time.monotonic()
            if not _pending_regen:
                _pending_regen = True
                asyncio.create_task(_debounced_regen(project_path))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    
    # Path to PLANNER directory passed as argument
    planner_dir = sys.argv[1]
    
    try:
        asyncio.run(main(planner_dir))
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception:
        # Ensure cleanup on unexpected exit
        try:
            hb_path = Path(planner_dir) / ".watcher_heartbeat"
            if hb_path.exists():
                hb_path.unlink()
        except Exception:
            pass
