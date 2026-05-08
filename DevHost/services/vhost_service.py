"""
Virtual host service — manages Apache vhost entries in the vhosts.conf file.
Only touches the DevHost-managed section between markers.
"""

import time
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_MARKER_BEGIN = "# BEGIN DevHost"
_MARKER_END = "# END DevHost"

_WRITE_RETRIES = 3
_WRITE_DELAY = 0.5


@dataclass
class DomainEntry:
    domain: str
    doc_root: str
    port: int = 80
    ssl: bool = False
    notes: str = ""
    ip: str = "127.0.0.1"
    enabled: bool = True
    extra_directives: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

_VHOST_TEMPLATE = """\
<VirtualHost *:{port}>
    ServerName {domain}
    DocumentRoot "{doc_root_fwd}"

    <Directory "{doc_root_fwd}">
        AllowOverride All
        Require all granted
    </Directory>

    ErrorLog "logs/{domain}-error.log"
    CustomLog "logs/{domain}-access.log" common
</VirtualHost>"""


def _render_vhost(entry: DomainEntry) -> str:
    doc_root_fwd = entry.doc_root.replace("\\", "/")
    block = _VHOST_TEMPLATE.format(
        port=entry.port,
        domain=entry.domain,
        doc_root_fwd=doc_root_fwd,
    )
    if entry.notes:
        block = f"# {entry.notes}\n{block}"
    return block


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class VhostService:
    def __init__(self, vhosts_conf: str) -> None:
        self._path = Path(vhosts_conf)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_entry(self, entry: DomainEntry) -> None:
        entries = self._read_managed_entries()
        entries[entry.domain] = entry
        self._write_managed(entries)

    def remove_entry(self, domain: str) -> None:
        entries = self._read_managed_entries()
        entries.pop(domain, None)
        self._write_managed(entries)

    def update_entry(self, old_domain: str, new_entry: DomainEntry) -> None:
        entries = self._read_managed_entries()
        entries.pop(old_domain, None)
        entries[new_entry.domain] = new_entry
        self._write_managed(entries)

    def get_domains(self) -> list[str]:
        return list(self._read_managed_entries().keys())

    def has_domain(self, domain: str) -> bool:
        return domain in self._read_managed_entries()

    def disable_entry(self, domain: str) -> None:
        """Comment out every line of the vhost block for this domain."""
        self._set_block_commented(domain, commented=True)

    def enable_entry(self, domain: str) -> None:
        """Uncomment every line of the vhost block for this domain."""
        self._set_block_commented(domain, commented=False)

    def _set_block_commented(self, domain: str, commented: bool) -> None:
        lines = self._read_raw_lines()
        new_lines: list[str] = []
        inside_managed = False
        pending_block: list[str] = []   # lines buffered since <VirtualHost>, domain not yet confirmed

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            bare = stripped.lstrip("#").strip()

            if stripped == _MARKER_BEGIN:
                inside_managed = True
                new_lines.append(line)
                i += 1
                continue
            if stripped == _MARKER_END:
                # Flush any pending block as-is (domain never matched)
                new_lines.extend(pending_block)
                pending_block = []
                inside_managed = False
                new_lines.append(line)
                i += 1
                continue

            if not inside_managed:
                new_lines.append(line)
                i += 1
                continue

            # Start buffering when we see a <VirtualHost …> tag
            if bare.startswith("<VirtualHost") and not pending_block:
                pending_block.append(line)
                i += 1
                continue

            if pending_block:
                pending_block.append(line)

                # Once we see ServerName, we know whether this is our domain
                if bare.lower().startswith("servername"):
                    parts = bare.split()
                    block_domain = parts[1] if len(parts) > 1 else ""

                    if block_domain != domain:
                        # Not our domain — flush the buffer unchanged and stop buffering
                        new_lines.extend(pending_block)
                        pending_block = []
                    # else: correct domain — keep buffering until </VirtualHost>

                # End of block — flush with comment/uncomment transformation if matched
                if bare == "</VirtualHost>":
                    for bline in pending_block:
                        bs = bline.strip()
                        bb = bs.lstrip("#").strip()
                        if commented:
                            if bs == "" or bs.startswith("#"):
                                new_lines.append(bline)
                            else:
                                new_lines.append("#" + bline)
                        else:
                            if bline.startswith("#"):
                                new_lines.append(bline[1:])
                            else:
                                new_lines.append(bline)
                    pending_block = []
                i += 1
                continue

            new_lines.append(line)
            i += 1

        # Safety: flush any remaining pending lines
        new_lines.extend(pending_block)
        self._safe_write("".join(new_lines))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read_managed_entries(self) -> dict[str, DomainEntry]:
        """
        Parse vhost file and return DomainEntry objects for each managed block.
        This is a best-effort parse — we re-render from stored app data on write,
        so we only need to detect which domains exist.
        """
        entries: dict[str, DomainEntry] = {}
        if not self._path.exists():
            return entries

        current_domain: str | None = None
        current_port = 80
        current_root = ""
        inside = False

        with self._path.open("r", encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if line == _MARKER_BEGIN:
                    inside = True
                    continue
                if line == _MARKER_END:
                    break
                if not inside:
                    continue

                if line.startswith("<VirtualHost"):
                    # e.g. <VirtualHost *:80>
                    try:
                        current_port = int(line.split(":")[1].rstrip(">"))
                    except (IndexError, ValueError):
                        current_port = 80
                elif line.lower().startswith("servername"):
                    current_domain = line.split()[1] if len(line.split()) > 1 else None
                elif line.lower().startswith("documentroot"):
                    current_root = line.split(None, 1)[1].strip('"') if len(line.split()) > 1 else ""
                elif line == "</VirtualHost>" and current_domain:
                    entries[current_domain] = DomainEntry(
                        domain=current_domain,
                        doc_root=current_root,
                        port=current_port,
                    )
                    current_domain = None
                    current_root = ""
                    current_port = 80

        return entries

    def _read_raw_lines(self) -> list[str]:
        if not self._path.exists():
            # Create the file with a basic header if missing
            self._path.parent.mkdir(parents=True, exist_ok=True)
            header = "# Apache Virtual Hosts — managed by DevHost\n"
            self._path.write_text(header, encoding="utf-8")
        with self._path.open("r", encoding="utf-8", errors="replace") as fh:
            return fh.readlines()

    def _write_managed(self, entries: dict[str, DomainEntry]) -> None:
        lines = self._read_raw_lines()

        # Remove existing managed block
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

        while cleaned and cleaned[-1].strip() == "":
            cleaned.pop()

        # Build new block
        block: list[str] = ["\n", _MARKER_BEGIN + "\n\n"]
        for entry in entries.values():
            block.append(_render_vhost(entry) + "\n\n")
        block.append(_MARKER_END + "\n")

        new_content = "".join(cleaned + block)
        self._safe_write(new_content)

    def _safe_write(self, content: str) -> None:
        for attempt in range(1, _WRITE_RETRIES + 1):
            try:
                with self._path.open("w", encoding="utf-8") as fh:
                    fh.write(content)
                logger.info("vhosts.conf updated: %s", self._path)
                return
            except PermissionError as exc:
                if attempt < _WRITE_RETRIES:
                    logger.warning(
                        "vhosts.conf write attempt %d/%d failed (%s) — retrying…",
                        attempt, _WRITE_DELAY, exc,
                    )
                    time.sleep(_WRITE_DELAY)
                else:
                    raise
