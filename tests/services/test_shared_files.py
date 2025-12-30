"""Tests for engine.services.shared_files module."""

import pytest
from pathlib import Path

from engine.services.shared_files import (
    LOCATION_SHARED_DIRS,
    ensure_agent_directory,
    ensure_description_files,
    ensure_shared_directories,
    get_shared_dirs_for_location,
    read_location_description,
    sync_shared_files_in,
    sync_shared_files_out,
    get_shared_file_list,
)


class TestLocationSharedDirs:
    """Tests for LOCATION_SHARED_DIRS mapping."""

    def test_town_square_has_shared_dirs(self):
        """Test town_square has shared directories."""
        dirs = LOCATION_SHARED_DIRS.get("town_square")

        assert dirs is not None
        assert "town_square" in dirs
        assert "bulletin_board" in dirs

    def test_workshop_has_shared_dir(self):
        """Test workshop has shared directory."""
        dirs = LOCATION_SHARED_DIRS.get("workshop")

        assert dirs is not None
        assert "workshop" in dirs

    def test_library_has_shared_dir(self):
        """Test library has shared directory."""
        dirs = LOCATION_SHARED_DIRS.get("library")

        assert dirs is not None
        assert "library" in dirs


class TestGetSharedDirsForLocation:
    """Tests for get_shared_dirs_for_location function."""

    def test_known_location(self):
        """Test getting shared dirs for known location."""
        dirs = get_shared_dirs_for_location("workshop")

        assert "workshop" in dirs

    def test_unknown_location(self):
        """Test getting shared dirs for unknown location returns empty."""
        dirs = get_shared_dirs_for_location("unknown_place")

        assert dirs == []

    def test_town_square_multiple_dirs(self):
        """Test town_square has multiple shared directories."""
        dirs = get_shared_dirs_for_location("town_square")

        assert len(dirs) >= 2


class TestEnsureAgentDirectory:
    """Tests for ensure_agent_directory function."""

    def test_creates_agent_directories(self, temp_village_dir: Path):
        """Test that agent directories are created."""
        agent_dir = ensure_agent_directory("Ember", temp_village_dir)

        assert agent_dir.exists()
        assert (agent_dir / "home").exists()
        assert (agent_dir / "workspace").exists()
        assert (agent_dir / "journal").exists()
        assert (agent_dir / "memories").exists()
        assert (agent_dir / "inbox").exists()
        assert (agent_dir / "outbox").exists()

    def test_agent_name_lowercased(self, temp_village_dir: Path):
        """Test agent name is lowercased in path."""
        agent_dir = ensure_agent_directory("Ember", temp_village_dir)

        assert "ember" in str(agent_dir)
        assert "Ember" not in str(agent_dir)

    def test_idempotent(self, temp_village_dir: Path):
        """Test calling multiple times is safe."""
        dir1 = ensure_agent_directory("Ember", temp_village_dir)
        dir2 = ensure_agent_directory("Ember", temp_village_dir)

        assert dir1 == dir2
        assert dir1.exists()


class TestEnsureSharedDirectories:
    """Tests for ensure_shared_directories function."""

    def test_creates_shared_root(self, temp_village_dir: Path):
        """Test shared root directory is created."""
        ensure_shared_directories(temp_village_dir)

        shared_root = temp_village_dir / "shared"
        assert shared_root.exists()

    def test_creates_subdirectories(self, temp_village_dir: Path):
        """Test shared subdirectories are created."""
        ensure_shared_directories(temp_village_dir)

        shared_root = temp_village_dir / "shared"
        assert (shared_root / "town_square").exists()
        assert (shared_root / "bulletin_board").exists()
        assert (shared_root / "workshop").exists()
        assert (shared_root / "library").exists()


