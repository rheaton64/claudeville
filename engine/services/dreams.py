"""
Dream storage and retrieval for ClaudeVille (engine).

Dreams are stored separately from journals in an agent-specific dreams directory.
"""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path

from .shared_files import ensure_agent_directory


logger = logging.getLogger(__name__)

def append_dream(
    agent_name: str,
    content: str,
    tick: int,
    village_root: Path | str,
) -> Path:
    """
    Append a dream entry for an agent.

    Stores the dream in ./dreams/ with tick metadata for filtering.
    """
    agent_dir = ensure_agent_directory(agent_name, village_root)
    dreams_dir = agent_dir / "dreams"
    dreams_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    entry = _format_dream_entry(content)
    file_content = f"[tick:{tick}]\n{entry}"
    dream_file = dreams_dir / f"{timestamp}.md"

    with open(dream_file, "w") as f:
        f.write(file_content)

    logger.debug(
        "DREAM_APPEND | agent=%s | tick=%s | file=%s",
        agent_name,
        tick,
        dream_file.name,
    )
    return dream_file


def get_unseen_dreams(agent_dir: Path, last_active_tick: int) -> list[str]:
    """
    Return dreams with tick > last active tick.
    """
    dreams_dir = agent_dir / "dreams"
    if not dreams_dir.exists():
        return []

    unseen: list[str] = []

    for dream_file in sorted(dreams_dir.glob("*.md")):
        tick, content = _read_dream_entry(dream_file)
        if tick is None:
            continue
        if tick > last_active_tick:
            unseen.append(content)

    return unseen


def _format_dream_entry(content: str) -> str:
    return f"[Dream]\n{content}\n\n(A gentle inspiration drifted through your rest...)"


def _read_dream_entry(path: Path) -> tuple[int | None, str]:
    content = path.read_text()

    entry_tick = None
    entry_content = content
    if content.startswith("[tick:"):
        end_bracket = content.find("]")
        if end_bracket > 0:
            try:
                entry_tick = int(content[6:end_bracket])
                entry_content = content[end_bracket + 1 :].lstrip("\n")
            except ValueError:
                entry_tick = None

    return entry_tick, entry_content
