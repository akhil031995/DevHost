"""
Admin elevation service — ensures the process runs with administrator privileges.
Uses ctypes to check current elevation and ShellExecuteW to relaunch with "runas".
"""

import sys
import ctypes
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def is_admin() -> bool:
    """Return True if the current process has administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_as_admin() -> None:
    """
    Relaunch the current process with administrator privileges via UAC prompt.
    Exits the current (non-elevated) process after triggering the elevated one.
    """
    try:
        if getattr(sys, "frozen", False):
            # Running as a PyInstaller EXE — relaunch the EXE itself
            executable = sys.executable
            params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
            work_dir = str(Path(executable).parent)
        else:
            # Running from source — pass the absolute script path so the
            # elevated process can find it regardless of working directory.
            executable = sys.executable
            script = str(Path(sys.argv[0]).resolve())
            extra = " ".join(f'"{arg}"' for arg in sys.argv[1:])
            params = f'"{script}" {extra}'.strip()
            work_dir = str(Path(script).parent)

        logger.info("Relaunching with admin privileges: %s %s (cwd=%s)", executable, params, work_dir)

        ret = ctypes.windll.shell32.ShellExecuteW(
            None,       # hwnd
            "runas",    # verb — triggers UAC
            executable, # file
            params,     # parameters
            work_dir,   # lpDirectory — set working dir for the elevated process
            1,          # SW_SHOWNORMAL
        )

        # ShellExecuteW returns >32 on success
        if ret <= 32:
            logger.error("ShellExecuteW failed with code %d", ret)

    except Exception as exc:
        logger.exception("Failed to relaunch as admin: %s", exc)
    finally:
        sys.exit(0)


def ensure_admin() -> None:
    """
    Call this at application startup.
    If not running as admin, triggers UAC relaunch and exits.
    If already admin, returns normally.
    """
    if not is_admin():
        logger.warning("Not running as administrator — relaunching with elevation.")
        relaunch_as_admin()
