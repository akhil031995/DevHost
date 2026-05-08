"""
Settings dialog — tabbed layout grouped by function.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
    QCheckBox, QFileDialog, QComboBox, QMessageBox, QTabWidget, QWidget,
)

from services.settings_service import SettingsService


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings: SettingsService | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(660)
        self.setMinimumHeight(400)
        self.setModal(True)
        self._build_ui()
        if settings:
            self._load_settings()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Application Settings")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #89b4fa;")
        root.addWidget(title)

        tabs = QTabWidget()
        root.addWidget(tabs)

        tabs.addTab(self._tab_apache(),    "Apache")
        tabs.addTab(self._tab_paths(),     "Paths")
        tabs.addTab(self._tab_behaviour(), "Behaviour")
        tabs.addTab(self._tab_timeouts(),  "Timeouts")

        # ── Buttons ───────────────────────────────────────────────────
        buttons = QDialogButtonBox()
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("btn_primary")
        save_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setObjectName("btn_danger")

        buttons.addButton(save_btn,   QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.addButton(reset_btn,  QDialogButtonBox.ButtonRole.ResetRole)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        reset_btn.clicked.connect(self._on_reset)
        root.addWidget(buttons)

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _tab_apache(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(14)

        grp = QGroupBox("Web Server")
        form = QFormLayout(grp)
        form.setSpacing(10)
        form.setContentsMargins(12, 16, 12, 12)

        self.server_type = QComboBox()
        self.server_type.addItems(["xampp", "wamp", "laragon", "custom"])
        form.addRow("Server Type", self.server_type)

        self.apache_bin  = self._path_row(form, "Apache Binary (httpd.exe) *", file=True)
        self.service_name = QLineEdit()
        self.service_name.setPlaceholderText("Optional — leave blank if not running as a service")
        form.addRow("Windows Service Name", self.service_name)

        layout.addWidget(grp)
        layout.addStretch()
        return w

    def _tab_paths(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(14)

        conf_grp = QGroupBox("Config Files")
        conf_form = QFormLayout(conf_grp)
        conf_form.setSpacing(10)
        conf_form.setContentsMargins(12, 16, 12, 12)
        self.vhosts_conf = self._path_row(conf_form, "VHosts Config File *",       file=True)
        self.httpd_conf  = self._path_row(conf_form, "httpd.conf (main config) *", file=True)
        layout.addWidget(conf_grp)

        hosts_grp = QGroupBox("Windows Hosts File")
        hosts_form = QFormLayout(hosts_grp)
        hosts_form.setSpacing(10)
        hosts_form.setContentsMargins(12, 16, 12, 12)
        self.hosts_file = self._path_row(hosts_form, "Hosts File Path *", file=True)
        layout.addWidget(hosts_grp)

        defaults_grp = QGroupBox("Defaults for New Domains")
        defaults_form = QFormLayout(defaults_grp)
        defaults_form.setSpacing(10)
        defaults_form.setContentsMargins(12, 16, 12, 12)

        self.default_port = QSpinBox()
        self.default_port.setRange(1, 65535)
        self.default_port.setValue(80)
        self.default_port.setFixedWidth(100)
        defaults_form.addRow("Default Port", self.default_port)

        self.default_doc_root = self._path_row(defaults_form, "Default Document Root")
        layout.addWidget(defaults_grp)

        layout.addStretch()
        return w

    def _tab_behaviour(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(14)

        grp = QGroupBox("Behaviour")
        form = QFormLayout(grp)
        form.setSpacing(10)
        form.setContentsMargins(12, 16, 12, 12)

        self.auto_restart        = QCheckBox("Auto-restart Apache after changes")
        self.validate_before_save = QCheckBox("Validate Apache config before saving")
        self.backup_before_modify = QCheckBox("Create backup before modifications")
        form.addRow("", self.auto_restart)
        form.addRow("", self.validate_before_save)
        form.addRow("", self.backup_before_modify)

        self.max_backups = QSpinBox()
        self.max_backups.setRange(1, 100)
        self.max_backups.setValue(20)
        self.max_backups.setFixedWidth(80)
        form.addRow("Max Backups to Keep", self.max_backups)

        self.poll_interval = QSpinBox()
        self.poll_interval.setRange(0, 300)
        self.poll_interval.setValue(5)
        self.poll_interval.setFixedWidth(80)
        self.poll_interval.setSuffix(" sec")
        self.poll_interval.setSpecialValueText("Disabled")
        form.addRow("Apache Status Poll Interval", self.poll_interval)

        layout.addWidget(grp)
        layout.addStretch()
        return w

    def _tab_timeouts(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(14)

        grp = QGroupBox("Apache Operation Timeouts")
        form = QFormLayout(grp)
        form.setSpacing(10)
        form.setContentsMargins(12, 16, 12, 12)

        def _sb(default: int, max_val: int = 300) -> QSpinBox:
            sb = QSpinBox()
            sb.setRange(5, max_val)
            sb.setValue(default)
            sb.setFixedWidth(90)
            sb.setSuffix(" sec")
            return sb

        self.timeout_start_bat  = _sb(60)
        self.timeout_stop_bat   = _sb(30)
        self.timeout_start_poll = _sb(10, 60)
        self.timeout_service    = _sb(30)

        form.addRow("Start bat timeout",       self.timeout_start_bat)
        form.addRow("Stop bat timeout",        self.timeout_stop_bat)
        form.addRow("Start poll timeout",      self.timeout_start_poll)
        form.addRow("Windows service timeout", self.timeout_service)

        layout.addWidget(grp)
        layout.addStretch()
        return w

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _path_row(self, form: QFormLayout, label: str, file: bool = False) -> QLineEdit:
        row = QHBoxLayout()
        edit = QLineEdit()
        row.addWidget(edit)
        btn = QPushButton("…")
        btn.setFixedWidth(32)
        if file:
            btn.clicked.connect(lambda: self._browse_file(edit))
        else:
            btn.clicked.connect(lambda: self._browse_dir(edit))
        row.addWidget(btn)
        form.addRow(label, row)
        return edit

    def _browse_file(self, target: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select File", target.text() or "C:\\")
        if path:
            target.setText(path)

    def _browse_dir(self, target: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Directory", target.text() or "C:\\")
        if path:
            target.setText(path)

    # ------------------------------------------------------------------
    # Load / Save / Reset
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        s = self._settings
        idx = self.server_type.findText(s.get("server_type", "xampp"))
        self.server_type.setCurrentIndex(max(0, idx))
        self.apache_bin.setText(s.get("apache_bin", ""))
        self.service_name.setText(s.get("apache_service_name", ""))
        self.vhosts_conf.setText(s.get("vhosts_conf", ""))
        self.httpd_conf.setText(s.get("httpd_conf", ""))
        self.hosts_file.setText(s.get("hosts_file", ""))
        self.default_port.setValue(int(s.get("default_port", 80)))
        self.default_doc_root.setText(s.get("default_doc_root", ""))
        self.auto_restart.setChecked(bool(s.get("auto_restart_apache", True)))
        self.validate_before_save.setChecked(bool(s.get("validate_before_save", True)))
        self.backup_before_modify.setChecked(bool(s.get("backup_before_modify", True)))
        self.max_backups.setValue(int(s.get("max_backups", 20)))
        self.poll_interval.setValue(int(s.get("status_poll_interval", 5)))
        self.timeout_start_bat.setValue(int(s.get("timeout_start_bat", 60)))
        self.timeout_stop_bat.setValue(int(s.get("timeout_stop_bat", 30)))
        self.timeout_start_poll.setValue(int(s.get("timeout_start_poll", 10)))
        self.timeout_service.setValue(int(s.get("timeout_service", 30)))

    def _on_save(self) -> None:
        if not self._settings:
            self.accept()
            return
        self._settings.update({
            "server_type":          self.server_type.currentText(),
            "apache_bin":           self.apache_bin.text().strip(),
            "apache_service_name":  self.service_name.text().strip(),
            "vhosts_conf":          self.vhosts_conf.text().strip(),
            "httpd_conf":           self.httpd_conf.text().strip(),
            "hosts_file":           self.hosts_file.text().strip(),
            "default_port":         self.default_port.value(),
            "default_doc_root":     self.default_doc_root.text().strip(),
            "auto_restart_apache":  self.auto_restart.isChecked(),
            "validate_before_save": self.validate_before_save.isChecked(),
            "backup_before_modify": self.backup_before_modify.isChecked(),
            "max_backups":          self.max_backups.value(),
            "status_poll_interval": self.poll_interval.value(),
            "timeout_start_bat":    self.timeout_start_bat.value(),
            "timeout_stop_bat":     self.timeout_stop_bat.value(),
            "timeout_start_poll":   self.timeout_start_poll.value(),
            "timeout_service":      self.timeout_service.value(),
        })
        self.accept()

    def _on_reset(self) -> None:
        reply = QMessageBox.question(
            self, "Reset Settings",
            "Reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes and self._settings:
            self._settings.reset_to_defaults()
            self._load_settings()
