import os
import pytest
from pathlib import Path
from planner.files.scaffold import scaffold_project, PLANNER_FILES, DIAGRAM_FILES
from planner.files.reader import read_planner_file, clear_cache, _FILE_CACHE
from planner.files.writer import write_planner_file, OverwriteRejectedError

def test_scaffold_project(tmp_path):
    """
    Test that scaffold_project creates the PLANNER directory structure 
    and all expected initial empty files.
    """
    # Run scaffolding on temporary path
    scaffold_project(base_path=tmp_path)
    
    planner_dir = tmp_path / "PLANNER"
    diagrams_dir = planner_dir / "ARCHITECTURE_DIAGRAMS"
    modules_dir = planner_dir / "MODULES"
    
    # Assert directories exist
    assert planner_dir.is_dir()
    assert diagrams_dir.is_dir()
    assert modules_dir.is_dir()
    
    # Assert PLANNER files exist and are empty
    for name in PLANNER_FILES:
        filepath = planner_dir / name
        assert filepath.is_file()
        assert filepath.stat().st_size == 0
        
    # Assert ARCHITECTURE_DIAGRAMS files exist and are empty
    for name in DIAGRAM_FILES:
        filepath = diagrams_dir / name
        assert filepath.is_file()
        assert filepath.stat().st_size == 0


def test_read_planner_file_caching(tmp_path):
    """
    Test that read_planner_file retrieves file contents and caches them correctly.
    """
    file_path = tmp_path / "test.md"
    file_path.write_text("initial content", encoding="utf-8")
    
    # Clear cache first
    clear_cache(file_path)
    
    # First read (uncached)
    content1 = read_planner_file(file_path)
    assert content1 == "initial content"
    
    # Verify that caching is taking place
    assert file_path in _FILE_CACHE
    
    # If we modify file on disk, uncached read gets the fresh content
    file_path.write_text("new content", encoding="utf-8")
    content_uncached = read_planner_file(file_path, use_cache=False)
    assert content_uncached == "new content"
    
    # Verify clear_cache removes it
    clear_cache(file_path)
    assert file_path not in _FILE_CACHE
    content_after_clear = read_planner_file(file_path)
    assert content_after_clear == "new content"


def test_write_planner_file_raw_idea(tmp_path):
    """
    Test that write_planner_file always appends for RawIdea.md.
    """
    raw_idea_path = tmp_path / "RawIdea.md"
    
    # Write initial content
    write_planner_file(raw_idea_path, "Idea step 1")
    assert raw_idea_path.read_text(encoding="utf-8") == "Idea step 1"
    
    # Append second piece
    write_planner_file(raw_idea_path, "Idea step 2")
    assert raw_idea_path.read_text(encoding="utf-8") == "Idea step 1\nIdea step 2"
    
    # Append with newline at end
    write_planner_file(raw_idea_path, "\nIdea step 3\n")
    assert raw_idea_path.read_text(encoding="utf-8") == "Idea step 1\nIdea step 2\nIdea step 3\n"
    
    # Append again, it shouldn't add double newline since it ended with newline
    write_planner_file(raw_idea_path, "Idea step 4")
    assert raw_idea_path.read_text(encoding="utf-8") == "Idea step 1\nIdea step 2\nIdea step 3\nIdea step 4"


def test_write_planner_file_overwrite_protection(tmp_path):
    """
    Test overwrite protection rules on other planner files.
    """
    prd_path = tmp_path / "PRD.md"
    
    # Initial write to empty file should succeed (size = 0)
    write_planner_file(prd_path, "Version 1")
    assert prd_path.read_text(encoding="utf-8") == "Version 1"
    
    # Attempting to write without force should raise OverwriteRejectedError
    with pytest.raises(OverwriteRejectedError):
        write_planner_file(prd_path, "Version 2")
        
    # Attempting to write with force=True should succeed
    write_planner_file(prd_path, "Version 2", force=True)
    assert prd_path.read_text(encoding="utf-8") == "Version 2"


def test_write_planner_file_confirm_callback(tmp_path):
    """
    Test custom confirm_callback logic.
    """
    prd_path = tmp_path / "PRD.md"
    write_planner_file(prd_path, "Original Content")
    
    # Mock confirm_callback rejecting overwrite
    def reject_callback(path):
        return False
        
    with pytest.raises(OverwriteRejectedError):
        write_planner_file(prd_path, "Rejected Content", confirm_callback=reject_callback)
    assert prd_path.read_text(encoding="utf-8") == "Original Content"
    
    # Mock confirm_callback accepting overwrite
    def accept_callback(path):
        return True
        
    write_planner_file(prd_path, "Accepted Content", confirm_callback=accept_callback)
    assert prd_path.read_text(encoding="utf-8") == "Accepted Content"
