"""
Main application window — domain table, toolbar, and orchestration.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer
from PySide6.QtGui import QAction, QIcon, QFont, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QToolBar,
    QStatusBar, QPushButton, QMessageBox, QSizePolicy,
    QApplication, QAbstractItemView,
)

from services.settings_service import SettingsService
from services.hosts_service import HostsService
from services.vhost_service import VhostService, DomainEntry
from services.apache_service import ApacheService
from services.backup_service import BackupService
from services.validation_service import ValidationService
from services.httpd_conf_service import HttpdConfService
from ui.add_domain_dialog import AddDomainDialog
from ui.edit_domain_dialog import EditDomainDialog
from ui.settings_dialog import SettingsDialog
from ui.restore_dialog import RestoreDialog

logger = logging.getLogger(__name__)

# ── Column indices ──────────────────────────────────────────────────────────
COL_OPEN   = 0
COL_TOGGLE = 1
COL_DOMAIN = 2
COL_PATH   = 3
COL_PORT   = 4
COL_STATUS = 5
COL_NOTES  = 6

COLUMNS = ["", "", "Domain", "Document Root", "Port", "Status", "Notes"]


# ── Worker threads for Apache operations ───────────────────────────────────
class ApacheRestartWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, apache: ApacheService) -> None:
        super().__init__()
        self._apache = apache

    def run(self) -> None:
        ok, msg = self._apache.restart()
        self.finished.emit(ok, msg)


class ApacheStopWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, apache: ApacheService) -> None:
        super().__init__()
        self._apache = apache

    def run(self) -> None:
        ok, msg = self._apache.stop()
        self.finished.emit(ok, msg)


class ApacheStartWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, apache: ApacheService) -> None:
        super().__init__()
        self._apache = apache

    def run(self) -> None:
        ok, msg = self._apache.start()
        self.finished.emit(ok, msg)


class ApacheStatusWorker(QThread):
    """Lightweight background thread for the periodic status poll."""
    result = Signal(bool)  # True = running

    def __init__(self, apache: ApacheService) -> None:
        super().__init__()
        self._apache = apache

    def run(self) -> None:
        self.result.emit(self._apache.is_running())


# ── Domain data store (in-memory, backed by domains.json) ──────────────────
class DomainStore:
    """Persists domain metadata alongside the vhost / hosts files."""

    def __init__(self, store_path: Path) -> None:
        self._path = store_path
        self._domains: dict[str, dict[str, Any]] = {}
        self._load()

    def all(self) -> dict[str, dict[str, Any]]:
        return dict(self._domains)

    def get(self, domain: str) -> dict[str, Any] | None:
        return self._domains.get(domain)

    def add(self, data: dict[str, Any]) -> None:
        self._domains[data["domain"]] = data
        self._save()

    def update(self, old_domain: str, data: dict[str, Any]) -> None:
        self._domains.pop(old_domain, None)
        self._domains[data["domain"]] = data
        self._save()

    def remove(self, domain: str) -> None:
        self._domains.pop(domain, None)
        self._save()

    def domains(self) -> list[str]:
        return list(self._domains.keys())

    def _load(self) -> None:
        if self._path.exists():
            try:
                with self._path.open("r", encoding="utf-8") as fh:
                    self._domains = json.load(fh)
            except Exception:
                self._domains = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as fh:
            json.dump(self._domains, fh, indent=2)


# ── Main Window ────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsService) -> None:
        super().__init__()
        self._settings = settings
        self._restart_worker: ApacheRestartWorker | None = None
        self._stop_worker: ApacheStopWorker | None = None
        self._start_worker: ApacheStartWorker | None = None
        self._status_worker: ApacheStatusWorker | None = None

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_apache_status)

        self._init_services()
        self._init_ui()
        self.refresh_table()
        self._check_config_paths()
        self._restart_poll_timer()

    # ------------------------------------------------------------------
    # Service init
    # ------------------------------------------------------------------

    def _init_services(self) -> None:
        s = self._settings
        self._backup = BackupService(s.backup_dir, s.max_backups)
        self._hosts = HostsService(s.hosts_file)
        self._vhost = VhostService(s.vhosts_conf)
        self._httpdconf = HttpdConfService(s.httpd_conf)
        self._apache = ApacheService(
            s.apache_bin,
            s.get("server_type", "xampp"),
            s.get("apache_service_name", ""),
            timeout_start_bat=s.timeout_start_bat,
            timeout_stop_bat=s.timeout_stop_bat,
            timeout_start_poll=s.timeout_start_poll,
            timeout_service=s.timeout_service,
        )
        self._validator = ValidationService(s.apache_bin)

        base_dir = Path(__file__).resolve().parent.parent
        self._store = DomainStore(base_dir / "config" / "domains.json")

    def _reinit_services(self) -> None:
        """Re-create services after settings change."""
        self._init_services()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        self.setWindowTitle("DevHost — Local Domain Manager")
        self.setMinimumSize(960, 600)
        self.resize(1100, 680)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_toolbar()
        self._build_header(layout)
        self._build_table(layout)
        self._build_statusbar()

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        def action(text: str, tip: str, slot, icon_text: str = "") -> QAction:
            act = QAction(text, self)
            act.setStatusTip(tip)
            act.triggered.connect(slot)
            tb.addAction(act)
            return act

        self._act_add     = action("＋  Add Domain",     "Add a new local domain",           self.on_add_domain)
        self._act_edit    = action("✎  Edit",            "Edit selected domain",              self.on_edit_domain)
        self._act_delete  = action("✕  Delete",          "Delete selected domain",            self.on_delete_domain)
        self._act_open    = action("⎋  Open in Chrome",  "Open selected domain in Chrome",    self.on_open_in_browser)
        tb.addSeparator()
        self._act_start   = action("▶  Start Apache",    "Start the Apache web server",        self.on_start_apache)
        self._act_restart = action("↺  Restart Apache",  "Restart the Apache web server",     self.on_restart_apache)
        self._act_stop    = action("■  Stop Apache",     "Stop the Apache web server",         self.on_stop_apache)
        tb.addSeparator()
        action("⚙  Settings",        "Open application settings",         self.on_open_settings)
        action("⧉  Open Config Dir", "Open config folder in Explorer",    self.on_open_config_dir)
        action("⬛  Backup Now",      "Manually create a backup now",      self.on_backup_now)
        action("⟳  Restore Backup",  "Restore a previous backup",         self.on_restore_backup)
        action("⟲  Refresh",         "Refresh domain list",               self.refresh_table)

        self._act_edit.setEnabled(False)
        self._act_delete.setEnabled(False)
        self._act_open.setEnabled(False)

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        header = QWidget()
        header.setObjectName("header")
        header.setStyleSheet(
            "QWidget#header { background: #181825; border-bottom: 1px solid #45475a; }"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 14, 20, 14)

        title_col = QVBoxLayout()
        title = QLabel("DevHost")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #89b4fa; letter-spacing: -0.5px;")
        subtitle = QLabel("Local Domain Manager for Apache / XAMPP / WAMP / Laragon")
        subtitle.setStyleSheet("font-size: 12px; color: #a6adc8;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        h_layout.addLayout(title_col)

        h_layout.addStretch()

        self._apache_badge = QLabel("● Apache: Unknown")
        self._apache_badge.setStyleSheet("color: #a6adc8; font-size: 12px;")
        h_layout.addWidget(self._apache_badge)

        check_btn = QPushButton("Check Status")
        check_btn.setFixedHeight(28)
        check_btn.clicked.connect(self._refresh_apache_status)
        h_layout.addWidget(check_btn)

        parent_layout.addWidget(header)

    def _build_table(self, parent_layout: QVBoxLayout) -> None:
        wrapper = QWidget()
        wrapper.setStyleSheet("background: #1e1e2e;")
        w_layout = QVBoxLayout(wrapper)
        w_layout.setContentsMargins(16, 16, 16, 16)

        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setSortingEnabled(False)
        self._table.horizontalHeader().setSectionsClickable(False)
        self._table.horizontalHeader().setStretchLastSection(True)

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(COL_OPEN,   QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(COL_TOGGLE, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(COL_DOMAIN, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(COL_PATH,   QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(COL_PORT,   QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(COL_NOTES,  QHeaderView.ResizeMode.ResizeToContents)
        self._table.setColumnWidth(COL_OPEN,   50)
        self._table.setColumnWidth(COL_TOGGLE, 54)
        self._table.setColumnWidth(COL_PORT,   70)
        self._table.setColumnWidth(COL_STATUS, 110)

        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._table.doubleClicked.connect(self.on_edit_domain)

        w_layout.addWidget(self._table)

        # Empty-state label
        self._empty_label = QLabel(
            "No domains configured yet.\n\nClick  ＋ Add Domain  to get started."
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            "color: #585b70; font-size: 15px; padding: 40px;"
        )
        self._empty_label.hide()
        w_layout.addWidget(self._empty_label)

        parent_layout.addWidget(wrapper)

    def _build_statusbar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status_label = QLabel("Ready")
        sb.addWidget(self._status_label)
        self._domain_count_label = QLabel("")
        sb.addPermanentWidget(self._domain_count_label)

    # ------------------------------------------------------------------
    # Table management
    # ------------------------------------------------------------------

    def refresh_table(self) -> None:
        domains = self._store.all()
        self._table.setRowCount(0)

        if not domains:
            self._table.hide()
            self._empty_label.show()
            self._domain_count_label.setText("")
        else:
            self._empty_label.hide()
            self._table.show()
            for data in sorted(domains.values(), key=lambda d: d.get("domain", "").lower()):
                self._add_table_row(data)
            self._domain_count_label.setText(
                f"{len(domains)} domain{'s' if len(domains) != 1 else ''}"
            )

    def _add_table_row(self, data: dict[str, Any]) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setRowHeight(row, 44)

        # ── Open-in-Chrome button (col 0) ─────────────────────────────
        open_btn = QPushButton("🔗")
        open_btn.setToolTip("Open in Chrome")
        open_btn.setFixedSize(42, 32)
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 16px;
                padding: 0;
                min-width: 0;
            }
            QPushButton:hover  { background-color: #313244; border-radius: 6px; }
            QPushButton:pressed { background-color: #45475a; border-radius: 6px; }
        """)
        domain_for_btn = data.get("domain", "")
        port_for_btn   = int(data.get("port", 80))
        open_btn.clicked.connect(
            lambda _, d=domain_for_btn, p=port_for_btn: self._open_url(d, p)
        )
        cell_widget = QWidget()
        cell_widget.setStyleSheet("background-color: transparent;")
        cell_layout = QHBoxLayout(cell_widget)
        cell_layout.addWidget(open_btn)
        cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cell_layout.setContentsMargins(4, 0, 4, 0)
        self._table.setCellWidget(row, COL_OPEN, cell_widget)

        # ── Enable/disable toggle (col 1) ─────────────────────────────
        enabled = data.get("enabled", True)
        toggle_btn = QPushButton("ON" if enabled else "OFF")
        toggle_btn.setFixedSize(40, 24)
        toggle_btn.setCheckable(True)
        toggle_btn.setChecked(enabled)
        self._style_toggle(toggle_btn, enabled)
        domain_for_toggle = data.get("domain", "")
        toggle_btn.clicked.connect(
            lambda checked, d=domain_for_toggle, b=toggle_btn: self.on_toggle_domain(d, checked, b)
        )
        toggle_cell = QWidget()
        toggle_cell.setStyleSheet("background-color: transparent;")
        toggle_layout = QHBoxLayout(toggle_cell)
        toggle_layout.addWidget(toggle_btn)
        toggle_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toggle_layout.setContentsMargins(2, 0, 2, 0)
        self._table.setCellWidget(row, COL_TOGGLE, toggle_cell)

        # ── Data columns ──────────────────────────────────────────────
        domain_item = QTableWidgetItem(data.get("domain", ""))
        domain_item.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        if enabled:
            domain_item.setForeground(QColor("#89b4fa"))
        else:
            domain_item.setForeground(QColor("#585b70"))

        path_item = QTableWidgetItem(data.get("doc_root", ""))
        port_item = QTableWidgetItem(str(data.get("port", 80)))
        port_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        if not enabled:
            status_item = QTableWidgetItem("○ Disabled")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(QColor("#585b70"))
        else:
            status = "active" if Path(data.get("doc_root", "")).exists() else "warning"
            status_item = QTableWidgetItem(
                "● Active" if status == "active" else "⚠ Path Missing"
            )
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(
                QColor("#a6e3a1") if status == "active" else QColor("#f9e2af")
            )

        notes_item = QTableWidgetItem(data.get("notes", ""))
        notes_item.setForeground(QColor("#a6adc8"))

        self._table.setItem(row, COL_DOMAIN, domain_item)
        self._table.setItem(row, COL_PATH,   path_item)
        self._table.setItem(row, COL_PORT,   port_item)
        self._table.setItem(row, COL_STATUS, status_item)
        self._table.setItem(row, COL_NOTES,  notes_item)

    def _selected_domain(self) -> str | None:
        rows = self._table.selectedItems()
        if not rows:
            return None
        return self._table.item(self._table.currentRow(), COL_DOMAIN).text()

    def _on_selection_changed(self) -> None:
        has_sel = bool(self._table.selectedItems())
        self._act_edit.setEnabled(has_sel)
        self._act_delete.setEnabled(has_sel)
        self._act_open.setEnabled(has_sel)

    # ------------------------------------------------------------------
    # Domain operations
    # ------------------------------------------------------------------

    def _port_map(self, exclude_domain: str = "") -> dict[int, str]:
        """Return {port: domain} for all stored domains, optionally excluding one."""
        return {
            int(d.get("port", 80)): d.get("domain", "")
            for d in self._store.all().values()
            if d.get("domain", "") != exclude_domain and int(d.get("port", 80)) != 80
        }

    def on_add_domain(self) -> None:
        dlg = AddDomainDialog(
            self,
            validation_service=self._validator,
            default_port=self._settings.default_port,
            existing_domains=self._store.domains(),
            existing_ports=self._port_map(),
            default_doc_root=self._settings.get("default_doc_root", ""),
        )
        if dlg.exec() != AddDomainDialog.DialogCode.Accepted:
            return

        data = {
            "domain":   dlg.domain,
            "doc_root": dlg.doc_root,
            "port":     dlg.port,
            "ssl":      dlg.ssl,
            "notes":    dlg.notes,
        }

        self._apply_changes(
            action="add",
            data=data,
        )

    def on_edit_domain(self) -> None:
        domain = self._selected_domain()
        if not domain:
            return
        existing = self._store.get(domain)
        if not existing:
            return

        other_domains = [d for d in self._store.domains() if d != domain]
        dlg = EditDomainDialog(
            self,
            validation_service=self._validator,
            existing_domains=other_domains,
            existing_ports=self._port_map(exclude_domain=domain),
            domain=existing.get("domain", domain),
            doc_root=existing.get("doc_root", ""),
            port=existing.get("port", 80),
            ssl=existing.get("ssl", False),
            notes=existing.get("notes", ""),
        )
        if dlg.exec() != EditDomainDialog.DialogCode.Accepted:
            return

        new_data = {
            "domain":   dlg.domain,
            "doc_root": dlg.doc_root,
            "port":     dlg.port,
            "ssl":      dlg.ssl,
            "notes":    dlg.notes,
        }
        self._apply_changes(action="edit", data=new_data, old_domain=domain)

    def on_delete_domain(self) -> None:
        domain = self._selected_domain()
        if not domain:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete domain  '{domain}'?\n\n"
            "This will remove it from the hosts file and Apache vhosts config.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._apply_changes(action="delete", data={"domain": domain})

    # ------------------------------------------------------------------
    # Enable / disable toggle
    # ------------------------------------------------------------------

    @staticmethod
    def _style_toggle(btn: QPushButton, enabled: bool) -> None:
        if enabled:
            btn.setText("ON")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #a6e3a1;
                    color: #1e1e2e;
                    border: none;
                    border-radius: 5px;
                    font-size: 10px;
                    font-weight: 700;
                    min-width: 0;
                    padding: 0;
                }
                QPushButton:hover { background-color: #94d49f; }
            """)
        else:
            btn.setText("OFF")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #45475a;
                    color: #a6adc8;
                    border: none;
                    border-radius: 5px;
                    font-size: 10px;
                    font-weight: 700;
                    min-width: 0;
                    padding: 0;
                }
                QPushButton:hover { background-color: #585b70; }
            """)

    def on_toggle_domain(self, domain: str, enabled: bool, btn: QPushButton) -> None:
        self._style_toggle(btn, enabled)

        s = self._settings

        # Backup before modifying
        if s.backup_before_modify:
            try:
                self._backup.backup_file(Path(s.hosts_file), "hosts")
                self._backup.backup_file(Path(s.vhosts_conf), "vhosts")
            except Exception as exc:
                QMessageBox.warning(self, "Backup Failed", f"Could not create backup:\n{exc}")

        try:
            if enabled:
                self._hosts.enable_entry(domain)
                self._vhost.enable_entry(domain)
            else:
                self._hosts.disable_entry(domain)
                self._vhost.disable_entry(domain)

            # Persist enabled state
            data = self._store.get(domain) or {}
            data["enabled"] = enabled
            self._store.update(domain, data)

            # Sync httpd.conf Listen ports from ENABLED domains only
            active_ports = {
                int(d.get("port", 80))
                for d in self._store.all().values()
                if d.get("enabled", True)
            }
            self._httpdconf.sync_ports(active_ports)

        except Exception as exc:
            logger.exception("Toggle failed for %s", domain)
            QMessageBox.critical(self, "Toggle Failed", f"Could not toggle domain:\n{exc}")
            # Revert button state
            self._style_toggle(btn, not enabled)
            btn.setChecked(not enabled)
            return

        self.refresh_table()
        state = "enabled" if enabled else "disabled"
        self._status(f"Domain '{domain}' {state}.")

        if s.auto_restart_apache:
            self.on_restart_apache()

    def on_open_in_browser(self) -> None:
        domain = self._selected_domain()
        if not domain:
            return
        data = self._store.get(domain) or {}
        self._open_url(domain, int(data.get("port", 80)))

    def _open_url(self, domain: str, port: int) -> None:
        url = f"http://{domain}/" if port == 80 else f"http://{domain}:{port}/"

        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        chrome = next((p for p in chrome_paths if Path(p).exists()), None)

        try:
            if chrome:
                subprocess.Popen(
                    [chrome, url],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                )
            else:
                webbrowser.open(url)
            self._status(f"Opened {url}")
        except Exception as exc:
            QMessageBox.warning(self, "Open Failed", f"Could not open browser:\n{exc}")

    # ------------------------------------------------------------------
    # Change pipeline — backup → write → validate → (restart)
    # ------------------------------------------------------------------

    def _apply_changes(
        self,
        action: str,
        data: dict[str, Any],
        old_domain: str | None = None,
    ) -> None:
        domain = data["domain"]
        s = self._settings

        # 1. Backup
        if s.backup_before_modify:
            try:
                self._backup.backup_file(Path(s.hosts_file), "hosts")
                self._backup.backup_file(Path(s.vhosts_conf), "vhosts")
                self._backup.backup_file(Path(s.httpd_conf), "httpdconf")
            except Exception as exc:
                reply = QMessageBox.question(
                    self, "Backup Failed",
                    f"Could not create backup:\n{exc}\n\nContinue anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

        # 2. Write hosts & vhosts
        hosts_ok, vhosts_ok = True, True
        try:
            if action == "add":
                self._hosts.add_entry(domain)
                entry = DomainEntry(
                    domain=domain,
                    doc_root=data["doc_root"],
                    port=data.get("port", 80),
                    ssl=data.get("ssl", False),
                    notes=data.get("notes", ""),
                )
                self._vhost.add_entry(entry)
                self._store.add(data)

            elif action == "edit":
                src = old_domain or domain
                self._hosts.update_entry(src, domain)
                new_entry = DomainEntry(
                    domain=domain,
                    doc_root=data["doc_root"],
                    port=data.get("port", 80),
                    ssl=data.get("ssl", False),
                    notes=data.get("notes", ""),
                )
                self._vhost.update_entry(src, new_entry)
                self._store.update(src, data)

            elif action == "delete":
                self._hosts.remove_entry(domain)
                self._vhost.remove_entry(domain)
                self._store.remove(domain)

        except Exception as exc:
            logger.exception("Failed to write config files")
            QMessageBox.critical(
                self, "Write Error",
                f"Failed to update configuration:\n\n{exc}\n\n"
                "Check that you are running as Administrator.",
            )
            return

        # 2b. Sync Listen ports in httpd.conf — enabled domains only
        try:
            all_ports = {
                int(d.get("port", 80))
                for d in self._store.all().values()
                if d.get("enabled", True)
            }
            self._httpdconf.sync_ports(all_ports)
        except Exception as exc:
            logger.warning("Could not sync httpd.conf ports: %s", exc)
            QMessageBox.warning(
                self, "httpd.conf Warning",
                f"Domains were saved, but Listen ports in httpd.conf could not be updated:\n\n{exc}",
            )

        # 3. Validate Apache config
        if s.validate_before_save:
            self._status("Validating Apache config…")
            QApplication.processEvents()
            ok, msg = self._apache.test_config()
            if not ok:
                QMessageBox.critical(
                    self, "Apache Config Invalid",
                    f"Apache configuration validation failed:\n\n{msg}\n\n"
                    "Your backup has been preserved. "
                    "Restoring from backup is recommended.",
                )
                self._status("⚠ Apache config validation failed — check logs.", error=True)
                self.refresh_table()
                return

        # 4. Refresh UI
        self.refresh_table()

        action_labels = {"add": "added", "edit": "updated", "delete": "deleted"}
        self._status(f"Domain '{domain}' {action_labels.get(action, 'changed')} successfully.")

        # 5. Restart Apache
        if s.auto_restart_apache:
            self.on_restart_apache()

    # ------------------------------------------------------------------
    # Apache controls
    # ------------------------------------------------------------------

    def _apache_busy(self) -> bool:
        return any([
            self._restart_worker and self._restart_worker.isRunning(),
            self._stop_worker    and self._stop_worker.isRunning(),
            self._start_worker   and self._start_worker.isRunning(),
        ])

    def _set_apache_btns(self, enabled: bool) -> None:
        self._act_start.setEnabled(enabled)
        self._act_restart.setEnabled(enabled)
        self._act_stop.setEnabled(enabled)

    def on_start_apache(self) -> None:
        if self._apache_busy():
            return
        self._set_apache_btns(False)
        self._status("Starting Apache…")
        worker = ApacheStartWorker(self._apache)
        worker.finished.connect(self._on_start_done)
        worker.start()
        self._start_worker = worker

    def _on_start_done(self, ok: bool, msg: str) -> None:
        self._set_apache_btns(True)
        if ok:
            self._status(f"Apache started: {msg}")
        else:
            QMessageBox.warning(self, "Apache Start Failed", msg)
            self._status(f"Apache start failed: {msg}", error=True)
        self._refresh_apache_status()

    def on_restart_apache(self) -> None:
        if self._apache_busy():
            return

        self._set_apache_btns(False)
        self._status("Restarting Apache…")

        worker = ApacheRestartWorker(self._apache)
        worker.finished.connect(self._on_restart_done)
        worker.start()
        self._restart_worker = worker

    def _on_restart_done(self, ok: bool, msg: str) -> None:
        self._set_apache_btns(True)
        if ok:
            self._status(f"Apache restarted: {msg}")
            self._refresh_apache_status()
        else:
            QMessageBox.warning(self, "Apache Restart Failed", msg)
            self._status(f"Apache restart failed: {msg}", error=True)

    def on_stop_apache(self) -> None:
        if self._apache_busy():
            return
        self._set_apache_btns(False)
        self._status("Stopping Apache…")

        worker = ApacheStopWorker(self._apache)
        worker.finished.connect(self._on_stop_done)
        worker.start()
        self._stop_worker = worker

    def _on_stop_done(self, ok: bool, msg: str) -> None:
        self._set_apache_btns(True)
        if ok:
            self._status(f"Apache stopped: {msg}")
        else:
            QMessageBox.warning(self, "Apache Stop Failed", msg)
            self._status(f"Apache stop failed: {msg}", error=True)
        self._refresh_apache_status()

    def _refresh_apache_status(self) -> None:
        """Immediate synchronous check — only call from the main thread after an operation."""
        self._update_apache_badge(self._apache.is_running())

    def _restart_poll_timer(self) -> None:
        """Start or restart the periodic status poll based on current settings."""
        self._poll_timer.stop()
        interval = self._settings.status_poll_interval
        if interval > 0:
            self._poll_timer.start(interval * 1000)

    def _poll_apache_status(self) -> None:
        """Timer callback — spawn a background thread so tasklist never blocks the UI."""
        if self._status_worker and self._status_worker.isRunning():
            return  # previous poll still running, skip this tick
        worker = ApacheStatusWorker(self._apache)
        worker.result.connect(self._update_apache_badge)
        worker.start()
        self._status_worker = worker

    def _update_apache_badge(self, running: bool) -> None:
        if running:
            self._apache_badge.setText("● Apache: Running")
            self._apache_badge.setStyleSheet("color: #a6e3a1; font-size: 12px;")
        else:
            self._apache_badge.setText("● Apache: Stopped")
            self._apache_badge.setStyleSheet("color: #f38ba8; font-size: 12px;")

    # ------------------------------------------------------------------
    # Other toolbar actions
    # ------------------------------------------------------------------

    def on_open_settings(self) -> None:
        dlg = SettingsDialog(self, settings=self._settings)
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            self._reinit_services()
            self._restart_poll_timer()
            self._status("Settings saved.")

    def on_open_config_dir(self) -> None:
        config_dir = Path(__file__).resolve().parent.parent / "config"
        os.startfile(str(config_dir))

    def on_backup_now(self) -> None:
        s = self._settings
        errors: list[str] = []
        for label, path in [
            ("hosts",     s.hosts_file),
            ("vhosts",    s.vhosts_conf),
            ("httpdconf", s.httpd_conf),
        ]:
            try:
                p = self._backup.backup_file(Path(path), label)
                logger.info("Manual backup: %s", p)
            except Exception as exc:
                errors.append(f"{label}: {exc}")

        if errors:
            QMessageBox.warning(self, "Backup Warning", "\n".join(errors))
        else:
            QMessageBox.information(self, "Backup Created", "Backup files created successfully.")
            self._status("Backup created.")

    def on_restore_backup(self) -> None:
        s = self._settings
        dlg = RestoreDialog(
            self,
            backup_service=self._backup,
            hosts_path=s.hosts_file,
            vhosts_path=s.vhosts_conf,
            httpdconf_path=s.httpd_conf,
        )
        dlg.exec()

    # ------------------------------------------------------------------
    # Startup checks
    # ------------------------------------------------------------------

    def _check_config_paths(self) -> None:
        s = self._settings
        problems: list[str] = []

        if not Path(s.apache_bin).exists():
            problems.append(f"Apache binary not found:\n  {s.apache_bin}")
        if not Path(s.vhosts_conf).exists():
            problems.append(f"VHosts config not found:\n  {s.vhosts_conf}")
        if not Path(s.httpd_conf).exists():
            problems.append(f"httpd.conf not found:\n  {s.httpd_conf}")
        if not Path(s.hosts_file).exists():
            problems.append(f"Hosts file not found:\n  {s.hosts_file}")

        if problems:
            QMessageBox.warning(
                self,
                "Configuration Required",
                "Some paths are not configured correctly:\n\n"
                + "\n\n".join(problems)
                + "\n\nOpen Settings to fix them before adding domains.",
            )

        self._refresh_apache_status()

    # ------------------------------------------------------------------
    # Status bar helper
    # ------------------------------------------------------------------

    def _status(self, msg: str, error: bool = False) -> None:
        color = "#f38ba8" if error else "#a6adc8"
        self._status_label.setStyleSheet(f"color: {color};")
        self._status_label.setText(msg)
        logger.info("Status: %s", msg)
