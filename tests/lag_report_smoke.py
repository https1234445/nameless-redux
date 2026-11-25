"""ROB RUN lag report: offline payload, privacy labels and Qt smoke test."""
import os
import sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from PySide6.QtWidgets import QApplication
from lag_report import (LagReportDialog, build_incident_report,
                        report_as_text, REPORT_FORMAT, SYMPTOMS)

app = QApplication.instance() or QApplication([])
report = build_incident_report(
    "EU", SYMPTOMS[0], "Teleported back three times.",
    "45 ms", "2026-11-25 18:00 UTC")
assert report["format"] == REPORT_FORMAT
assert report["ddos_diagnosed"] is False
assert report["uploaded_automatically"] is False
assert report["incident"]["region_user_reported"] == "EU"
assert "not establish a DDoS" in report_as_text(report)
assert "PLAYER-REPORTED" in report_as_text(report)
for invalid in ("", " "):
    try:
        build_incident_report("EU", SYMPTOMS[0], invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("Empty incident description accepted")
try:
    build_incident_report("EU", "DDoS confirmed", "Something happened")
except ValueError:
    pass
else:
    raise AssertionError("Unsupported symptom accepted")
reference = {"endpoint": "Cloudflare DNS / TCP 443",
             "result": {"median_ms": 20, "failure_percent": 0}}
dialog = LagReportDialog(reference=reference)
dialog.description.setPlainText("Rubber banding in a match.")
payload = dialog.payload()
assert payload["public_reference_tcp_check"] == reference
assert "NOT THE GAME SERVER" in report_as_text(payload)
dialog.close()
app.quit()
print("ROB RUN lag report: offline export payload, safety labels and UI OK")
