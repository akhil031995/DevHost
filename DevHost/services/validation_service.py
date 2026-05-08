"""
Validation service — validates domain names, paths, and Apache configuration syntax.
"""

import re
import subprocess
import logging
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# RFC-1123 hostname regex, allows .local / .test / .dev suffixes
_DOMAIN_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


@dataclass
class ValidationResult:
    ok: bool
    message: str = ""

    def __bool__(self) -> bool:
        return self.ok


class ValidationService:
    def __init__(self, apache_bin: str) -> None:
        self._apache_bin = apache_bin

    # ------------------------------------------------------------------
    # Domain / field validation
    # ------------------------------------------------------------------

    def validate_domain(self, domain: str) -> ValidationResult:
        domain = domain.strip()
        if not domain:
            return ValidationResult(False, "Domain name is required.")
        if not _DOMAIN_RE.match(domain):
            return ValidationResult(
                False,
                f"'{domain}' is not a valid domain name.\n"
                "Use lowercase letters, digits, hyphens, and dots (e.g. myapp.local).",
            )
        return ValidationResult(True)

    def validate_path(self, path_str: str) -> ValidationResult:
        path_str = path_str.strip()
        if not path_str:
            return ValidationResult(False, "Document root path is required.")
        path = Path(path_str)
        if not path.exists():
            return ValidationResult(
                False,
                f"Path does not exist:\n{path_str}\n\nCreate the directory first.",
            )
        if not path.is_dir():
            return ValidationResult(False, f"Path is not a directory:\n{path_str}")
        return ValidationResult(True)

    def validate_port(self, port: int | str) -> ValidationResult:
        try:
            p = int(port)
        except (ValueError, TypeError):
            return ValidationResult(False, "Port must be a number.")
        if not (1 <= p <= 65535):
            return ValidationResult(False, "Port must be between 1 and 65535.")
        return ValidationResult(True)

    # ------------------------------------------------------------------
    # Apache config syntax validation
    # ------------------------------------------------------------------

    def validate_apache_config(self) -> ValidationResult:
        """
        Run `httpd.exe -t` to validate Apache config syntax.
        Returns ok=True if syntax is valid.
        """
        apache_bin = self._apache_bin.strip()
        if not apache_bin:
            return ValidationResult(False, "Apache binary path is not configured.")

        bin_path = Path(apache_bin)
        if not bin_path.exists():
            return ValidationResult(
                False,
                f"Apache executable not found:\n{apache_bin}\n\n"
                "Check the Apache path in Settings.",
            )

        try:
            result = subprocess.run(
                [apache_bin, "-t"],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            # httpd -t writes to stderr even on success ("Syntax OK")
            output = (result.stdout + result.stderr).strip()
            logger.debug("httpd -t output: %s", output)

            if result.returncode == 0 or "Syntax OK" in output:
                return ValidationResult(True, "Syntax OK")

            return ValidationResult(False, f"Apache config error:\n\n{output}")

        except subprocess.TimeoutExpired:
            return ValidationResult(False, "Apache validation timed out after 15 s.")
        except Exception as exc:
            logger.exception("Apache validation failed")
            return ValidationResult(False, f"Could not run Apache validation:\n{exc}")
