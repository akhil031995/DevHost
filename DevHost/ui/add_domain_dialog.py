"""
Add Domain dialog — collects domain info from the user.
"""

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTextEdit, QVBoxLayout, QCheckBox, QFileDialog,
)
from PySide6.QtCore import Qt

from services.validation_service import ValidationService


class AddDomainDialog(QDialog):
    """Modal dialog for adding a new virtual host domain."""

    def __init__(
        self,
        parent=None,
        validation_service: ValidationService | None = None,
        default_port: int = 80,
        existing_domains: list[str] | None = None,
        existing_ports: dict[int, str] | None = None,
        default_doc_root: str = "",
    ) -> None:
        super().__init__(parent)
        self._validator = validation_service
        self._existing = existing_domains or []
        self._existing_ports = existing_ports or {}   # {port: domain}
        self._default_root = default_doc_root

        self.setWindowTitle("Add New Domain")
        self.setMinimumWidth(520)
        self.setModal(True)
        self._build_ui(default_port)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self, default_port: int) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("Add New Local Domain")
        title.setObjectName("label_accent")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        root.addWidget(title)

        subtitle = QLabel(
            "Configure a new virtual host for your local development environment."
        )
        subtitle.setObjectName("label_muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # ── Domain group ──────────────────────────────────────────────
        domain_grp = QGroupBox("Domain Configuration")
        domain_form = QFormLayout(domain_grp)
        domain_form.setSpacing(10)
        domain_form.setContentsMargins(12, 16, 12, 12)

        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("e.g. myapp.local")
        domain_form.addRow("Domain Name *", self.domain_input)

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(default_port)
        self.port_input.setFixedWidth(100)
        domain_form.addRow("Port *", self.port_input)

        self.ssl_check = QCheckBox("Enable SSL (future — requires mkcert)")
        self.ssl_check.setEnabled(False)
        domain_form.addRow("", self.ssl_check)

        root.addWidget(domain_grp)

        # ── Path group ────────────────────────────────────────────────
        path_grp = QGroupBox("Document Root")
        path_layout = QVBoxLayout(path_grp)
        path_layout.setContentsMargins(12, 16, 12, 12)

        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText(r"e.g. F:\php_workspace\myapp\public")
        if self._default_root:
            self.path_input.setText(self._default_root)
        path_row.addWidget(self.path_input)

        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._browse_path)
        path_row.addWidget(browse_btn)
        path_layout.addLayout(path_row)

        self.path_warning = QLabel("")
        self.path_warning.setStyleSheet("color: #f9e2af; font-size: 12px;")
        self.path_warning.setVisible(False)
        path_layout.addWidget(self.path_warning)
        root.addWidget(path_grp)

        # ── Notes ─────────────────────────────────────────────────────
        notes_grp = QGroupBox("Notes (optional)")
        notes_layout = QVBoxLayout(notes_grp)
        notes_layout.setContentsMargins(12, 16, 12, 12)
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Any notes about this project…")
        self.notes_input.setFixedHeight(60)
        notes_layout.addWidget(self.notes_input)
        root.addWidget(notes_grp)

        # ── Buttons ───────────────────────────────────────────────────
        buttons = QDialogButtonBox()
        self._ok_btn = QPushButton("Add Domain")
        self._ok_btn.setObjectName("btn_primary")
        self._ok_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")

        buttons.addButton(self._ok_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        # Live domain validation feedback
        self.domain_input.textChanged.connect(self._on_domain_changed)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _browse_path(self) -> None:
        start = self.path_input.text() or self._default_root or "C:\\"
        chosen = QFileDialog.getExistingDirectory(self, "Select Document Root", start)
        if chosen:
            self.path_input.setText(chosen)

    def _on_domain_changed(self, text: str) -> None:
        if not self._validator:
            return
        result = self._validator.validate_domain(text)
        if text and not result.ok:
            self.domain_input.setStyleSheet("border-color: #f38ba8;")
        else:
            self.domain_input.setStyleSheet("")

    def _on_accept(self) -> None:
        domain = self.domain_input.text().strip().lower()
        path = self.path_input.text().strip()
        port = self.port_input.value()

        # ── Validate domain ──────────────────────────────────────────
        if self._validator:
            result = self._validator.validate_domain(domain)
            if not result.ok:
                QMessageBox.warning(self, "Invalid Domain", result.message)
                self.domain_input.setFocus()
                return

        # ── Duplicate check ──────────────────────────────────────────
        if domain in self._existing:
            QMessageBox.warning(
                self, "Duplicate Domain",
                f"The domain '{domain}' already exists.\nChoose a different name.",
            )
            self.domain_input.setFocus()
            return

        # ── Validate path ────────────────────────────────────────────
        if self._validator:
            result = self._validator.validate_path(path)
            if not result.ok:
                reply = QMessageBox.question(
                    self, "Path Does Not Exist",
                    f"{result.message}\n\nAdd anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    self.path_input.setFocus()
                    return

        # ── Validate port ────────────────────────────────────────────
        if self._validator:
            result = self._validator.validate_port(port)
            if not result.ok:
                QMessageBox.warning(self, "Invalid Port", result.message)
                self.port_input.setFocus()
                return

        # ── Port conflict check ──────────────────────────────────────
        if port != 80 and port in self._existing_ports:
            conflict = self._existing_ports[port]
            reply = QMessageBox.warning(
                self, "Port Already in Use",
                f"Port <b>{port}</b> is already used by <b>{conflict}</b>.<br><br>"
                "Multiple domains can share a port, but Apache may behave "
                "unexpectedly without distinct ServerAlias or ServerName rules.<br><br>"
                "Add anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                self.port_input.setFocus()
                return

        self.accept()

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    @property
    def domain(self) -> str:
        return self.domain_input.text().strip().lower()

    @property
    def doc_root(self) -> str:
        return self.path_input.text().strip()

    @property
    def port(self) -> int:
        return self.port_input.value()

    @property
    def ssl(self) -> bool:
        return self.ssl_check.isChecked()

    @property
    def notes(self) -> str:
        return self.notes_input.toPlainText().strip()
