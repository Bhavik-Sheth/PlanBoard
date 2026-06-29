# planner/watcher/heartbeat.py
import json
import os
import time
from pathlib import Path

def write_heartbeat(project_path: Path, status: str, last_regen: float = None):
    hb_path = project_path / ".watcher_heartbeat"
    
    # Try reading the existing heartbeat to keep the last_regen if not passed
    if last_regen is None:
        try:
            if hb_path.exists():
                data = json.loads(hb_path.read_text(encoding="utf-8"))
                last_regen = data.get("last_regen", 0.0)
        except Exception:
            pass
            
    if last_regen is None:
        last_regen = 0.0
        
    data = {
        "pid": os.getpid(),
        "last_regen": last_regen,
        "status": status,
        "timestamp": time.time()
    }
    try:
        hb_path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass

def delete_heartbeat(project_path: Path):
    hb_path = project_path / ".watcher_heartbeat"
    if hb_path.exists():
        try:
            hb_path.unlink()
        except Exception:
            pass
