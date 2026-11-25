from ui_controls import ClickOnlyComboBox
"""ROB RUN Lag Report: local, opt-in incident reports for developers.

No automatic uploads, game traffic capture, network changes or DDoS claims.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout)

SYMPTOMS = (
    "Rubber-banding / teleporting",
    "Delayed actions / hit registration",
    "Disconnects / timeouts",
    "In-game packet-loss indicator",
    "High in-game ping",
    "Other / uncertain",
)
REPORT_FORMAT = "nameless-rob-run-lag-report-v1"


def build_incident_report(region, symptom, description, game_ping="",
                          occurred_at="", reference=None):
    """Only user-supplied details; optional reference is clearly labeled."""
    region = region.strip()
    description = description.strip()
    game_ping = game_ping.strip()
    occurred_at = occurred_at.strip()
    if symptom not in SYMPTOMS:
        raise ValueError("Choose a supported symptom")
    if not description or len(description) > 2000:
        raise ValueError("Describe the issue (1-2000 characters)")
    if len(region) > 80 or len(game_ping) > 60 or len(occurred_at) > 80:
        raise ValueError("One of the report fields is too long")
    if reference is not None:
        if not isinstance(reference, dict) or not isinstance(
                reference.get("endpoint"), str) or not isinstance(
                reference.get("result"), dict):
            raise ValueError("Invalid reference measurement")
    return {
        "format": REPORT_FORMAT,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "game": "ROB RUN",
        "steam_app_id": 4262460,
        "incident": {
            "region_user_reported": region or "Not provided",
            "time_user_reported": occurred_at or "Not provided",
            "symptom_user_reported": symptom,
            "description_user_reported": description,
            "in_game_ping_user_reported": game_ping or "Not provided",
        },
        "public_reference_tcp_check": reference,
        "measurement_note": (
            "Public TCP reference checks do not measure ROB RUN server latency "
            "or game UDP packet loss. All in-game symptoms are user-reported."),
        "ddos_diagnosed": False,
        "game_files_modified": False,
        "network_settings_modified": False,
        "uploaded_automatically": False,
    }


def report_as_text(report):
    incident = report["incident"]
    lines = [
        "ROB RUN / CONNECTION INCIDENT REPORT",
        "Created (UTC): " + report["created_utc"],
        "Region (player-reported): " + incident["region_user_reported"],
        "Incident time (player-reported): " + incident["time_user_reported"],
        "Symptom: " + incident["symptom_user_reported"],
        "In-game ping (player-reported): " +
        incident["in_game_ping_user_reported"],
        "",
        "DESCRIPTION (PLAYER-REPORTED)",
        incident["description_user_reported"],
    ]
    ref = report.get("public_reference_tcp_check")
    if ref:
        metrics = ref["result"]
        lines += [
            "",
            "OPTIONAL PUBLIC TCP REFERENCE CHECK (NOT THE GAME SERVER)",
            "Endpoint: " + ref["endpoint"],
            "Median TCP connect: " + str(metrics.get("median_ms")) + " ms",
            "TCP connection failures: " +
            str(metrics.get("failure_percent")) + "%",
        ]
    lines += [
        "",
        "LIMITATIONS",
        report["measurement_note"],
        "This report does not establish a DDoS attack or a server outage.",
        "Created locally by NAMELESS REDUX; not automatically submitted.",
    ]
    return "\n".join(lines) + "\n"


class LagReportDialog(QDialog):
    def __init__(self, parent=None, reference=None):
        super().__init__(parent)
        self.reference = reference
        self.setWindowTitle("NAMELESS REDUX / ROB RUN LAG REPORT")
        self.resize(750, 660)
        self.setMinimumSize(570, 490)
        self.setStyleSheet("""
            QDialog { background: #101326; color: #F5F2FF; }
            QLabel { color: #F5F2FF; }
            QLabel#reportTitle { color: #8DE9F3; font-size: 24px; font-weight: 900; }
            QLabel#reportNote { color: #ADB8D6; }
            QLineEdit, QTextEdit, QComboBox { background: #1B203A; color: #F5F2FF;
                border: 1px solid #565C82; border-radius: 7px; padding: 8px; }
            QPushButton { background: #302B52; color: #F8F4FF;
                border: 1px solid #69618E; border-radius: 7px; padding: 9px; }
            QPushButton:hover { background: #493C78; }
        """)
        root = QVBoxLayout(self)
        title = QLabel("ROB RUN  /  LAG INCIDENT REPORT")
        title.setObjectName("reportTitle")
        root.addWidget(title)
        note = QLabel("Describe a real incident. No automatic uploads or DDoS diagnosis.")
        note.setObjectName("reportNote")
        note.setWordWrap(True)
        root.addWidget(note)
        form = QFormLayout()
        self.region = QLineEdit()
        self.region.setMaxLength(80)
        self.region.setPlaceholderText("Optional: Europe / North America / other")
        form.addRow("Game region", self.region)
        self.occurred = QLineEdit()
        self.occurred.setMaxLength(80)
        self.occurred.setPlaceholderText("Optional: date, time and timezone")
        form.addRow("When it happened", self.occurred)
        self.symptom = ClickOnlyComboBox()
        self.symptom.addItems(SYMPTOMS)
        form.addRow("Main symptom", self.symptom)
        self.game_ping = QLineEdit()
        self.game_ping.setMaxLength(60)
        self.game_ping.setPlaceholderText("Optional: as displayed in ROB RUN")
        form.addRow("In-game ping", self.game_ping)
        root.addLayout(form)
        root.addWidget(QLabel("WHAT HAPPENED? (REQUIRED)"))
        self.description = QTextEdit()
        self.description.setPlaceholderText(
            "Describe the incident, how often it occurs and what you were doing.")
        root.addWidget(self.description, 1)
        self.reference_note = QLabel(
            "Latest public TCP reference measurement: " +
            ("available; will be included" if reference else "not available"))
        self.reference_note.setObjectName("reportNote")
        root.addWidget(self.reference_note)
        buttons = QHBoxLayout()
        txt = QPushButton("EXPORT TEXT REPORT")
        txt.clicked.connect(lambda: self.export("txt"))
        buttons.addWidget(txt)
        js = QPushButton("EXPORT JSON REPORT")
        js.clicked.connect(lambda: self.export("json"))
        buttons.addWidget(js)
        close = QPushButton("CLOSE")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        root.addLayout(buttons)

    def payload(self):
        return build_incident_report(
            self.region.text(), self.symptom.currentText(),
            self.description.toPlainText(), self.game_ping.text(),
            self.occurred.text(), self.reference)

    def export(self, extension):
        try:
            report = self.payload()
        except ValueError as exc:
            QMessageBox.warning(self, "Report needs details", str(exc))
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save local ROB RUN incident report",
            "rob-run-lag-report." + extension,
            "Text (*.txt)" if extension == "txt" else "JSON (*.json)")
        if not filename:
            return
        content = (report_as_text(report) if extension == "txt" else
                   json.dumps(report, ensure_ascii=False, indent=2))
        try:
            Path(filename).write_text(content, encoding="utf-8")
            QMessageBox.information(
                self, "Report saved",
                "Report saved locally. Review it before sharing with anyone.")
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
