"""Tests for engine.services.dreams module."""

import pytest
from pathlib import Path

from engine.services.dreams import append_dream, get_unseen_dreams, _format_dream_entry, _read_dream_entry


class TestAppendDream:
    """Tests for append_dream function."""

    def test_creates_dream_file(self, temp_village_dir: Path):
        """Test dream file is created."""
        path = append_dream(
            agent_name="Ember",
            content="You dreamed of a beautiful garden.",
            tick=5,
            village_root=temp_village_dir,
        )

        assert path.exists()
        assert path.suffix == ".md"

    def test_dream_contains_tick_header(self, temp_village_dir: Path):
        """Test dream file has tick header."""
        path = append_dream(
            agent_name="Ember",
            content="A vision appeared.",
            tick=10,
            village_root=temp_village_dir,
        )

        content = path.read_text()
        assert content.startswith("[tick:10]")

    def test_dream_contains_formatted_content(self, temp_village_dir: Path):
        """Test dream content is formatted."""
        path = append_dream(
            agent_name="Ember",
            content="Stars aligned.",
            tick=5,
            village_root=temp_village_dir,
        )

        content = path.read_text()
        assert "[Dream]" in content
        assert "Stars aligned." in content
        assert "inspiration drifted" in content

    def test_creates_dreams_directory(self, temp_village_dir: Path):
        """Test dreams directory is created."""
        append_dream(
            agent_name="Sage",
            content="A quiet thought.",
            tick=1,
            village_root=temp_village_dir,
        )

        dreams_dir = temp_village_dir / "agents" / "sage" / "dreams"
        assert dreams_dir.exists()

    def test_agent_name_lowercased(self, temp_village_dir: Path):
        """Test agent directory uses lowercase name."""
        append_dream(
            agent_name="EMBER",
            content="Test",
            tick=1,
            village_root=temp_village_dir,
        )

        assert (temp_village_dir / "agents" / "ember" / "dreams").exists()


class TestGetUnseenDreams:
    """Tests for get_unseen_dreams function."""

    def test_no_dreams_dir_returns_empty(self, temp_village_dir: Path):
        """Test returns empty when no dreams directory."""
        agent_dir = temp_village_dir / "agents" / "ember"
        agent_dir.mkdir(parents=True)

        result = get_unseen_dreams(agent_dir, last_active_tick=0)

        assert result == []

    def test_returns_dreams_after_tick(self, temp_village_dir: Path):
        """Test returns dreams with tick > last_active_tick."""
        # Create dreams at different ticks
        append_dream("Ember", "Dream 1", tick=5, village_root=temp_village_dir)
        append_dream("Ember", "Dream 2", tick=10, village_root=temp_village_dir)
        append_dream("Ember", "Dream 3", tick=15, village_root=temp_village_dir)

        agent_dir = temp_village_dir / "agents" / "ember"
        result = get_unseen_dreams(agent_dir, last_active_tick=8)

        assert len(result) == 2  # Dreams at tick 10 and 15

    def test_excludes_dreams_at_or_before_tick(self, temp_village_dir: Path):
        """Test excludes dreams at or before last_active_tick."""
        append_dream("Ember", "Old dream", tick=5, village_root=temp_village_dir)
        append_dream("Ember", "New dream", tick=20, village_root=temp_village_dir)

        agent_dir = temp_village_dir / "agents" / "ember"
        result = get_unseen_dreams(agent_dir, last_active_tick=10)

        assert len(result) == 1
        assert "New dream" in result[0]

    def test_returns_formatted_content(self, temp_village_dir: Path):
        """Test returned dreams are formatted."""
        append_dream("Ember", "Starlight", tick=5, village_root=temp_village_dir)

        agent_dir = temp_village_dir / "agents" / "ember"
        result = get_unseen_dreams(agent_dir, last_active_tick=0)

        assert len(result) == 1
        assert "[Dream]" in result[0]
        assert "Starlight" in result[0]


class TestFormatDreamEntry:
    """Tests for _format_dream_entry helper."""

    def test_wraps_content(self):
        """Test content is wrapped with markers."""
        result = _format_dream_entry("Test content")

        assert "[Dream]" in result
        assert "Test content" in result
        assert "inspiration drifted" in result


class TestReadDreamEntry:
    """Tests for _read_dream_entry helper."""

    def test_parses_tick_header(self, tmp_path: Path):
        """Test parses tick from header."""
        dream_file = tmp_path / "dream.md"
        dream_file.write_text("[tick:42]\nSome content")

        tick, content = _read_dream_entry(dream_file)

        assert tick == 42
        assert content == "Some content"

    def test_no_header_returns_none_tick(self, tmp_path: Path):
        """Test returns None tick when no header."""
        dream_file = tmp_path / "dream.md"
        dream_file.write_text("Just content")

        tick, content = _read_dream_entry(dream_file)

        assert tick is None
        assert content == "Just content"

    def test_invalid_tick_returns_none(self, tmp_path: Path):
        """Test returns None for invalid tick value."""
        dream_file = tmp_path / "dream.md"
        dream_file.write_text("[tick:abc]\nContent")

        tick, content = _read_dream_entry(dream_file)

        assert tick is None
