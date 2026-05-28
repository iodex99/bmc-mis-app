"""Settings / About page — version info + in-app updater."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, config
from ..services import updater


# --- worker threads ----------------------------------------------------------

class _CheckWorker(QObject):
    finished = Signal(object, str)   # info | None, error message

    def run(self) -> None:
        try:
            info = updater.check_latest()
            self.finished.emit(info, "")
        except Exception as exc:
            self.finished.emit(None, str(exc))


class _DownloadWorker(QObject):
    progress = Signal(int)           # 0..100
    finished = Signal(object, str)   # new_dir Path | None, error message

    def __init__(self, info: updater.UpdateInfo) -> None:
        super().__init__()
        self.info = info

    def run(self) -> None:
        try:
            def _p(done, total):
                self.progress.emit(int(done * 100 / total) if total else 0)
            new_dir = updater.download_update(self.info, _p)
            self.finished.emit(new_dir, "")
        except Exception as exc:
            self.finished.emit(None, str(exc))


# --- page --------------------------------------------------------------------

class SettingsPage(QWidget):
    """Version, update controls, data folder path."""

    update_state_changed = Signal(object)     # UpdateInfo | None

    def __init__(self) -> None:
        super().__init__()
        self._latest: updater.UpdateInfo | None = None
        self._thread: QThread | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        heading = QLabel("Settings")
        heading.setObjectName("pageHeading")
        root.addWidget(heading)
        root.addWidget(QLabel("App information, updates and data location.",
                              objectName="pageNote"))

        # --- about box -----------------------------------------------------
        about = QGroupBox("About")
        a = QVBoxLayout(about)
        a.addWidget(QLabel(
            f"<b>{config.APP_NAME}</b><br>"
            f"Version <b>{__version__}</b>"))
        a.addWidget(QLabel(
            f"Data folder: <code>{config.DATA_DIR}</code><br>"
            f"<span style='color:#64748B;'>"
            "(your database and generated reports — updates never touch this)"
            "</span>"))
        root.addWidget(about)

        # --- update box ----------------------------------------------------
        upd = QGroupBox("Updates")
        u = QVBoxLayout(upd)

        if not updater.UPDATES_ENABLED:
            u.addWidget(QLabel(
                "<span style='color:#94A3B8;'>"
                "Auto-updater not configured for this build."
                "</span>"))
        else:
            self.status_label = QLabel("Click below to check for a new version.")
            u.addWidget(self.status_label)

            self.notes = QTextBrowser()
            self.notes.setVisible(False)
            self.notes.setMaximumHeight(180)
            u.addWidget(self.notes)

            self.progress = QProgressBar()
            self.progress.setVisible(False)
            u.addWidget(self.progress)

            row = QHBoxLayout()
            self.check_btn = QPushButton("Check for updates")
            self.install_btn = QPushButton("Install update")
            self.install_btn.setObjectName("primary")
            self.install_btn.setVisible(False)
            self.check_btn.clicked.connect(self.check_now)
            self.install_btn.clicked.connect(self._install)
            row.addWidget(self.check_btn)
            row.addWidget(self.install_btn)
            row.addStretch(1)
            u.addLayout(row)

            self.auto_check = QCheckBox(
                "Check automatically on launch (recommended)")
            self.auto_check.setChecked(updater.auto_check_enabled())
            self.auto_check.toggled.connect(updater.set_auto_check)
            u.addWidget(self.auto_check)

        root.addWidget(upd)
        root.addStretch(1)

    # -- update flow ---------------------------------------------------------
    def offer_update(self, info: updater.UpdateInfo) -> None:
        """Display an available update (called from background auto-check)."""
        if not updater.UPDATES_ENABLED:
            return
        self._latest = info
        self.status_label.setText(
            f"<b>Update available:</b> v{info.version} "
            f"(you have v{__version__}).")
        self.notes.setMarkdown(info.notes or "_No release notes provided._")
        self.notes.setVisible(True)
        self.install_btn.setVisible(True)
        self.update_state_changed.emit(info)

    def check_now(self) -> None:
        if self._thread is not None:
            return
        self.check_btn.setEnabled(False)
        self.status_label.setText("Checking…")
        self.notes.setVisible(False)
        self.install_btn.setVisible(False)
        self._run_thread(_CheckWorker(), self._on_check_finished)

    def _on_check_finished(self, info, error: str) -> None:
        self.check_btn.setEnabled(True)
        self._cleanup_thread()
        if error:
            self.status_label.setText(f"<span style='color:#B91C1C;'>"
                                      f"Couldn't check: {error}</span>")
            return
        if info is None:
            self.status_label.setText(
                f"You're up to date (v{__version__}).")
            self._latest = None
            self.update_state_changed.emit(None)
            return
        self.offer_update(info)

    def _install(self) -> None:
        if not self._latest:
            return
        if QMessageBox.question(
                self, "Install update",
                f"Download and install v{self._latest.version}?\n\n"
                "The app will close and relaunch automatically. Your data "
                "will not be affected.") != QMessageBox.Yes:
            return
        self.install_btn.setEnabled(False)
        self.check_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status_label.setText("Downloading update…")

        worker = _DownloadWorker(self._latest)
        worker.progress.connect(self.progress.setValue)
        self._run_thread(worker, self._on_download_finished)

    def _on_download_finished(self, new_dir, error: str) -> None:
        self._cleanup_thread()
        if error:
            self.progress.setVisible(False)
            self.install_btn.setEnabled(True)
            self.check_btn.setEnabled(True)
            QMessageBox.critical(self, "Update failed",
                                 f"Could not download the update.\n\n{error}")
            self.status_label.setText("<span style='color:#B91C1C;'>"
                                      "Update download failed.</span>")
            return
        self.status_label.setText("Installing — the app will restart…")
        try:
            updater.apply_update(new_dir)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Update failed", str(exc))
            self.install_btn.setEnabled(True)
            self.check_btn.setEnabled(True)

    # -- thread plumbing -----------------------------------------------------
    def _run_thread(self, worker: QObject, on_finished) -> None:
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        self._thread = thread

    def _cleanup_thread(self) -> None:
        self._thread = None
