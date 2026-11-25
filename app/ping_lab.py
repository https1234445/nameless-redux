"""PING LAB: safe, read-only network quality diagnostics.

Tests only user-approved public reference endpoints; does not infer ROB RUN
server health, capture game traffic, change DNS, or modify network settings.
"""
from __future__ import annotations

import json
import socket
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, QSettings
from ping_history import (HISTORY_FORMAT, add_entry, make_entry,
                          validate_history, history_text)

from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QSpinBox, QTextEdit, QVBoxLayout)

ENDPOINTS = {
    "Cloudflare DNS / TCP 443": ("1.1.1.1", 443),
    "Google DNS / TCP 443": ("8.8.8.8", 443),
}
SAMPLE_COUNT = 12
SAMPLE_DELAY_SECONDS = 0.25
MAX_TIMEOUT_SECONDS = 1.5


def summarize_samples(samples):
    """Connection failure is not proof of UDP/game packet loss."""
    if not samples:
        raise ValueError("At least one sample is required")
    if any(v is not None and (not isinstance(v, (int, float)) or
                             isinstance(v, bool) or v < 0) for v in samples):
        raise ValueError("Invalid connection sample")
    good = [float(v) for v in samples if v is not None]
    failures = len(samples) - len(good)
    return {
        "attempts": len(samples),
        "successes": len(good),
        "connection_failures": failures,
        "failure_percent": round(100 * failures / len(samples), 1),
        "min_ms": round(min(good), 1) if good else None,
        "median_ms": round(statistics.median(good), 1) if good else None,
        "max_ms": round(max(good), 1) if good else None,
        "jitter_ms": round(statistics.mean(
            abs(b - a) for a, b in zip(good, good[1:])), 1)
        if len(good) > 1 else None,
    }


def tcp_probe(host, port, timeout=MAX_TIMEOUT_SECONDS):
    """Measure TCP connect time; no ICMP or game protocol claims."""
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return round((time.perf_counter() - start) * 1000, 2)
    except (OSError, TimeoutError):
        return None


class ProbeWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, host, port, count=SAMPLE_COUNT, probe=tcp_probe):
        super().__init__()
        self.host, self.port, self.count, self.probe = host, port, count, probe

    def run(self):
        try:
            values = []
            for index in range(self.count):
                values.append(self.probe(self.host, self.port))
                if index + 1 < self.count:
                    QThread.msleep(int(SAMPLE_DELAY_SECONDS * 1000))
            self.finished.emit(summarize_samples(values))
        except Exception as exc:
            self.failed.emit(str(exc))


def network_guidance(result):
    if result["successes"] == 0:
        return ("All TCP connection attempts failed. The endpoint may block "
                "connections, or the route/network may be unavailable. This does "
                "not prove ROB RUN servers are down.")
    if result["failure_percent"] >= 10:
        return ("Intermittent TCP connection failures detected. Compare wired "
                "Ethernet versus Wi-Fi, check background downloads, and repeat "
                "at another time. TCP failures are NOT a UDP packet-loss rate.")
    if result["jitter_ms"] is not None and result["jitter_ms"] > 30:
        return ("Connection times vary noticeably. Test over Ethernet and "
                "without background uploads. This measures TCP connect-time "
                "variation, not in-game latency.")
    return ("Reference endpoint connections look reasonably consistent. "
            "If ROB RUN still loses packets, the cause could be a game-specific "
            "route or server; this test cannot identify which.")