class TestSyncSharedFilesIn:
    """Tests for sync_shared_files_in function."""

    def test_copies_files_to_agent(self, temp_village_dir: Path):
        """Test files are copied from master to agent directory."""
        # Setup
        ensure_shared_directories(temp_village_dir)
        agent_dir = ensure_agent_directory("Ember", temp_village_dir)
        master_dir = temp_village_dir / "shared"

        # Create a test file in the master
        test_file = master_dir / "workshop" / "test.txt"
        test_file.write_text("Hello from workshop!")

        # Sync
        copied = sync_shared_files_in(agent_dir, "workshop", master_dir)

        # Verify
        agent_file = agent_dir / "shared" / "workshop" / "test.txt"
        assert agent_file.exists()
        assert agent_file.read_text() == "Hello from workshop!"
        assert len(copied) == 1

    def test_returns_copied_file_list(self, temp_village_dir: Path):
        """Test returns list of copied file paths."""
        ensure_shared_directories(temp_village_dir)
        agent_dir = ensure_agent_directory("Ember", temp_village_dir)
        master_dir = temp_village_dir / "shared"

        # Create test files
        (master_dir / "workshop" / "file1.txt").write_text("1")
        (master_dir / "workshop" / "file2.txt").write_text("2")

        copied = sync_shared_files_in(agent_dir, "workshop", master_dir)

        assert len(copied) == 2
        assert any("file1.txt" in f for f in copied)
        assert any("file2.txt" in f for f in copied)

    def test_clears_existing_shared_dir(self, temp_village_dir: Path):
        """Test existing shared directory is cleared before sync."""
        ensure_shared_directories(temp_village_dir)
        agent_dir = ensure_agent_directory("Ember", temp_village_dir)
        master_dir = temp_village_dir / "shared"

        # Create a file that should be removed
        old_shared = agent_dir / "shared" / "old_file.txt"
        old_shared.parent.mkdir(parents=True, exist_ok=True)
        old_shared.write_text("old content")

        # Sync (should clear old file)
        sync_shared_files_in(agent_dir, "workshop", master_dir)

        assert not old_shared.exists()

    def test_unknown_location_syncs_nothing(self, temp_village_dir: Path):
        """Test syncing unknown location copies nothing."""
        ensure_shared_directories(temp_village_dir)
        agent_dir = ensure_agent_directory("Ember", temp_village_dir)
        master_dir = temp_village_dir / "shared"

        copied = sync_shared_files_in(agent_dir, "unknown_place", master_dir)

        assert copied == []


class TestSyncSharedFilesOut:
    """Tests for sync_shared_files_out function."""

    def test_copies_files_to_master(self, temp_village_dir: Path):
        """Test files are copied from agent to master directory."""
        ensure_shared_directories(temp_village_dir)
        agent_dir = ensure_agent_directory("Ember", temp_village_dir)
        master_dir = temp_village_dir / "shared"

        # Create a file in agent's shared directory
        agent_shared = agent_dir / "shared" / "workshop"
        agent_shared.mkdir(parents=True, exist_ok=True)
        (agent_shared / "agent_created.txt").write_text("Created by agent")

        # Sync out
        sync_shared_files_out(agent_dir, "workshop", master_dir)

        # Verify
        master_file = master_dir / "workshop" / "agent_created.txt"
        assert master_file.exists()
        assert master_file.read_text() == "Created by agent"

    def test_clears_agent_shared_after_sync(self, temp_village_dir: Path):
        """Test agent's shared directory is cleared after sync out."""
        ensure_shared_directories(temp_village_dir)
        agent_dir = ensure_agent_directory("Ember", temp_village_dir)
        master_dir = temp_village_dir / "shared"

        # Create a file in agent's shared directory
        agent_shared = agent_dir / "shared" / "workshop"
        agent_shared.mkdir(parents=True, exist_ok=True)
        (agent_shared / "test.txt").write_text("test")

        # Sync out
        sync_shared_files_out(agent_dir, "workshop", master_dir)

        # Agent's shared should be removed
        assert not (agent_dir / "shared").exists()

    def test_no_shared_dir_does_nothing(self, temp_village_dir: Path):
        """Test syncing when no shared dir exists does nothing."""
        agent_dir = ensure_agent_directory("Ember", temp_village_dir)
        master_dir = temp_village_dir / "shared"

        # Should not raise
        sync_shared_files_out(agent_dir, "workshop", master_dir)


class TestGetSharedFileList:
    """Tests for get_shared_file_list function."""

    def test_lists_files(self, temp_village_dir: Path):
        """Test listing files in shared directory."""
        agent_dir = ensure_agent_directory("Ember", temp_village_dir)

        # Create some files
        shared = agent_dir / "shared" / "workshop"
        shared.mkdir(parents=True, exist_ok=True)
        (shared / "file1.txt").write_text("1")
        (shared / "file2.txt").write_text("2")

        files = get_shared_file_list(agent_dir)

        assert len(files) == 2

    def test_empty_when_no_shared_dir(self, temp_village_dir: Path):
        """Test returns empty when no shared directory exists."""
        agent_dir = ensure_agent_directory("Ember", temp_village_dir)

        files = get_shared_file_list(agent_dir)

        assert files == []

    def test_lists_nested_files(self, temp_village_dir: Path):
        """Test listing nested files."""
        agent_dir = ensure_agent_directory("Ember", temp_village_dir)

        # Create nested structure
        nested = agent_dir / "shared" / "workshop" / "subdir"
        nested.mkdir(parents=True, exist_ok=True)
        (nested / "nested.txt").write_text("nested content")

        files = get_shared_file_list(agent_dir)

        assert len(files) == 1
        assert any("nested.txt" in f for f in files)


