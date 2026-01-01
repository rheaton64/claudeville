"""
Shared files management for ClaudeVille (engine).

Copies location-based shared files into an agent's ./shared/ directory
before a turn, and syncs them back out afterward.
"""

from pathlib import Path
import logging
import re
import shutil


logger = logging.getLogger(__name__)


# Location to shared directories mapping
LOCATION_SHARED_DIRS: dict[str, list[str]] = {
    "town_square": ["town_square", "bulletin_board"],
    "workshop": ["workshop"],
    "library": ["library"],
    "residential": ["residential"],
    "garden": ["garden"],
    "riverbank": ["riverbank"],
}


def ensure_agent_directory(agent_name: str, village_root: Path | str) -> Path:
    """
    Create an agent's directory structure if it doesn't exist.

    Returns the agent's root directory path.
    """
    root = Path(village_root)
    agent_dir = root / "agents" / str(agent_name).lower()

    directories = [
        agent_dir / "home",
        agent_dir / "workspace",
        agent_dir / "journal",
        agent_dir / "dreams",
        agent_dir / "memories",
        agent_dir / "inbox",
        agent_dir / "outbox",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    return agent_dir


def ensure_shared_directories(village_root: Path | str) -> None:
    """Ensure the shared directory structure exists."""
    root = Path(village_root)
    shared_root = root / "shared"
    shared_root.mkdir(parents=True, exist_ok=True)

    subdirs = {name for names in LOCATION_SHARED_DIRS.values() for name in names}
    for subdir in sorted(subdirs):
        (shared_root / subdir).mkdir(parents=True, exist_ok=True)


def get_shared_dirs_for_location(location: str) -> list[str]:
    """Get list of shared directory names accessible from a location."""
    return LOCATION_SHARED_DIRS.get(location, [])


def sync_shared_files_in(
    agent_dir: Path,
    location: str,
    master_dir: Path,
) -> list[str]:
    """
    Copy shared files INTO agent's directory before their turn.

    Returns a list of relative file paths copied (for context prompt).
    """
    master_dir.mkdir(parents=True, exist_ok=True)
    shared_dir = agent_dir / "shared"

    if shared_dir.exists():
        shutil.rmtree(shared_dir)
    shared_dir.mkdir(exist_ok=True)

    copied_files: list[str] = []
    for subdir in get_shared_dirs_for_location(location):
        src = master_dir / subdir
        dst = shared_dir / subdir

        if src.exists() and src.is_dir():
            shutil.copytree(src, dst)

            for f in dst.rglob("*"):
                if f.is_file():
                    rel_path = f.relative_to(agent_dir)
                    copied_files.append(str(rel_path))

    if copied_files:
        logger.debug(
            "sync_shared_files_in | location=%s | files=%d",
            location,
            len(copied_files),
        )

    return sorted(copied_files)


def sync_shared_files_out(
    agent_dir: Path,
    location: str,
    master_dir: Path,
) -> None:
    """
    Copy modified shared files FROM agent's directory back to master.

    Uses the location from turn start, not current location.
    """
    shared_dir = agent_dir / "shared"
    if not shared_dir.exists():
        return

    files_synced = 0
    for subdir in get_shared_dirs_for_location(location):
        src = shared_dir / subdir
        dst = master_dir / subdir

        if src.exists() and src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)

            for f in src.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(src)
                    target = dst / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, target)
                    files_synced += 1

    if shared_dir.exists():
        shutil.rmtree(shared_dir)

    if files_synced:
        logger.debug(
            "sync_shared_files_out | location=%s | files=%d",
            location,
            files_synced,
        )


def get_shared_file_list(agent_dir: Path) -> list[str]:
    """
    Get list of available shared files in agent's directory.
    """
    shared_dir = agent_dir / "shared"
    if not shared_dir.exists():
        return []

    files = []
    for f in shared_dir.rglob("*"):
        if f.is_file():
            rel_path = f.relative_to(agent_dir)
            files.append(str(rel_path))

    return sorted(files)


def ensure_description_files(
    village_root: Path | str,
    location_descriptions: dict[str, str],
) -> None:
    """
    Create description.md files for each location if they don't exist.

    These files contain the location descriptions that appear in agent prompts.
    Agents can edit these files to collaboratively shape how locations are described.
    """
    root = Path(village_root)
    shared_dir = root / "shared"

    for location_id, description in location_descriptions.items():
        desc_file = shared_dir / location_id / "description.md"
        if not desc_file.exists():
            desc_file.parent.mkdir(parents=True, exist_ok=True)
            content = f"""<!-- This is what you see when you're in this location.
Feel free to edit/add to it as the village grows! -->

{description}
"""
            desc_file.write_text(content)
            logger.debug(
                "Created description.md for location=%s",
                location_id,
            )


def read_location_description(
    village_root: Path | str,
    location_id: str,
) -> str | None:
    """
    Read location description from shared file, stripping HTML comments.

    Returns None if file doesn't exist or is empty after stripping comments.
    Falls back to Location.description in calling code.
    """
    root = Path(village_root)
    desc_file = root / "shared" / location_id / "description.md"

    if not desc_file.exists():
        return None

    content = desc_file.read_text().strip()
    # Strip HTML comments
    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL).strip()

    return content if content else None
