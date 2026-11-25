"""NAMELESS concept atlas: 20 original cosmetics, zero game integration.

A browseable gallery and exportable high-resolution presentation board.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QWidget, QGridLayout, QFileDialog, QMessageBox)
from redux_armory import (
    PACK_NAMES, SLOTS, SLOT_TITLES, COSMETIC_TITLES, PACK_STYLE,
    CosmeticCanvas)

ATLAS_WIDTH, ATLAS_HEIGHT = 2400, 2920


def render_atlas():
    """Render a single 20-concept showcase board without touching game assets."""
    image = QImage(ATLAS_WIDTH, ATLAS_HEIGHT, QImage.Format_ARGB32)
    image.fill(QColor("#0B1020"))
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QColor("#F8F4FF"))
    p.setFont(QFont("Segoe UI", 54, QFont.Bold))
    p.drawText(90, 115, "NAMELESS / REDUX ATLAS")
    p.setFont(QFont("Segoe UI", 22))
    p.setPen(QColor("#B8A8D7"))
    p.drawText(92, 164, "20 ORIGINAL COSMETIC CONCEPTS  /  FOUR WORLDS")
    for row, pack in enumerate(PACK_NAMES):
        y = 220 + row * 660
        style = PACK_STYLE[pack]
        p.setPen(QColor(style["accent"]))
        p.setFont(QFont("Segoe UI", 29, QFont.Bold))
        p.drawText(90, y + 38, "%02d   %s" % (row + 1, pack))
        for idx, slot in enumerate(SLOTS):
            x = 90 + idx * 447
            cell_y = y + 70
            canvas = CosmeticCanvas(pack=pack, slot=slot)
            thumb = canvas.snapshot().scaled(
                420, 310, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawImage(x, cell_y, thumb)
            p.setPen(QColor("#F4F0FF"))
            p.setFont(QFont("Segoe UI", 17, QFont.Bold))
            p.drawText(x, cell_y + 347, COSMETIC_TITLES[pack][slot])
            p.setPen(QColor("#A7A8C4"))
            p.setFont(QFont("Segoe UI", 13))
            p.drawText(x, cell_y + 377, SLOT_TITLES[slot])
    p.setPen(QPen(QColor("#535A83"), 2))
    p.drawLine(90, 2840, 2310, 2840)
    p.setPen(QColor("#B9BDD5"))
    p.setFont(QFont("Segoe UI", 18))
    p.drawText(90, 2885, "STANDALONE CONCEPT ART  /  NOT INSTALLED INTO ROB RUN")
    p.end()
    return image


class CosmeticAtlas(QDialog):
    """Gallery selection emits a local concept choice through the callback."""
    def __init__(self, parent=None, on_select=None):
        super().__init__(parent)
        self.setWindowTitle("NAMELESS REDUX / THE CONCEPT ATLAS")
        self.resize(1320, 850)
        self.setMinimumSize(940, 620)
        self.on_select = on_select
        self.setStyleSheet("""
            QDialog, QScrollArea, QWidget#atlasBody { background: #0B1020; color: #F6F1FF; }
            QLabel { color: #F6F1FF; background: transparent; }
            QLabel#atlasTitle { font-size: 27px; font-weight: 900; }
            QLabel#atlasSub { color: #B9B6D8; font-size: 12px; }
            QPushButton { background: #292B51; color: #FFFFFF;
                border: 1px solid #6764A1; border-radius: 9px;
                padding: 10px; font-weight: 800; }
            QPushButton:hover { background: #49417E; border-color: #D2B4FF; }
        """)
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        heading = QLabel("THE REDUX ATLAS")
        heading.setObjectName("atlasTitle")
        titles.addWidget(heading)
        subtitle = QLabel("20 original concepts / 4 collections / 5 categories / preview only")
        subtitle.setObjectName("atlasSub")
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        self.export_button = QPushButton("EXPORT FULL ATLAS PNG")
        self.export_button.clicked.connect(self.export_atlas)
        header.addWidget(self.export_button)
        root.addLayout(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        body = QWidget()
        body.setObjectName("atlasBody")
        grid = QGridLayout(body)
        grid.setSpacing(15)
        self.concept_buttons = {}
        for row, pack in enumerate(PACK_NAMES):
            label = QLabel("%02d  /  %s" % (row + 1, pack))
            label.setStyleSheet(
                "color: %s; font-size: 18px; font-weight: 900;" %
                PACK_STYLE[pack]["accent"])
            grid.addWidget(label, row * 2, 0, 1, 5)
            for column, slot in enumerate(SLOTS):
                cell = QWidget()
                cell_layout = QVBoxLayout(cell)
                cell_layout.setContentsMargins(2, 2, 2, 2)
                canvas = CosmeticCanvas(cell, pack=pack, slot=slot)
                canvas.setMinimumSize(130, 110)
                canvas.setMaximumHeight(185)
                cell_layout.addWidget(canvas)
                btn = QPushButton(COSMETIC_TITLES[pack][slot])
                btn.setToolTip("Preview " + SLOT_TITLES[slot] + " in Cosmetic Garage")
                btn.clicked.connect(
                    lambda checked=False, a=pack, b=slot: self.choose(a, b))
                cell_layout.addWidget(btn)
                self.concept_buttons[(pack, slot)] = btn
                grid.addWidget(cell, row * 2 + 1, column)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        footer = QLabel("ALL DESIGNS ARE ORIGINAL NAMELESS PREVIEWS. NO ROB RUN FILES ARE READ OR MODIFIED.")
        footer.setObjectName("atlasSub")
        root.addWidget(footer)

    def choose(self, pack, slot):
        if self.on_select:
            self.on_select(pack, slot)
        self.accept()

    def export_atlas(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export NAMELESS concept atlas", "nameless-redux-atlas.png",
            "PNG (*.png)")
        if not filename:
            return
        if not render_atlas().save(filename, "PNG"):
            QMessageBox.warning(self, "Export failed", "Unable to save atlas PNG.")