class PingLab(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NAMELESS REDUX / PING LAB")
        self.resize(780, 660)
        self.setMinimumSize(630, 520)
        self.thread = None
        self.worker = None
        self.last_result = None
        self.last_endpoint = None
        self.settings = QSettings("NAMELESS", "NAMELESS REDUX")
        self.history = self.load_history()
        self.setStyleSheet("""
            QDialog { background: #101326; color: #F5F2FF; }
            QLabel { color: #F5F2FF; }
            QLabel#netTitle { color: #8DE9F3; font-size: 25px; font-weight: 900; }
            QLabel#netNote { color: #ADB8D6; }
            QPushButton, QComboBox, QSpinBox { background: #302B52; color: #F8F4FF;
                border: 1px solid #69618E; border-radius: 7px; padding: 9px; }
            QPushButton:hover { background: #493C78; }
            QTextEdit { background: #151A30; color: #F2EEFF;
                border: 1px solid #45496A; border-radius: 8px; padding: 10px; }
        """)
        root = QVBoxLayout(self)
        heading = QLabel("PING LAB  /  CONNECTION QUALITY")
        heading.setObjectName("netTitle")
        root.addWidget(heading)
        note = QLabel("Reference endpoint TCP tests only — NOT ROB RUN ping or UDP packet loss.")
        note.setObjectName("netNote")
        note.setWordWrap(True)
        root.addWidget(note)
        root.addWidget(QLabel("PUBLIC REFERENCE ENDPOINT"))
        self.endpoint = QComboBox()
        self.endpoint.addItems(ENDPOINTS)
        root.addWidget(self.endpoint)
        self.start_button = QPushButton("RUN 12-SAMPLE CONNECTION CHECK")
        self.start_button.clicked.connect(self.start_probe)
        root.addWidget(self.start_button)
        self.results = QTextEdit()
        self.results.setReadOnly(True)
        self.results.setPlainText(
            "Click RUN to measure connection setup times to the selected public "
            "reference service. No changes will be made to Windows or ROB RUN.")
        root.addWidget(self.results, 1)
        root.addWidget(QLabel("TROUBLESHOOTING / NO MAGIC BOOST"))
        guide = QTextEdit()
        guide.setReadOnly(True)
        guide.setPlainText(
            "01  Prefer Ethernet over Wi-Fi for consistent latency.\n\n"
            "02  Pause large uploads, cloud sync and downloads while playing.\n\n"
            "03  Compare results at different times and on a second network.\n\n"
            "04  If only ROB RUN has problems, record region, time and symptoms "
            "for the developer.\n\n"
            "05  Never disable your firewall, antivirus or security settings "
            "for a supposed ping boost.")
        root.addWidget(guide, 1)
        root.addWidget(QLabel("LOCAL CONNECTION HISTORY  /  LAST 60 CHECKS"))
        self.history_view = QTextEdit()
        self.history_view.setReadOnly(True)
        self.history_view.setPlainText(history_text(self.history))
        root.addWidget(self.history_view, 1)
        history_buttons = QHBoxLayout()
        export_history = QPushButton("EXPORT HISTORY JSON")
        export_history.clicked.connect(self.export_history)
        history_buttons.addWidget(export_history)
        clear_history = QPushButton("CLEAR LOCAL HISTORY")
        clear_history.clicked.connect(self.clear_history)
        history_buttons.addWidget(clear_history)
        root.addLayout(history_buttons)
        buttons = QHBoxLayout()
        self.export_button = QPushButton("EXPORT DIAGNOSTIC JSON")
        self.export_button.clicked.connect(self.export_report)
        self.export_button.setEnabled(False)
        buttons.addWidget(self.export_button)
        close = QPushButton("CLOSE")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        root.addLayout(buttons)
        footer = QLabel(
            "A failed TCP connection is NOT the same as UDP packet loss. "
            "This tool cannot diagnose DDoS or early-access server outages.")
        footer.setObjectName("netNote")
        footer.setWordWrap(True)
        root.addWidget(footer)

    def load_history(self):
        raw = self.settings.value("ping_lab/history", "")
        if not raw:
            return []
        try:
            return validate_history(json.loads(str(raw)))
        except (ValueError, TypeError):
            return []

    def store_history(self):
        payload = {"format": HISTORY_FORMAT, "entries": self.history}
        self.settings.setValue("ping_lab/history", json.dumps(payload))
        self.settings.sync()
        self.history_view.setPlainText(history_text(self.history))

    def clear_history(self):
        confirm = QMessageBox.question(
            self, "Clear PING LAB history",
            "Delete all locally saved connection checks? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.history = []
            self.store_history()

    def export_history(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export local PING LAB history",
            "nameless-ping-history.json", "JSON (*.json)")
        if not filename:
            return
        try:
            Path(filename).write_text(json.dumps({
                "format": HISTORY_FORMAT, "entries": self.history,
                "method": "TCP connect to public reference endpoints",
                "not_game_server_test": True,
                "not_udp_packet_loss": True,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def start_probe(self):
        if self.thread is not None:
            return
        self.last_result = None
        self.export_button.setEnabled(False)
        self.last_endpoint = self.endpoint.currentText()
        host, port = ENDPOINTS[self.last_endpoint]
        self.start_button.setEnabled(False)
        self.endpoint.setEnabled(False)
        self.results.setPlainText("Checking reference endpoint… this may take up to 22 seconds.")
        self.thread = QThread(self)
        self.worker = ProbeWorker(host, port)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.show_result)
        self.worker.failed.connect(self.show_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.probe_finished)
        self.thread.start()

    def show_result(self, result):
        self.last_result = result
        self.history = add_entry(
            self.history, make_entry(self.last_endpoint, result))
        self.store_history()
        self.export_button.setEnabled(True)
        lines = [
            "REFERENCE  /  " + self.last_endpoint,
            "TCP ATTEMPTS  /  " + str(result["attempts"]),
            "CONNECTED  /  " + str(result["successes"]),
            "CONNECTION FAILURES  /  " + str(result["connection_failures"]),
            "FAILURE RATE  /  " + str(result["failure_percent"]) + "%",
            "MEDIAN CONNECT TIME  /  " + str(result["median_ms"]) + " ms",
            "CONNECT-TIME VARIATION  /  " + str(result["jitter_ms"]) + " ms",
            "",
            network_guidance(result),
        ]
        self.results.setPlainText("\n".join(lines))

    def show_error(self, message):
        self.results.setPlainText("Diagnostic failed: " + message)

    def probe_finished(self):
        self.thread = None
        self.worker = None
        self.start_button.setEnabled(True)
        self.endpoint.setEnabled(True)

    def export_report(self):
        if self.last_result is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save connection diagnostic", "nameless-ping-lab.json",
            "JSON (*.json)")
        if not filename:
            return
        report = {
            "format": "nameless-ping-lab-v1",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "method": "TCP connect to public reference endpoint",
            "endpoint": self.last_endpoint,
            "not_game_server_test": True,
            "not_udp_packet_loss": True,
            "result": self.last_result,
            "guidance": network_guidance(self.last_result),
            "network_settings_modified": False,
            "game_files_modified": False,
        }
        try:
            Path(filename).write_text(
                json.dumps(report, indent=2, ensure_ascii=False),
                encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
