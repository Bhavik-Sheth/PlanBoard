# planboard/watcher/watcher_manager.py
import os
import sys
import subprocess
import time
import json
from pathlib import Path
from typing import Optional

class WatcherManager:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.hb_path = self.project_path / ".watcher_heartbeat"
        self.proc: Optional[subprocess.Popen] = None
        self.restart_count = 0
        self.permanently_failed = False

    def start(self):
        """Start watcher subprocess. Called on /init or /run."""
        if self.permanently_failed:
            return
        
        # Check if already running (and alive)
        if self.health_check() == "alive" and self.is_process_running():
            return

        # Stop existing if dead/stale but process still exists
        self.stop()

        # Start subprocess
        cmd = [sys.executable, "-m", "planboard.watcher.architecture_watcher", str(self.project_path)]
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(self.project_path.parent)
            )
            # Reset restart count when started fresh
            self.restart_count = 0
        except Exception as e:
            # Mark failed
            self.permanently_failed = True

    def stop(self):
        """Terminate watcher subprocess cleanly."""
        pid = None
        if self.hb_path.exists():
            try:
                data = json.loads(self.hb_path.read_text(encoding="utf-8"))
                pid = data.get("pid")
            except Exception:
                pass
                
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
            
        if pid:
            try:
                import signal
                os.kill(pid, signal.SIGTERM)
                # wait a bit
                time.sleep(0.5)
                # check if still alive, then SIGKILL
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass
                
        # Clean up heartbeat file
        if self.hb_path.exists():
            try:
                self.hb_path.unlink()
            except Exception:
                pass

    def is_process_running(self) -> bool:
        if self.proc and self.proc.poll() is None:
            return True
        # Also check PID from heartbeat file
        if self.hb_path.exists():
            try:
                data = json.loads(self.hb_path.read_text(encoding="utf-8"))
                pid = data.get("pid")
                if pid:
                    os.kill(pid, 0)
                    return True
            except Exception:
                pass
        return False

    def health_check(self) -> str:
        """
        Returns "alive" | "stale" | "dead".
        Reads heartbeat file. If last_update > 10s ago → "stale".
        If file missing → "dead".
        """
        if not self.hb_path.exists():
            return "dead"
        
        try:
            data = json.loads(self.hb_path.read_text(encoding="utf-8"))
            timestamp = data.get("timestamp", 0.0)
            if time.time() - timestamp > 10.0:
                return "stale"
            return "alive"
        except Exception:
            return "dead"

    def restart_if_dead(self):
        """Called by Orchestrator on every /run and /approve. Auto-restarts dead watcher."""
        if self.permanently_failed:
            return

        health = self.health_check()
        if health == "dead" or not self.is_process_running():
            if self.restart_count >= 3:
                self.permanently_failed = True
                return
            
            self.restart_count += 1
            self.start()

    def get_status_for_tui(self) -> dict:
        """
        Returns {"symbol": "●", "color": "green/yellow/red/grey", "label": "Live/..."}
        """
        if self.permanently_failed:
            return {"symbol": "●", "color": "grey", "label": "Unavailable"}
        
        health = self.health_check()
        if health == "dead":
            return {"symbol": "●", "color": "red", "label": "Watcher crashed"}
        
        # Read heartbeat data
        try:
            data = json.loads(self.hb_path.read_text(encoding="utf-8"))
            status = data.get("status", "idle")
            
            if status == "running":
                return {"symbol": "●", "color": "yellow", "label": "Regenerating..."}
            
            if status == "error":
                return {"symbol": "●", "color": "yellow", "label": "Stale (Regen Failed)"}

            if health == "stale":
                return {"symbol": "●", "color": "yellow", "label": "Stale"}
                
            return {"symbol": "●", "color": "green", "label": "Live"}
        except Exception:
            return {"symbol": "●", "color": "red", "label": "Watcher crashed"}
