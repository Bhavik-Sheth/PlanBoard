import sys
from pathlib import Path
from watchfiles import watch
from planner.agents.architecture_diagram_agent import generate_diagrams

def start_watcher(planner_dir_path: str) -> None:
    planner_dir = Path(planner_dir_path).resolve()
    if not planner_dir.exists():
        print(f"❌  PLANNER directory not found at: {planner_dir}. Run `planner init` first.", file=sys.stderr)
        sys.exit(1)
        
    print(f"👁️  Starting architecture diagram watcher on: {planner_dir}")
    
    # watch yields a set of change tuples: (change_type, file_path_str)
    for changes in watch(planner_dir):
        needs_regeneration = False
        changed_files = []
        for change_type, file_path_str in changes:
            file_path = Path(file_path_str).resolve()
            
            # The changed file MUST be directly under planner_dir
            if file_path.parent == planner_dir:
                # The file must be a Markdown file
                if file_path.suffix == ".md":
                    # Ignore Tracker.md and CLAUDE.md to prevent unnecessary updates
                    if file_path.name not in ("Tracker.md", "CLAUDE.md"):
                        needs_regeneration = True
                        changed_files.append(file_path.name)
                        
        if needs_regeneration:
            print(f"🔄  Detected change in top-level md files: {', '.join(changed_files)}. Regenerating diagrams...")
            try:
                generate_diagrams(str(planner_dir))
                print("✅  Diagrams updated successfully.")
            except Exception as e:
                print(f"❌  Error updating diagrams: {e}", file=sys.stderr)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else str(Path.cwd() / "PLANNER")
    try:
        start_watcher(path)
    except KeyboardInterrupt:
        print("\n👋  Watcher stopped.")
