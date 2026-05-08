"""
Edit Domain dialog — pre-populated with an existing domain's data.
Reuses the same layout as Add Domain but pre-fills all fields.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTextEdit, QVBoxLayout, QCheckBox, QFileDialog,
)

from services.validation_service import ValidationService


class EditDomainDialog(QDialog):
    """Modal dialog for editing an existing virtual host domain."""

    def __init__(
        self,
        parent=None,
        validation_service: ValidationService | None = None,
        existing_domains: list[str] | None = None,
        existing_ports: dict[int, str] | None = None,
        # Pre-filled values
        domain: str = "",
        doc_root: str = "",
        port: int = 80,
        ssl: bool = False,
        notes: str = "",
    ) -> None:
        super().__init__(parent)
        self._validator = validation_service
        self._existing = existing_domains or []
        self._existing_ports = existing_ports or {}   # {port: domain}
        self._original_domain = domain
        self._original_port = port

        self.setWindowTitle(f"Edit Domain — {domain}")
        self.setMinimumWidth(520)
        self.setModal(True)
        self._build_ui(domain, doc_root, port, ssl, notes)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(
        self,
        domain: str, doc_root: str, port: int, ssl: bool, notes: str,
    ) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(16)
        root_layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel(f"Edit Domain: {domain}")
        title.setObjectName("label_accent")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        root_layout.addWidget(title)

        subtitle = QLabel("Update the virtual host configuration for this domain.")
        subtitle.setObjectName("label_muted")
        root_layout.addWidget(subtitle)

        # ── Domain group ──────────────────────────────────────────────
        domain_grp = QGroupBox("Domain Configuration")
        domain_form = QFormLayout(domain_grp)
        domain_form.setSpacing(10)
        domain_form.setContentsMargins(12, 16, 12, 12)

        self.domain_input = QLineEdit(domain)
        domain_form.addRow("Domain Name *", self.domain_input)

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(port)
        self.port_input.setFixedWidth(100)
        domain_form.addRow("Port *", self.port_input)

        self.ssl_check = QCheckBox("Enable SSL (future — requires mkcert)")
        self.ssl_check.setChecked(ssl)
        self.ssl_check.setEnabled(False)
        domain_form.addRow("", self.ssl_check)

        root_layout.addWidget(domain_grp)

        # ── Path group ────────────────────────────────────────────────
        path_grp = QGroupBox("Document Root")
        path_layout = QVBoxLayout(path_grp)
        path_layout.setContentsMargins(12, 16, 12, 12)

        path_row = QHBoxLayout()
        self.path_input = QLineEdit(doc_root)
        path_row.addWidget(self.path_input)

        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._browse_path)
        path_row.addWidget(browse_btn)
        path_layout.addLayout(path_row)
        root_layout.addWidget(path_grp)

        # ── Notes ─────────────────────────────────────────────────────
        notes_grp = QGroupBox("Notes (optional)")
        notes_layout = QVBoxLayout(notes_grp)
        notes_layout.setContentsMargins(12, 16, 12, 12)
        self.notes_input = QTextEdit(notes)
        self.notes_input.setFixedHeight(60)
        notes_layout.addWidget(self.notes_input)
        root_layout.addWidget(notes_grp)

        # ── Buttons ───────────────────────────────────────────────────
        buttons = QDialogButtonBox()
        self._ok_btn = QPushButton("Save Changes")
        self._ok_btn.setObjectName("btn_primary")
        self._ok_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")

        buttons.addButton(self._ok_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)

        self.domain_input.textChanged.connect(self._on_domain_changed)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _browse_path(self) -> None:
        start = self.path_input.text() or "C:\\"
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

        if self._validator:
            r = self._validator.validate_domain(domain)
            if not r.ok:
                QMessageBox.warning(self, "Invalid Domain", r.message)
                return

        # Allow same name (not changed), but reject if it clashes with another
        if domain != self._original_domain and domain in self._existing:
            QMessageBox.warning(
                self, "Duplicate Domain",
                f"The domain '{domain}' already exists.",
            )
            return

        if self._validator:
            r = self._validator.validate_path(path)
            if not r.ok:
                reply = QMessageBox.question(
                    self, "Path Does Not Exist",
                    f"{r.message}\n\nSave anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    return

        if self._validator:
            r = self._validator.validate_port(port)
            if not r.ok:
                QMessageBox.warning(self, "Invalid Port", r.message)
                return

        # ── Port conflict check (skip if port unchanged) ─────────────
        if port != 80 and port != self._original_port and port in self._existing_ports:
            conflict = self._existing_ports[port]
            reply = QMessageBox.warning(
                self, "Port Already in Use",
                f"Port <b>{port}</b> is already used by <b>{conflict}</b>.<br><br>"
                "Multiple domains can share a port, but Apache may behave "
                "unexpectedly without distinct ServerAlias or ServerName rules.<br><br>"
                "Save anyway?",
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
