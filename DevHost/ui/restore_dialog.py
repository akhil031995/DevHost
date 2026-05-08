"""
Restore Backup dialog — list available backups and let the user restore one.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QHBoxLayout,
)
from PySide6.QtCore import Qt

from services.backup_service import BackupService


class RestoreDialog(QDialog):
    def __init__(
        self,
        parent=None,
        backup_service: BackupService | None = None,
        hosts_path: str = "",
        vhosts_path: str = "",
        httpdconf_path: str = "",
    ) -> None:
        super().__init__(parent)
        self._bs = backup_service
        self._hosts_path = hosts_path
        self._vhosts_path = vhosts_path
        self._httpdconf_path = httpdconf_path

        self.setWindowTitle("Restore Backup")
        self.setMinimumSize(620, 420)
        self.setModal(True)
        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel("Available Backups")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #89b4fa;")
        root.addWidget(title)

        hint = QLabel(
            "Select a backup file then click the target to restore it to. "
            "The current file will be overwritten."
        )
        hint.setObjectName("label_muted")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        root.addWidget(self._list)

        btn_row = QHBoxLayout()
        for label, path in [
            ("Restore → Hosts File",   self._hosts_path),
            ("Restore → VHosts Config", self._vhosts_path),
            ("Restore → httpd.conf",    self._httpdconf_path),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("btn_success")
            target = path  # capture for lambda
            btn.clicked.connect(lambda checked=False, t=target: self._restore(t))
            btn_row.addWidget(btn)
        root.addLayout(btn_row)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        root.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _populate(self) -> None:
        if not self._bs:
            return
        for path in self._bs.list_backups():
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self._list.addItem(item)

    def _restore(self, destination: str) -> None:
        item = self._list.currentItem()
        if not item:
            QMessageBox.warning(self, "No Selection", "Please select a backup file.")
            return
        if not destination:
            QMessageBox.warning(self, "No Target", "Target path is not configured in Settings.")
            return

        backup_path: Path = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self, "Confirm Restore",
            f"Restore:\n  {backup_path.name}\n\nTo:\n  {destination}\n\n"
            "This will overwrite the current file. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._bs.restore(backup_path, Path(destination))
            QMessageBox.information(self, "Restored", "File restored successfully.")
        except Exception as exc:
            QMessageBox.critical(self, "Restore Failed", str(exc))