class TestEnsureDescriptionFiles:
    """Tests for ensure_description_files function."""

    def test_creates_description_files(self, temp_village_dir: Path):
        """Test description files are created for each location."""
        ensure_shared_directories(temp_village_dir)

        descriptions = {
            "workshop": "A cozy workshop.",
            "library": "A quiet library.",
        }
        ensure_description_files(temp_village_dir, descriptions)

        workshop_desc = temp_village_dir / "shared" / "workshop" / "description.md"
        library_desc = temp_village_dir / "shared" / "library" / "description.md"

        assert workshop_desc.exists()
        assert library_desc.exists()

    def test_includes_comment_in_file(self, temp_village_dir: Path):
        """Test description files include helpful comment."""
        ensure_shared_directories(temp_village_dir)

        descriptions = {"workshop": "A cozy workshop."}
        ensure_description_files(temp_village_dir, descriptions)

        content = (
            temp_village_dir / "shared" / "workshop" / "description.md"
        ).read_text()

        assert "<!--" in content
        assert "Feel free to edit" in content
        assert "A cozy workshop." in content

    def test_does_not_overwrite_existing(self, temp_village_dir: Path):
        """Test existing description files are not overwritten."""
        ensure_shared_directories(temp_village_dir)

        # Create an existing file
        workshop_dir = temp_village_dir / "shared" / "workshop"
        workshop_dir.mkdir(parents=True, exist_ok=True)
        desc_file = workshop_dir / "description.md"
        desc_file.write_text("Custom description by agents!")

        descriptions = {"workshop": "Default description."}
        ensure_description_files(temp_village_dir, descriptions)

        # Should preserve the existing content
        assert desc_file.read_text() == "Custom description by agents!"

    def test_creates_parent_directories(self, temp_village_dir: Path):
        """Test parent directories are created if needed."""
        # Don't call ensure_shared_directories first
        descriptions = {"new_location": "A brand new place."}
        ensure_description_files(temp_village_dir, descriptions)

        desc_file = temp_village_dir / "shared" / "new_location" / "description.md"
        assert desc_file.exists()


class TestReadLocationDescription:
    """Tests for read_location_description function."""

    def test_reads_description(self, temp_village_dir: Path):
        """Test reading description from file."""
        ensure_shared_directories(temp_village_dir)

        # Create a description file
        desc_file = temp_village_dir / "shared" / "workshop" / "description.md"
        desc_file.write_text("A wonderful workshop full of tools.")

        result = read_location_description(temp_village_dir, "workshop")

        assert result == "A wonderful workshop full of tools."

    def test_strips_html_comments(self, temp_village_dir: Path):
        """Test HTML comments are stripped from output."""
        ensure_shared_directories(temp_village_dir)

        content = """<!-- This is a comment -->

The actual description.

<!-- Another comment -->"""
        desc_file = temp_village_dir / "shared" / "workshop" / "description.md"
        desc_file.write_text(content)

        result = read_location_description(temp_village_dir, "workshop")

        assert result == "The actual description."
        assert "<!--" not in result

    def test_returns_none_for_missing_file(self, temp_village_dir: Path):
        """Test returns None when description file doesn't exist."""
        ensure_shared_directories(temp_village_dir)

        result = read_location_description(temp_village_dir, "workshop")

        assert result is None

    def test_returns_none_for_empty_file(self, temp_village_dir: Path):
        """Test returns None when file is empty after stripping."""
        ensure_shared_directories(temp_village_dir)

        # Create a file with only comments
        desc_file = temp_village_dir / "shared" / "workshop" / "description.md"
        desc_file.write_text("<!-- Only a comment -->")

        result = read_location_description(temp_village_dir, "workshop")

        assert result is None

    def test_strips_whitespace(self, temp_village_dir: Path):
        """Test whitespace is stripped from result."""
        ensure_shared_directories(temp_village_dir)

        desc_file = temp_village_dir / "shared" / "workshop" / "description.md"
        desc_file.write_text("  \n  A description with whitespace.  \n  ")

        result = read_location_description(temp_village_dir, "workshop")

        assert result == "A description with whitespace."
