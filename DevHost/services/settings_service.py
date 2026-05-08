"""
Settings service — loads and persists application configuration from/to JSON.
Provides typed access to all configurable values with safe defaults.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Resolve paths relative to the project root (one level above services/)
_BASE_DIR = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _BASE_DIR / "config" / "settings.json"

_DEFAULTS: dict[str, Any] = {
    # Apache / web server
    "apache_bin": r"C:\xampp\apache\bin\httpd.exe",
    "vhosts_conf": r"C:\xampp\apache\conf\extra\httpd-vhosts.conf",
    "httpd_conf": r"C:\xampp\apache\conf\httpd.conf",
    "apache_service_name": "",          # optional Windows service name
    "server_type": "xampp",            # xampp | wamp | laragon | custom

    # Hosts file
    "hosts_file": r"C:\Windows\System32\drivers\etc\hosts",

    # Paths
    "backup_dir": str(_BASE_DIR / "backups"),
    "log_dir": str(_BASE_DIR / "logs"),
    "default_doc_root": r"F:\php_workspace",

    # Defaults for new domains
    "default_port": 80,
    "default_ssl_port": 443,

    # Behaviour
    "auto_restart_apache": True,
    "validate_before_save": True,
    "backup_before_modify": True,
    "max_backups": 20,
    "status_poll_interval": 5,   # seconds between Apache status checks (0 = disabled)

    # Apache operation timeouts (seconds)
    "timeout_start_bat": 60,     # apache_start.bat / apache_restart.bat
    "timeout_stop_bat": 30,      # apache_stop.bat
    "timeout_start_poll": 10,    # max seconds to poll after launching httpd.exe
    "timeout_service": 30,       # net start / net stop
}


class SettingsService:
    """Thread-safe, singleton-style settings manager."""

    def __init__(self, config_path: Path = _CONFIG_PATH) -> None:
        self._path = config_path
        self._data: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, fallback: Any = None) -> Any:
        return self._data.get(key, fallback)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def update(self, updates: dict[str, Any]) -> None:
        self._data.update(updates)
        self._save()

    def all(self) -> dict[str, Any]:
        return dict(self._data)

    def reset_to_defaults(self) -> None:
        self._data = dict(_DEFAULTS)
        self._save()

    # ------------------------------------------------------------------
    # Convenience typed accessors
    # ------------------------------------------------------------------

    @property
    def apache_bin(self) -> str:
        return self._data["apache_bin"]

    @property
    def vhosts_conf(self) -> str:
        return self._data["vhosts_conf"]

    @property
    def httpd_conf(self) -> str:
        return self._data.get("httpd_conf", r"C:\xampp\apache\conf\httpd.conf")

    @property
    def hosts_file(self) -> str:
        return self._data["hosts_file"]

    @property
    def backup_dir(self) -> Path:
        p = Path(self._data["backup_dir"])
        return p if p.is_absolute() else _BASE_DIR / p

    @property
    def log_dir(self) -> Path:
        p = Path(self._data["log_dir"])
        return p if p.is_absolute() else _BASE_DIR / p

    @property
    def default_port(self) -> int:
        return int(self._data.get("default_port", 80))

    @property
    def auto_restart_apache(self) -> bool:
        return bool(self._data.get("auto_restart_apache", True))

    @property
    def validate_before_save(self) -> bool:
        return bool(self._data.get("validate_before_save", True))

    @property
    def backup_before_modify(self) -> bool:
        return bool(self._data.get("backup_before_modify", True))

    @property
    def max_backups(self) -> int:
        return int(self._data.get("max_backups", 20))

    @property
    def status_poll_interval(self) -> int:
        return max(0, int(self._data.get("status_poll_interval", 5)))

    @property
    def timeout_start_bat(self) -> int:
        return max(5, int(self._data.get("timeout_start_bat", 60)))

    @property
    def timeout_stop_bat(self) -> int:
        return max(5, int(self._data.get("timeout_stop_bat", 30)))

    @property
    def timeout_start_poll(self) -> int:
        return max(1, int(self._data.get("timeout_start_poll", 10)))

    @property
    def timeout_service(self) -> int:
        return max(5, int(self._data.get("timeout_service", 30)))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        self._data = dict(_DEFAULTS)
        if self._path.exists():
            try:
                with self._path.open("r", encoding="utf-8") as fh:
                    stored = json.load(fh)
                self._data.update(stored)
                logger.debug("Settings loaded from %s", self._path)
            except Exception as exc:
                logger.warning("Could not load settings (%s) — using defaults.", exc)
        else:
            logger.info("No settings file found — creating with defaults.")
            self._save()

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
            logger.debug("Settings saved to %s", self._path)
        except Exception as exc:
            logger.error("Failed to save settings: %s", exc)
