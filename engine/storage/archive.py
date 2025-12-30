from pathlib import Path


class EventArchive:
    """Manages archival of old events to cold storage."""
    def __init__(self, village_root: Path):
        self.village_root = village_root
        self.archive_dir = village_root / "archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.active_log = village_root / "events.jsonl"

    def archive_events_before(self, tick: int) -> int:
        """
        Move events older than `tick` from active log to archive.
        Returns the number of events archived.
        """
        if not self.active_log.exists():
            return 0
        
        with open(self.active_log, "r") as f:
            lines = f.readlines()

        if not lines:
            return 0

        import json
        keep_lines = []
        archive_lines = []

        for line in lines:
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("tick", 0) < tick:
                archive_lines.append(line)
            else:
                keep_lines.append(line)

        if not archive_lines:
            return 0

        first_tick = json.loads(archive_lines[0])["tick"]
        last_tick = json.loads(archive_lines[-1])["tick"]
        archive_path = self.archive_dir / f"events_{first_tick}_{last_tick}.jsonl"

        with open(archive_path, "a") as f:
            f.writelines(archive_lines)

        with open(self.active_log, "w") as f:
            f.writelines(keep_lines)

        return len(archive_lines)

    def get_archive_ranges(self) -> list[tuple[int, int]]:
        """Get list of (start_tick, end_tick) ranges for all archived files."""
        ranges = []
        for path in self.archive_dir.glob("events_*_*.jsonl"):
            parts = path.stem.split("_")
            if len(parts) == 3:
                ranges.append((int(parts[1]), int(parts[2])))
        return sorted(ranges)

    def load_archived_events(self, start_tick: int, end_tick: int) -> list[str]:
        """Load events from archived file within the given tick range. Returns raw JSON strings."""
        import json
        results = []
        for path in self.archive_dir.glob("events_*_*.jsonl"):
            parts = path.stem.split("_")
            if len(parts) != 3:
                continue
            start, end = int(parts[1]), int(parts[2])
            if start <= end_tick and end >= start_tick:
                with open(path, "r") as f:
                    for line in f:
                        if line.strip():
                            event = json.loads(line)
                            if start_tick <= event.get("tick", 0) <= end_tick:
                                results.append(line)
        return results
        
        