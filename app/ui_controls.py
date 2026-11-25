"""Combo boxes must never change settings when scrolling a page."""
from PySide6.QtWidgets import QComboBox


class ClickOnlyComboBox(QComboBox):
    """Mouse wheel passes to the parent scroll area instead of selecting items."""

    def wheelEvent(self, event):
        event.ignore()
