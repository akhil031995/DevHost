"""
Application-wide stylesheet — dark professional developer theme.
"""

# Colour palette
C_BG = "#1e1e2e"          # main background
C_BG2 = "#181825"         # sidebar / panel backgrounds
C_BG3 = "#313244"         # card / hover backgrounds
C_ACCENT = "#89b4fa"      # blue accent (Catppuccin Mocha)
C_ACCENT2 = "#cba6f7"     # purple accent
C_GREEN = "#a6e3a1"
C_RED = "#f38ba8"
C_YELLOW = "#f9e2af"
C_TEXT = "#cdd6f4"        # primary text
C_TEXT2 = "#a6adc8"       # secondary / muted text
C_BORDER = "#45475a"      # subtle borders
C_INPUT = "#262637"       # input background

MAIN_STYLESHEET = f"""
/* ── Global ───────────────────────────────────────────────── */
* {{
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    color: {C_TEXT};
}}

QMainWindow, QDialog, QWidget {{
    background-color: {C_BG};
}}

/* ── Tool bar ─────────────────────────────────────────────── */
QToolBar {{
    background-color: {C_BG2};
    border-bottom: 1px solid {C_BORDER};
    padding: 4px 8px;
    spacing: 4px;
}}

QToolBar QToolButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 12px;
    color: {C_TEXT};
    font-weight: 500;
}}

QToolBar QToolButton:hover {{
    background-color: {C_BG3};
    border-color: {C_BORDER};
}}

QToolBar QToolButton:pressed {{
    background-color: {C_ACCENT};
    color: {C_BG};
}}

QToolBar::separator {{
    background: {C_BORDER};
    width: 1px;
    margin: 6px 4px;
}}

/* ── Table ────────────────────────────────────────────────── */
QTableWidget {{
    background-color: {C_BG2};
    alternate-background-color: {C_BG};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    gridline-color: {C_BORDER};
    selection-background-color: {C_BG3};
    selection-color: {C_TEXT};
    outline: none;
}}

QTableWidget::item {{
    padding: 8px 12px;
    border: none;
}}

QTableWidget::item:selected {{
    background-color: {C_BG3};
    color: {C_TEXT};
}}

QHeaderView::section {{
    background-color: {C_BG2};
    color: {C_TEXT2};
    border: none;
    border-bottom: 1px solid {C_BORDER};
    border-right: 1px solid {C_BORDER};
    padding: 8px 12px;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QHeaderView::section:last {{
    border-right: none;
}}

/* ── Push buttons ─────────────────────────────────────────── */
QPushButton {{
    background-color: {C_BG3};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 500;
    min-width: 80px;
}}

QPushButton:hover {{
    background-color: {C_ACCENT};
    color: {C_BG};
    border-color: {C_ACCENT};
}}

QPushButton:pressed {{
    background-color: {C_ACCENT2};
    color: {C_BG};
}}

QPushButton:disabled {{
    color: {C_BORDER};
    background-color: {C_BG2};
    border-color: {C_BG2};
}}

QPushButton#btn_primary {{
    background-color: {C_ACCENT};
    color: {C_BG};
    border: none;
    font-weight: 600;
}}

QPushButton#btn_primary:hover {{
    background-color: {C_ACCENT2};
}}

QPushButton#btn_danger {{
    background-color: transparent;
    color: {C_RED};
    border-color: {C_RED};
}}

QPushButton#btn_danger:hover {{
    background-color: {C_RED};
    color: {C_BG};
}}

QPushButton#btn_success {{
    background-color: transparent;
    color: {C_GREEN};
    border-color: {C_GREEN};
}}

QPushButton#btn_success:hover {{
    background-color: {C_GREEN};
    color: {C_BG};
}}

/* ── Inputs ───────────────────────────────────────────────── */
QLineEdit, QTextEdit, QSpinBox, QComboBox {{
    background-color: {C_INPUT};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {C_TEXT};
    selection-background-color: {C_ACCENT};
    selection-color: {C_BG};
}}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {C_ACCENT};
}}

QLineEdit:read-only {{
    background-color: {C_BG2};
    color: {C_TEXT2};
}}

QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {C_BG3};
    border: none;
    width: 18px;
}}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {C_ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {C_INPUT};
    border: 1px solid {C_BORDER};
    selection-background-color: {C_ACCENT};
    selection-color: {C_BG};
    outline: none;
}}

/* ── Labels ───────────────────────────────────────────────── */
QLabel {{
    color: {C_TEXT};
    background: transparent;
}}

QLabel#label_muted {{
    color: {C_TEXT2};
    font-size: 12px;
}}

QLabel#label_accent {{
    color: {C_ACCENT};
    font-weight: 600;
}}

/* ── Status bar ───────────────────────────────────────────── */
QStatusBar {{
    background-color: {C_BG2};
    border-top: 1px solid {C_BORDER};
    color: {C_TEXT2};
    font-size: 12px;
    padding: 2px 8px;
}}

/* ── Scroll bars ──────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {C_BG2};
    width: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {C_BORDER};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {C_TEXT2};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {C_BG2};
    height: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background: {C_BORDER};
    border-radius: 4px;
    min-width: 20px;
}}

/* ── Check box ────────────────────────────────────────────── */
QCheckBox {{
    spacing: 8px;
    color: {C_TEXT};
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    background: {C_INPUT};
}}

QCheckBox::indicator:checked {{
    background: {C_ACCENT};
    border-color: {C_ACCENT};
}}

/* ── Group box ────────────────────────────────────────────── */
QGroupBox {{
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    color: {C_TEXT2};
    font-weight: 600;
    font-size: 12px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {C_TEXT2};
}}

/* ── Message box ──────────────────────────────────────────── */
QMessageBox {{
    background-color: {C_BG};
}}

QMessageBox QPushButton {{
    min-width: 90px;
}}

/* ── Tab widget ───────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    background: {C_BG2};
}}

QTabBar::tab {{
    background: {C_BG};
    border: 1px solid {C_BORDER};
    padding: 6px 16px;
    border-radius: 4px 4px 0 0;
    color: {C_TEXT2};
}}

QTabBar::tab:selected {{
    background: {C_BG2};
    color: {C_TEXT};
    border-bottom-color: {C_BG2};
}}

/* ── Tooltip ──────────────────────────────────────────────── */
QToolTip {{
    background-color: {C_BG3};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
}}

/* ── Splitter ─────────────────────────────────────────────── */
QSplitter::handle {{
    background: {C_BORDER};
}}
"""

# Badge-style colours for status column
STATUS_COLORS = {
    "active":   (C_GREEN,  C_BG),
    "inactive": (C_BORDER, C_TEXT2),
    "error":    (C_RED,    C_BG),
    "warning":  (C_YELLOW, C_BG),
}
