APP_STYLE = """
QMainWindow, QWidget { background: #0b1220; color: #e8eef8; font-family: 'Segoe UI'; font-size: 10pt; }
QFrame#Sidebar { background: #101a2d; border: none; }
QWidget#DividerHost { background: #0b1220; }
QFrame#ContentDivider {
    border: none;
    border-radius: 1px;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 rgba(85, 221, 177, 0),
        stop: 0.08 rgba(85, 221, 177, 95),
        stop: 0.28 rgba(50, 155, 226, 210),
        stop: 0.72 rgba(85, 221, 177, 190),
        stop: 0.92 rgba(85, 221, 177, 95),
        stop: 1 rgba(85, 221, 177, 0)
    );
}
QLabel#Brand { color: white; font-size: 17pt; font-weight: 700; padding: 18px 12px; }
QLabel#PageTitle { color: white; font-size: 22pt; font-weight: 700; }
QLabel#Subtitle { color: #9eabc0; font-size: 10pt; }
QLabel#VersionLabel { color: #61748f; font-size: 8.5pt; }
QMenuBar { background: #0d1728; color: #c9d4e5; border-bottom: 1px solid #203452; }
QMenuBar::item:selected, QMenu::item:selected { background: #203452; color: #55ddb1; }
QMenu { background: #111c2f; color: #e8eef8; border: 1px solid #2c3d5a; }
QPushButton { background: #1d2a42; border: 1px solid #334866; border-radius: 7px; padding: 8px 12px; }
QPushButton:hover { background: #263854; }
QPushButton:pressed { background: #18243a; }
QPushButton#Primary { background: #1f9f79; color: #071611; border: none; font-weight: 700; padding: 10px 16px; }
QPushButton#Primary:hover { background: #28c394; }
QPushButton#Danger { background: #762f42; border-color: #a64860; }
QPushButton#StopButton { background: #d33f55; color: white; border: none; font-size: 12pt; font-weight: 700; padding: 12px; }
QPushButton#Nav { text-align: left; border: none; background: transparent; color: #aebbd0; padding: 10px 16px; border-radius: 0; }
QPushButton#Nav:hover { background: #182641; color: white; }
QPushButton#Nav:checked { background: #203452; color: #55ddb1; border-left: 3px solid #55ddb1; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit, QListWidget, QTableWidget {
    background: #111c2f; border: 1px solid #2c3d5a; border-radius: 6px; padding: 6px; selection-background-color: #267a68;
}
QHeaderView::section { background: #17253c; color: #c9d4e5; border: none; padding: 7px; }
QTableWidget { gridline-color: #263650; }
QGroupBox { border: 1px solid #2c3d5a; border-radius: 8px; margin-top: 12px; padding-top: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QProgressBar { background: #101a2d; border: 1px solid #2c3d5a; border-radius: 6px; text-align: center; }
QProgressBar::chunk { background: #1f9f79; border-radius: 5px; }
QSlider::groove:horizontal { height: 6px; background: #263650; border-radius: 3px; }
QSlider::handle:horizontal { background: #55ddb1; width: 16px; margin: -5px 0; border-radius: 8px; }
"""
