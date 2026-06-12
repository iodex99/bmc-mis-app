"""Settings / About page — version info + in-app updater."""

from __future__ import annotations

import queue
import threading

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, config
from ..importing import tally_client
from ..services import updater


# --- page --------------------------------------------------------------------

class SettingsPage(QWidget):
    """Version, update controls, data folder path."""

    update_state_changed = Signal(object)     # UpdateInfo | None

    def __init__(self) -> None:
        super().__init__()
        self._latest: updater.UpdateInfo | None = None
        self._bg_thread: threading.Thread | None = None
        self._bg_timer: QTimer | None = None

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

        # --- Tally connection -----------------------------------------------
        tally_box = QGroupBox("Tally connection")
        tly = QVBoxLayout(tally_box)
        tly.addWidget(QLabel(
            "Address of the Tally HTTP gateway on this PC. Default "
            "<code>http://localhost:9000</code> works for almost everyone; "
            "change only if Tally is configured for a non-default port or "
            "running on another machine on the LAN."))
        tly_row = QHBoxLayout()
        tly_row.addWidget(QLabel("Tally URL:"))
        self.tally_url_edit = QLineEdit(tally_client.get_tally_url())
        self.tally_url_edit.setPlaceholderText(tally_client.DEFAULT_TALLY_URL)
        tly_row.addWidget(self.tally_url_edit, 1)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_tally_url)
        tly_row.addWidget(save_btn)
        tly.addLayout(tly_row)
        self.tally_status = QLabel("")
        self.tally_status.setWordWrap(True)
        tly.addWidget(self.tally_status)
        root.addWidget(tally_box)

        # --- danger zone ----------------------------------------------------
        danger = QGroupBox("Danger zone")
        danger.setObjectName("dangerZone")
        d = QVBoxLayout(danger)
        d.addWidget(QLabel(
            "Permanently delete every imported voucher, timesheet and salary "
            "row, so a stale import can be redone from scratch. Master data "
            "(entities, cost centres, managers, clients, employees, "
            "services, targets, saved CC-string mappings, column templates) "
            "is preserved. This cannot be undone."))
        reset_row = QHBoxLayout()
        reset_btn = QPushButton("Clear all data…")
        reset_btn.setObjectName("danger")
        reset_btn.clicked.connect(self._reset_all)
        open_folder_btn = QPushButton("Open data folder")
        open_folder_btn.clicked.connect(self._open_data_folder)
        reset_row.addWidget(open_folder_btn)
        reset_row.addStretch(1)
        reset_row.addWidget(reset_btn)
        d.addLayout(reset_row)
        root.addWidget(danger)

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
        if self._bg_timer is not None:
            return
        self.check_btn.setEnabled(False)
        self.status_label.setText("Checking…")
        self.notes.setVisible(False)
        self.install_btn.setVisible(False)
        self._run_bg(lambda _report: updater.check_latest(),
                     self._on_check_finished)

    def _on_check_finished(self, info, error: str) -> None:
        self.check_btn.setEnabled(True)
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
        if not self._latest or self._bg_timer is not None:
            return
        if QMessageBox.question(
                self, "Install update",
                f"Download and install v{self._latest.version}?\n\n"
                "The app will close and reopen by itself in a few "
                "seconds. Your data will not be affected.") != QMessageBox.Yes:
            return
        self.install_btn.setEnabled(False)
        self.check_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status_label.setText("Downloading update…")

        info = self._latest

        def work(report):
            return updater.download_update(
                info,
                lambda done, total: report(
                    int(done * 100 / total) if total else 0))

        self._run_bg(work, self._on_download_finished)

    def _on_download_finished(self, new_dir, error: str) -> None:
        if error:
            self.progress.setVisible(False)
            self.install_btn.setEnabled(True)
            self.check_btn.setEnabled(True)
            QMessageBox.critical(self, "Update failed",
                                 f"Could not download the update.\n\n{error}")
            self.status_label.setText("<span style='color:#B91C1C;'>"
                                      "Update download failed.</span>")
            return
        self.status_label.setText(
            "Installing — the app will close and reopen by itself…")
        QApplication.processEvents()
        try:
            updater.apply_update(new_dir)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Update failed", str(exc))
            self.install_btn.setEnabled(True)
            self.check_btn.setEnabled(True)

    # -- danger zone ---------------------------------------------------------
    def _reset_all(self) -> None:
        first = QMessageBox.warning(
            self, "Clear all data?",
            "<b>This will permanently delete:</b>"
            "<ul>"
            "<li>All imported vouchers and their splits</li>"
            "<li>All imported timesheet rows</li>"
            "<li>All imported salary rows</li>"
            "<li>The import-batch history</li>"
            "</ul>"
            "<b>This will be preserved:</b>"
            "<ul>"
            "<li>Master Data — entities, cost centres, managers, "
            "<b>clients</b>, <b>employees</b>, services, annual targets, "
            "and every alias / mapping you've curated.</li>"
            "<li>Saved CC-string mappings (partner + manager resolutions "
            "from the Review tab).</li>"
            "<li>Column-mapping templates and app settings.</li>"
            "</ul>"
            "<p><b>This cannot be undone.</b></p>",
            QMessageBox.Cancel | QMessageBox.Yes, QMessageBox.Cancel)
        if first != QMessageBox.Yes:
            return

        text, ok = QInputDialog.getText(
            self, "Final confirmation",
            "Type <b>RESET</b> (capitals) to confirm:",
            QLineEdit.Normal)
        if not ok or text.strip() != "RESET":
            QMessageBox.information(self, "Cancelled", "No changes made.")
            return

        from ..services.reset import reset_all_data
        try:
            reset_all_data()
        except Exception as exc:
            QMessageBox.critical(
                self, "Reset failed",
                f"Could not clear data:\n\n{exc}")
            return

        QMessageBox.information(
            self, "Done",
            "All data cleared. The app will close now — relaunch to start "
            "fresh.")
        QApplication.instance().quit()

    def _save_tally_url(self) -> None:
        url = self.tally_url_edit.text().strip()
        tally_client.set_tally_url(url)
        if tally_client.ping(timeout=2.0):
            self.tally_status.setText(
                f"<span style='color:#1B7A1B;'>"
                f"Saved. Tally is reachable at {tally_client.get_tally_url()}."
                f"</span>")
        else:
            self.tally_status.setText(
                f"<span style='color:#B07000;'>"
                f"Saved. (Tally isn't responding at "
                f"{tally_client.get_tally_url()} right now — that's fine if "
                f"Tally isn't open yet.)</span>")

    def _open_data_folder(self) -> None:
        import os
        from .. import config
        try:
            os.startfile(str(config.DATA_DIR))  # noqa: S606 (Windows)
        except Exception as exc:
            QMessageBox.warning(
                self, "Couldn't open",
                f"Couldn't open {config.DATA_DIR}:\n\n{exc}")

    # -- background plumbing ---------------------------------------------------
    def _run_bg(self, fn, on_done) -> None:
        """Run ``fn(report)`` on a plain Python thread; deliver
        ``on_done(result, error)`` back on the UI thread.

        Deliberately NOT QThread + cross-thread signals: that pattern
        intermittently killed the app on the operator's machine — the
        same failure class v0.3.64 eliminated from the import commit
        ("check for updates… sometimes closes automatically"). Here the
        worker thread touches no Qt object at all; it only puts plain
        tuples on a ``queue.Queue``. A ``QTimer`` on the UI thread
        polls the queue, so every widget update (progress ticks
        included, via ``fn``'s ``report(pct)`` argument) happens on
        the UI thread.
        """
        if self._bg_timer is not None:
            return
        q: queue.Queue = queue.Queue()

        def report(pct: int) -> None:
            q.put(("progress", pct, ""))

        def work() -> None:
            try:
                q.put(("done", fn(report), ""))
            except Exception as exc:   # surfaced to the UI via on_done
                q.put(("done", None, str(exc)))

        timer = QTimer(self)
        timer.setInterval(100)

        def poll() -> None:
            while True:
                try:
                    kind, payload, err = q.get_nowait()
                except queue.Empty:
                    return
                if kind == "progress":
                    self.progress.setValue(int(payload or 0))
                    continue
                timer.stop()
                timer.deleteLater()
                self._bg_timer = None
                self._bg_thread = None
                on_done(payload, err)
                return

        timer.timeout.connect(poll)
        self._bg_timer = timer
        self._bg_thread = threading.Thread(target=work, daemon=True)
        self._bg_thread.start()
        timer.start()
