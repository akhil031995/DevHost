"""
Apache service — starts, stops, and restarts Apache.
Supports XAMPP, WAMP, Laragon, and custom installations.
"""

import subprocess
import logging
import time
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)

# For subprocess.run() calls that must wait for output.
# DETACHED_PROCESS must NOT be used here — it breaks communicate() / timeout.
_RUN_FLAGS = subprocess.CREATE_NO_WINDOW

# For Popen fire-and-forget launches (httpd.exe itself).
# DETACHED_PROCESS fully severs the child from our console.
_POPEN_FLAGS = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS


def _run_silent(cmd: list[str], cwd: str | None = None, timeout: int = 30) -> int:
    """Run a command with no visible window, no stdio, return exit code."""
    r = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_RUN_FLAGS,
        cwd=cwd,
        timeout=timeout,
    )
    return r.returncode


def _popen_silent(cmd: list[str]) -> None:
    """Launch a process detached with no stdio handles — fire and forget."""
    subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_POPEN_FLAGS,
        close_fds=True,
    )


class ServerType(str, Enum):
    XAMPP = "xampp"
    WAMP = "wamp"
    LARAGON = "laragon"
    CUSTOM = "custom"


class ApacheService:
    def __init__(
        self,
        apache_bin: str,
        server_type: str = "xampp",
        service_name: str = "",
        timeout_start_bat: int = 60,
        timeout_stop_bat: int = 30,
        timeout_start_poll: int = 10,
        timeout_service: int = 30,
    ) -> None:
        self._bin = apache_bin
        self._type = ServerType(server_type.lower()) if server_type else ServerType.CUSTOM
        self._service = service_name
        self._t_start_bat   = timeout_start_bat
        self._t_stop_bat    = timeout_stop_bat
        self._t_start_poll  = timeout_start_poll
        self._t_service     = timeout_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> tuple[bool, str]:
        """Start Apache (no-op if already running). Returns (ok, message)."""
        logger.info("Starting Apache (%s)…", self._type)
        try:
            if self.is_running():
                return True, "Apache is already running."

            if self._service:
                rc = _run_silent(["net", "start", self._service], timeout=self._t_service)
                if rc != 0:
                    return False, f"Failed to start Windows service '{self._service}'."
                return True, f"Service '{self._service}' started."

            # Launch httpd.exe detached — apache_start.bat blocks forever (runs httpd in foreground)
            return self._launch_and_poll()

        except Exception as exc:
            msg = f"Apache start failed: {exc}"
            logger.exception(msg)
            return False, msg

    def restart(self) -> tuple[bool, str]:
        """Restart Apache using the appropriate strategy. Returns (ok, message)."""
        logger.info("Restarting Apache (%s)…", self._type)
        try:
            if self._service:
                return self._restart_via_service()
            if self._type == ServerType.XAMPP:
                return self._restart_xampp()
            if self._type == ServerType.WAMP:
                return self._restart_wamp()
            if self._type == ServerType.LARAGON:
                return self._restart_laragon()
            return self._stop_then_start()
        except Exception as exc:
            msg = f"Apache restart failed: {exc}"
            logger.exception(msg)
            return False, msg

    def stop(self) -> tuple[bool, str]:
        """Stop Apache completely. Returns (ok, message)."""
        logger.info("Stopping Apache (%s)…", self._type)
        try:
            if self._service:
                rc = _run_silent(["net", "stop", self._service], timeout=self._t_service)
                if rc != 0:
                    return False, f"Failed to stop Windows service '{self._service}'."
                return True, f"Service '{self._service}' stopped."

            # apache_stop.bat contains a broken @@BITROCK_INSTALLDIR@@ placeholder — use taskkill directly
            return self._kill_httpd()

        except Exception as exc:
            msg = f"Apache stop failed: {exc}"
            logger.exception(msg)
            return False, msg

    def test_config(self) -> tuple[bool, str]:
        """Run httpd -t and return (ok, output)."""
        if not Path(self._bin).exists():
            return False, f"Apache binary not found: {self._bin}"
        result = subprocess.run(
            [self._bin, "-t"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=_RUN_FLAGS,
        )
        output = (result.stdout + result.stderr).strip()
        ok = result.returncode == 0 or "Syntax OK" in output
        return ok, output

    def is_running(self) -> bool:
        """Check if httpd.exe is in the process list."""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq httpd.exe", "/NH"],
                capture_output=True, text=True, timeout=5,
                creationflags=_RUN_FLAGS,
            )
            return "httpd.exe" in result.stdout
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Restart strategies
    # ------------------------------------------------------------------

    def _restart_via_service(self) -> tuple[bool, str]:
        """net stop / net start for a named Windows service."""
        _run_silent(["net", "stop", self._service], timeout=self._t_service)
        rc = _run_silent(["net", "start", self._service], timeout=self._t_service)
        if rc != 0:
            return False, f"Failed to start Windows service '{self._service}'."
        return True, f"Service '{self._service}' restarted."

    def _restart_xampp(self) -> tuple[bool, str]:
        """Kill httpd.exe then relaunch it detached — bat files are unreliable on this XAMPP build."""
        return self._stop_then_start()

    def _restart_wamp(self) -> tuple[bool, str]:
        return self._stop_then_start()

    def _restart_laragon(self) -> tuple[bool, str]:
        old, self._service = self._service, "laragon-apache"
        result = self._restart_via_service()
        self._service = old
        return result

    def _kill_httpd(self) -> tuple[bool, str]:
        """Force-kill all httpd.exe processes and confirm they are gone."""
        _run_silent(["taskkill", "/F", "/IM", "httpd.exe"], timeout=10)
        time.sleep(0.5)
        if not self.is_running():
            return True, "Apache stopped."
        return False, "Stop command ran but httpd.exe is still running."

    def _launch_and_poll(self) -> tuple[bool, str]:
        """Launch httpd.exe detached and poll until it appears in the process list."""
        try:
            _popen_silent([self._bin])
        except Exception as exc:
            return False, f"Failed to launch Apache: {exc}"
        for _ in range(self._t_start_poll):
            time.sleep(1)
            if self.is_running():
                return True, "Apache started."
        return False, f"Apache launched but not detected after {self._t_start_poll} s."

    def _stop_then_start(self) -> tuple[bool, str]:
        """Kill httpd.exe then relaunch a fresh detached instance."""
        ok, msg = self._kill_httpd()
        if not ok:
            logger.warning("Stop phase: %s", msg)
        time.sleep(0.5)
        ok, msg = self._launch_and_poll()
        if ok:
            return True, "Apache restarted successfully."
        return False, msg
