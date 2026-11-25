"""Headless network diagnostics test without external traffic."""
import os
import sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from PySide6.QtWidgets import QApplication
from ping_lab import PingLab, ProbeWorker, ENDPOINTS, summarize_samples, network_guidance

app = QApplication.instance() or QApplication([])
assert len(ENDPOINTS) == 2
report = summarize_samples([10, 12, None, 18])
assert report["attempts"] == 4
assert report["connection_failures"] == 1
assert report["failure_percent"] == 25.0
assert report["median_ms"] == 12.0
assert "TCP" in network_guidance(report)
all_failed = summarize_samples([None, None])
assert all_failed["median_ms"] is None
assert all_failed["failure_percent"] == 100.0
for samples in ([], [-1], [True]):
    try:
        summarize_samples(samples)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid samples accepted")
worker = ProbeWorker("test.invalid", 443, count=3, probe=lambda *_: 20)
results = []
worker.finished.connect(results.append)
worker.run()
assert results[0]["successes"] == 3
dialog = PingLab()
assert dialog.endpoint.count() == 2
assert not dialog.export_button.isEnabled()
dialog.last_endpoint = dialog.endpoint.currentText()
dialog.show_result(report)
assert dialog.export_button.isEnabled()
assert "NOT" not in dialog.results.toPlainText() or dialog.last_result == report
dialog.close()
app.quit()
print("PING LAB: offline tests, UI, TCP metrics and guidance OK")
