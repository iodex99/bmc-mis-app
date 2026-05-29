"""The main application window: a navigation sidebar plus stacked pages."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QSize, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, config
from ..services import updater
from .dashboard_page import DashboardPage
from .generate_page import GeneratePage
from .import_page import ImportPage
from .master_data import MasterDataPage
from .review_page import ReviewPage
from .settings_page import SettingsPage

# Each nav entry: (label, page-factory). Real pages replace the placeholders
# as later phases are built.
NAV_ITEMS = [
    ("Dashboard", DashboardPage),
    ("Import Files", ImportPage),
    ("Review & Map", ReviewPage),
    ("Master Data", MasterDataPage),
    ("Generate MIS", GeneratePage),
    ("Settings", SettingsPage),
]
NAV_ITEMS_INDEX = {label: i for i, (label, _f) in enumerate(NAV_ITEMS)}


class MainWindow(QMainWindow):
    """Top-level window hosting the sidebar navigation and page stack."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self.resize(1280, 800)
        self.setMinimumSize(1100, 680)

        central = QWidget()
        central.setObjectName("central")
        central.setAutoFillBackground(True)
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        for _label, factory in NAV_ITEMS:
            self.stack.addWidget(factory())

        content = QWidget()
        content.setObjectName("content")
        content.setAutoFillBackground(True)
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(28, 22, 28, 18)
        content_lay.setSpacing(0)
        content_lay.addWidget(self.stack)

        root.addWidget(self._build_sidebar())
        root.addWidget(content, 1)

        self.nav.setCurrentRow(0)

        # Status bar: version on the left, update pill (when available) right.
        self.statusBar().showMessage(
            f"{config.APP_SHORT} v{__version__}  ·  Data: {config.DB_PATH}")
        self.update_pill = QPushButton("")
        self.update_pill.setObjectName("updatePill")
        self.update_pill.setCursor(Qt.PointingHandCursor)
        self.update_pill.setVisible(False)
        self.update_pill.clicked.connect(self._go_to_settings)
        self.statusBar().addPermanentWidget(self.update_pill)

        # The Settings page emits whenever its update state changes.
        self._settings_page = self.stack.widget(NAV_ITEMS_INDEX["Settings"])
        self._settings_page.update_state_changed.connect(self._set_update_state)

        # The Dashboard's quick-action cards emit a nav index to jump to.
        dashboard = self.stack.widget(NAV_ITEMS_INDEX["Dashboard"])
        if hasattr(dashboard, "navigate"):
            dashboard.navigate.connect(self.nav.setCurrentRow)

        # Silent auto-check on launch (off the UI thread, fail-quietly).
        self._auto_check_thread: QThread | None = None
        self._auto_check_worker: QObject | None = None
        if updater.auto_check_enabled():
            self._start_auto_check()

    def _start_auto_check(self) -> None:
        worker = _SilentCheck()
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_silent_check)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        # Keep Python references alive until the thread emits finished
        # (otherwise PySide6 may garbage-collect the worker and lose the
        # signal silently).
        self._auto_check_thread = thread
        self._auto_check_worker = worker
        thread.start()

    def _on_silent_check(self, info) -> None:
        self._auto_check_thread = None
        self._auto_check_worker = None
        if info is not None:
            self._settings_page.offer_update(info)

    def _set_update_state(self, info) -> None:
        if info is None:
            self.update_pill.setVisible(False)
            return
        self.update_pill.setText(f"  ●  Update available: v{info.version}  ")
        self.update_pill.setVisible(True)

    def _go_to_settings(self) -> None:
        self.nav.setCurrentRow(NAV_ITEMS_INDEX["Settings"])

    def _build_sidebar(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("sidebar")
        panel.setFixedWidth(232)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand = QLabel(
            "<div style='font-size:15px;font-weight:700;color:white;'>"
            "Bilimoria Mehta &amp; Co.</div>"
            "<div style='font-size:10px;color:#94A3B8;margin-top:6px;"
            "letter-spacing:2px;'>MIS&nbsp;&nbsp;GENERATOR</div>")
        brand.setObjectName("brand")
        brand.setTextFormat(Qt.RichText)
        brand.setAlignment(Qt.AlignCenter)
        layout.addWidget(brand)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFrameShape(QListWidget.NoFrame)
        for label, _factory in NAV_ITEMS:
            item = QListWidgetItem(label)
            item.setSizeHint(QSize(0, 46))
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        layout.addWidget(self.nav, 1)

        return panel


class _SilentCheck(QObject):
    """Background worker that quietly asks GitHub for the latest version."""
    finished = Signal(object)

    def run(self) -> None:
        try:
            info = updater.check_latest()
        except Exception:
            info = None
        self.finished.emit(info)
