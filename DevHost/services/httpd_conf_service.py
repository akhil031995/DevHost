"""
httpd.conf service — manages Listen directives in Apache's main config file.
Only touches DevHost-managed Listen lines between markers.
Port 80 is assumed to always exist (XAMPP default) and is never removed.
"""

import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MARKER_BEGIN = "# BEGIN DevHost Ports"
_MARKER_END   = "# END DevHost Ports"
_ALWAYS_KEEP  = {80}   # port 80 is always native in httpd.conf — never touch it

_WRITE_RETRIES = 3
_WRITE_DELAY   = 0.5


class HttpdConfService:
    def __init__(self, httpd_conf: str) -> None:
        self._path = Path(httpd_conf)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sync_ports(self, active_ports: set[int]) -> None:
        """
        Ensure every port in *active_ports* has a Listen directive.
        Ports not in active_ports (and not in _ALWAYS_KEEP) are removed
        from the managed block.
        """
        if not self._path.exists():
            raise FileNotFoundError(f"httpd.conf not found: {self._path}")

        # Ports 80/443 must always stay — never remove them
        wanted = active_ports | _ALWAYS_KEEP

        # Only manage ports that aren't already native (80 lives in httpd.conf natively).
        extra = wanted - {80}

        self._write_managed_ports(extra)
        logger.info("httpd.conf Listen ports synced: native 80 + managed %s", sorted(extra))

    def add_port(self, port: int) -> None:
        """Ensure a single port has a Listen directive."""
        current = self._read_managed_ports()
        if port not in {80} and port not in current:
            current.add(port)
            self._write_managed_ports(current)
            logger.info("Added Listen %d to httpd.conf", port)

    def remove_port_if_unused(self, port: int, remaining_ports: set[int]) -> None:
        """
        Remove a port's Listen directive only if no remaining domain uses it
        and it is not in _ALWAYS_KEEP.
        """
        if port in _ALWAYS_KEEP or port == 80:
            return
        if port in remaining_ports:
            return
        current = self._read_managed_ports()
        current.discard(port)
        self._write_managed_ports(current)
        logger.info("Removed Listen %d from httpd.conf", port)

    def get_managed_ports(self) -> set[int]:
        return self._read_managed_ports()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read_lines(self) -> list[str]:
        with self._path.open("r", encoding="utf-8", errors="replace") as fh:
            return fh.readlines()

    def _read_managed_ports(self) -> set[int]:
        ports: set[int] = set()
        inside = False
        for line in self._read_lines():
            s = line.strip()
            if s == _MARKER_BEGIN:
                inside = True
                continue
            if s == _MARKER_END:
                break
            if inside and s.startswith("Listen "):
                try:
                    ports.add(int(s.split()[1]))
                except (IndexError, ValueError):
                    pass
        return ports

    def _write_managed_ports(self, ports: set[int]) -> None:
        lines = self._read_lines()

        # Strip existing managed block
        cleaned: list[str] = []
        inside = False
        for line in lines:
            s = line.strip()
            if s == _MARKER_BEGIN:
                inside = True
                continue
            if s == _MARKER_END:
                inside = False
                continue
            if not inside:
                cleaned.append(line)

        # Remove trailing blanks
        while cleaned and cleaned[-1].strip() == "":
            cleaned.pop()

        if ports:
            block: list[str] = ["\n", _MARKER_BEGIN + "\n"]
            for p in sorted(ports):
                block.append(f"Listen {p}\n")
            block.append(_MARKER_END + "\n")
            new_content = "".join(cleaned + block)
        else:
            # No extra ports — leave file clean, no block at all
            new_content = "".join(cleaned) + "\n"

        self._safe_write(new_content)

    def _safe_write(self, content: str) -> None:
        for attempt in range(1, _WRITE_RETRIES + 1):
            try:
                with self._path.open("w", encoding="utf-8") as fh:
                    fh.write(content)
                logger.info("httpd.conf updated: %s", self._path)
                return
            except PermissionError as exc:
                if attempt < _WRITE_RETRIES:
                    logger.warning(
                        "httpd.conf write attempt %d/%d failed — retrying…", attempt, _WRITE_RETRIES
                    )
                    time.sleep(_WRITE_DELAY)
                else:
                    raise
