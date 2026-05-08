"""
Hosts file service — manages the Windows hosts file.
Only touches the DevHost-managed section between markers.
Never overwrites unrelated content.
"""

import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MARKER_BEGIN = "# BEGIN DevHost"
_MARKER_END = "# END DevHost"

# Retry parameters for locked-file writes
_WRITE_RETRIES = 3
_WRITE_DELAY = 0.5  # seconds


class HostsService:
    def __init__(self, hosts_path: str) -> None:
        self._path = Path(hosts_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_managed_entries(self) -> dict[str, str]:
        """Return {domain: ip} for every entry in the DevHost section."""
        entries: dict[str, str] = {}
        inside = False
        for line in self._read_lines():
            stripped = line.strip()
            if stripped == _MARKER_BEGIN:
                inside = True
                continue
            if stripped == _MARKER_END:
                break
            if inside and stripped and not stripped.startswith("#"):
                parts = stripped.split()
                if len(parts) >= 2:
                    entries[parts[1]] = parts[0]
        return entries

    def add_entry(self, domain: str, ip: str = "127.0.0.1") -> None:
        """Add or update a single domain entry in the managed section."""
        managed = self.read_managed_entries()
        managed[domain] = ip
        self._write_managed(managed)

    def remove_entry(self, domain: str) -> None:
        """Remove a domain from the managed section."""
        managed = self.read_managed_entries()
        managed.pop(domain, None)
        self._write_managed(managed)

    def update_entry(self, old_domain: str, new_domain: str, ip: str = "127.0.0.1") -> None:
        """Rename a domain entry."""
        managed = self.read_managed_entries()
        managed.pop(old_domain, None)
        managed[new_domain] = ip
        self._write_managed(managed)

    def disable_entry(self, domain: str) -> None:
        """Comment out the domain line so Apache ignores it."""
        self._set_entry_commented(domain, commented=True)

    def enable_entry(self, domain: str, ip: str = "127.0.0.1") -> None:
        """Uncomment the domain line (re-add if missing)."""
        self._set_entry_commented(domain, commented=False, ip=ip)

    def has_entry(self, domain: str) -> bool:
        return domain in self.read_managed_entries()

    def _set_entry_commented(self, domain: str, commented: bool, ip: str = "127.0.0.1") -> None:
        lines = self._read_lines()
        new_lines: list[str] = []
        inside = False
        found = False

        for line in lines:
            stripped = line.strip()
            if stripped == _MARKER_BEGIN:
                inside = True
                new_lines.append(line)
                continue
            if stripped == _MARKER_END:
                inside = False
                # If enabling and the entry was missing entirely, add it now
                if not found and not commented:
                    new_lines.append(f"{ip:<15} {domain}\n")
                new_lines.append(line)
                continue

            if inside:
                # Match both active and already-commented lines for this domain
                active   = stripped.split()
                inactive = stripped.lstrip("#").strip().split()
                is_this  = (
                    (len(active)   >= 2 and active[1]   == domain and not stripped.startswith("#")) or
                    (len(inactive) >= 2 and inactive[1] == domain and stripped.startswith("#"))
                )
                if is_this:
                    found = True
                    if commented:
                        # Ensure it's commented
                        base = stripped.lstrip("#").strip()
                        new_lines.append(f"#{base}\n")
                    else:
                        # Ensure it's active
                        parts = stripped.lstrip("#").strip().split()
                        stored_ip = parts[0] if parts else ip
                        new_lines.append(f"{stored_ip:<15} {domain}\n")
                    continue

            new_lines.append(line)

        self._safe_write("".join(new_lines))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read_lines(self) -> list[str]:
        if not self._path.exists():
            raise FileNotFoundError(f"Hosts file not found: {self._path}")
        with self._path.open("r", encoding="utf-8", errors="replace") as fh:
            return fh.readlines()

    def _write_managed(self, entries: dict[str, str]) -> None:
        """Rebuild the file, replacing only the managed block."""
        lines = self._read_lines()

        # Strip out existing managed block (including markers)
        cleaned: list[str] = []
        inside = False
        for line in lines:
            stripped = line.strip()
            if stripped == _MARKER_BEGIN:
                inside = True
                continue
            if stripped == _MARKER_END:
                inside = False
                continue
            if not inside:
                cleaned.append(line)

        # Remove trailing blank lines before appending new block
        while cleaned and cleaned[-1].strip() == "":
            cleaned.pop()

        # Build new managed block
        block_lines: list[str] = ["\n", _MARKER_BEGIN + "\n"]
        for domain, ip in sorted(entries.items()):
            block_lines.append(f"{ip:<15} {domain}\n")
        block_lines.append(_MARKER_END + "\n")

        new_content = "".join(cleaned + block_lines)
        self._safe_write(new_content)

    def _safe_write(self, content: str) -> None:
        """Write with retry logic for transiently locked files."""
        for attempt in range(1, _WRITE_RETRIES + 1):
            try:
                with self._path.open("w", encoding="utf-8") as fh:
                    fh.write(content)
                logger.info("Hosts file updated: %s", self._path)
                return
            except PermissionError as exc:
                if attempt < _WRITE_RETRIES:
                    logger.warning(
                        "Hosts file write attempt %d/%d failed (%s) — retrying…",
                        attempt, _WRITE_RETRIES, exc,
                    )
                    time.sleep(_WRITE_DELAY)
                else:
                    raise
