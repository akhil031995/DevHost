"""
Backup service — creates timestamped backups of the hosts file and vhosts config
before any modification. Also provides restore functionality.
"""

import shutil
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class BackupService:
    def __init__(self, backup_dir: Path, max_backups: int = 20) -> None:
        self._dir = backup_dir
        self._max = max_backups
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def backup_file(self, source: Path, label: str) -> Path:
        """
        Copy *source* into the backup directory with a timestamp + label suffix.
        Returns the backup path.
        Raises FileNotFoundError if source does not exist.
        """
        if not source.exists():
            raise FileNotFoundError(f"Cannot back up missing file: {source}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_name = f"{label}__{timestamp}{source.suffix or '.bak'}"
        dest = self._dir / dest_name

        shutil.copy2(source, dest)
        logger.info("Backup created: %s", dest)

        self._prune(label)
        return dest

    def list_backups(self, label: str | None = None) -> list[Path]:
        """Return backup files, optionally filtered by label, newest first."""
        pattern = f"{label}__*" if label else "*"
        files = sorted(self._dir.glob(pattern), reverse=True)
        return files

    def restore(self, backup_path: Path, destination: Path) -> None:
        """Overwrite *destination* with the contents of *backup_path*."""
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")

        shutil.copy2(backup_path, destination)
        logger.info("Restored %s → %s", backup_path.name, destination)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _prune(self, label: str) -> None:
        """Remove oldest backups for this label if count exceeds max_backups."""
        files = self.list_backups(label)
        excess = files[self._max:]
        for old in excess:
            try:
                old.unlink()
                logger.debug("Pruned old backup: %s", old.name)
            except Exception as exc:
                logger.warning("Could not prune backup %s: %s", old.name, exc)
