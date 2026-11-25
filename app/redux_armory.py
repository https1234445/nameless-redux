"""Original cosmetic concept garage and safe NAMELESS-only loadout composer.

All artwork is made from Qt vector primitives. The garage never reads or
modifies game assets and never communicates with the ROB RUN process.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QSettings
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QLinearGradient,
                          QPainter, QPen, QPolygonF, QRadialGradient)
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget)

PACK_NAMES = ("SAKURA DREAM", "NEON NIGHT", "FROSTBITE", "CRIMSON")
SLOTS = ("weapon", "vehicle", "outfit", "mask", "backpack")
SLOT_TITLES = {
    "weapon": "WEAPON FINISH",
    "vehicle": "VEHICLE SKIN",
    "outfit": "CHARACTER OUTFIT",
    "mask": "FACE MASK",
    "backpack": "BACKPACK",
}
PACK_STYLE = {
    "SAKURA DREAM": {
        "accent": "#F8AFCB", "bright": "#FFE3EC", "dark": "#614665",
        "sky": "#251E41", "secondary": "#B977A8", "symbol": "petal",
        "subtitle": "Soft blossom petals / brushed rose-gold trim",
    },
    "NEON NIGHT": {
        "accent": "#64E9F1", "bright": "#B59BFF", "dark": "#312D67",
        "sky": "#080E2A", "secondary": "#9166F1", "symbol": "circuit",
        "subtitle": "Electric cyan circuits / violet underglow",
    },
    "FROSTBITE": {
        "accent": "#A7EDF8", "bright": "#F0FEFF", "dark": "#345A80",
        "sky": "#10263E", "secondary": "#77B7CF", "symbol": "crystal",
        "subtitle": "Frosted ceramic finish / crystalline edges",
    },
    "CRIMSON": {
        "accent": "#FF9A73", "bright": "#FFE4BC", "dark": "#652F3E",
        "sky": "#240E26", "secondary": "#D7565F", "symbol": "ember",
        "subtitle": "Smoked carbon / glowing ember tracery",
    },
}
COSMETIC_TITLES = {
    "SAKURA DREAM": {
        "weapon": "BLOSSOM / 01", "vehicle": "HANAMI DRIFT",
        "outfit": "PETAL RUNNER", "mask": "KITSUNE BLOOM",
        "backpack": "SAKURA SATCHEL",
    },
    "NEON NIGHT": {
        "weapon": "VOLT / 07", "vehicle": "AFTERDARK GT",
        "outfit": "NIGHT CIRCUIT", "mask": "SPECTRUM VISOR",
        "backpack": "ECHO CORE",
    },
    "FROSTBITE": {
        "weapon": "GLACIER / 02", "vehicle": "POLAR DASH",
        "outfit": "TUNDRA SHELL", "mask": "WHITEOUT",
        "backpack": "ICE CARRIER",
    },
    "CRIMSON": {
        "weapon": "ASH / 09", "vehicle": "EMBER RUNNER",
        "outfit": "CINDER CLOAK", "mask": "REDLINE",
        "backpack": "COAL RUCK",
    },
}
FORMAT = "nameless-redux-loadout-v1"
RENDER_W, RENDER_H = 1000, 620


def tint(value, alpha=255):
    c = QColor(value)
    c.setAlpha(alpha)
    return c


def shape(p, points, fill, border=None, stroke=2):
    p.setBrush(QBrush(tint(fill)))
    p.setPen(QPen(tint(border), stroke) if border else Qt.NoPen)
    p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in points]))


def segment(p, points, stroke, width=3):
    p.setPen(QPen(tint(stroke), width, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    for a, b in zip(points, points[1:]):
        p.drawLine(QPointF(*a), QPointF(*b))


def ellipse(p, x, y, rx, ry, fill, border=None, stroke=2):
    p.setPen(QPen(tint(border), stroke) if border else Qt.NoPen)
    p.setBrush(QBrush(tint(fill)))
    p.drawEllipse(QPointF(x, y), rx, ry)


class CosmeticCanvas(QWidget):
    """Five independent original cosmetic illustrations, four color families."""
    def __init__(self, parent=None, pack="SAKURA DREAM", slot="vehicle"):
        super().__init__(parent)
        self.setObjectName("cosmeticConceptCanvas")
        self.setMinimumSize(470, 380)
        self.pack = "SAKURA DREAM"
        self.slot = "vehicle"
        self.set_concept(pack, slot)

    def set_concept(self, pack, slot):
        if pack not in PACK_NAMES or slot not in SLOTS:
            raise ValueError("Unknown cosmetic concept")
        self.pack, self.slot = pack, slot
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0B1021"))
        scale = min(self.width() / RENDER_W, self.height() / RENDER_H)
        p.translate((self.width() - RENDER_W * scale) / 2,
                    (self.height() - RENDER_H * scale) / 2)
        p.scale(scale, scale)
        self.draw_concept(p)
        p.end()

    def snapshot(self):
        image = QImage(RENDER_W, RENDER_H, QImage.Format_ARGB32)
        image.fill(QColor("#0B1021"))
        p = QPainter(image)
        self.draw_concept(p)
        p.end()
        return image

    def draw_concept(self, p):
        p.setRenderHint(QPainter.Antialiasing)
        style = PACK_STYLE[self.pack]
        bg = QLinearGradient(0, 0, 1000, 620)
        bg.setColorAt(0, tint(style["sky"]))
        bg.setColorAt(.70, tint(style["dark"]))
        bg.setColorAt(1, tint("#0D1428"))
        p.fillRect(QRectF(0, 0, RENDER_W, RENDER_H), bg)

        orb = QRadialGradient(QPointF(640, 260), 370)
        orb.setColorAt(0, tint(style["accent"], 110))
        orb.setColorAt(.5, tint(style["secondary"], 40))
        orb.setColorAt(1, tint(style["secondary"], 0))
        p.setPen(Qt.NoPen)
        p.setBrush(orb)
        p.drawEllipse(QPointF(640, 260), 370, 370)

        # Studio horizon / drawing grid.
        for y in range(120, 570, 56):
            segment(p, [(0, y), (1000, y)], "#31334E", 1)
        for x in range(48, 1000, 82):
            segment(p, [(x, 114), (x, 556)], "#31334E", 1)
        segment(p, [(60, 514), (942, 514)], style["accent"], 2)

        if self.slot == "weapon":
            self._weapon(p, style)
        elif self.slot == "vehicle":
            self._vehicle(p, style)
        elif self.slot == "outfit":
            self._outfit(p, style)
        elif self.slot == "mask":
            self._mask(p, style)
        else:
            self._backpack(p, style)

        p.fillRect(QRectF(0, 0, 1000, 93), tint("#090E21", 228))
        p.setPen(tint(style["bright"]))
        p.setFont(QFont("Segoe UI", 22, QFont.Bold))
        p.drawText(QRectF(28, 10, 960, 44), Qt.AlignVCenter,
                   COSMETIC_TITLES[self.pack][self.slot])
        p.setFont(QFont("Segoe UI", 10))
        p.setPen(tint("#D9DCE9"))
        p.drawText(QRectF(30, 55, 960, 23), Qt.AlignVCenter,
                   self.pack + "  /  " + SLOT_TITLES[self.slot])
        p.fillRect(QRectF(0, 574, 1000, 46), tint("#0A0E20", 235))
        p.setPen(tint("#D1D8E5"))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRectF(27, 577, 950, 33), Qt.AlignVCenter,
                   "NAMELESS ORIGINAL CONCEPT  /  NOT A ROB RUN ITEM  /  PREVIEW ONLY")

    def _emblem(self, p, style, x, y, size=32):
        symbol = style["symbol"]
        p.save()
        p.translate(x, y)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(tint(style["bright"]), 3))
        if symbol == "petal":
            for angle in (0, 72, 144, 216, 288):
                p.save()
                p.rotate(angle)
                p.setBrush(tint(style["accent"]))
                p.drawEllipse(QRectF(-size * .13, -size * .86,
                                    size * .26, size * .66))
                p.restore()
            ellipse(p, 0, 0, size * .13, size * .13, style["bright"])
        elif symbol == "circuit":
            for angle in (0, 90, 180, 270):
                p.save()
                p.rotate(angle)
                segment(p, [(0, -size * .1), (0, -size * .7),
                            (size * .35, -size * .7)], style["bright"], 3)
                ellipse(p, size * .35, -size * .7, 4, 4, style["accent"])
                p.restore()
        elif symbol == "crystal":
            shape(p, [(0, -size), (size * .75, 0), (0, size),
                      (-size * .75, 0)], style["accent"], style["bright"])
            segment(p, [(0, -size), (0, size)], style["bright"], 2)
            segment(p, [(-size * .75, 0), (size * .75, 0)],
                    style["bright"], 2)
        else:
            shape(p, [(0, -size), (size * .7, -size * .1),
                      (size * .3, size), (-size * .7, size * .15)],
                  style["accent"], style["bright"])
            shape(p, [(0, -size * .5), (size * .18, size * .08),
                      (-size * .1, size * .55), (-size * .2, 0)],
                  style["bright"])
        p.restore()

    def _vehicle(self, p, s):
        ellipse(p, 512, 498, 350, 31, "#111427")
        # Original simplified performance coupe.
        shape(p, [(160, 403), (219, 341), (363, 326),
                  (449, 258), (656, 260), (749, 335),
                  (839, 356), (877, 398), (852, 443),
                  (173, 443)], s["dark"], s["bright"], 4)
        shape(p, [(375, 328), (452, 276), (641, 277),
                  (717, 334), (667, 340), (359, 341)],
              "#162640", s["accent"], 3)
        segment(p, [(546, 279), (558, 340)], s["bright"], 2)
        shape(p, [(199, 364), (349, 346), (732, 347),
                  (832, 382), (840, 420), (188, 421)],
              s["secondary"], s["bright"], 2)
        segment(p, [(191, 407), (833, 407)], s["accent"], 5)
        segment(p, [(283, 364), (695, 363)], s["bright"], 3)
        for x in (317, 751):
            ellipse(p, x, 439, 65, 65, "#090D18", s["accent"], 3)
            ellipse(p, x, 439, 38, 38, "#4D536B", s["bright"], 2)
            ellipse(p, x, 439, 17, 17, s["accent"])
            for angle in range(0, 360, 60):
                t = math.radians(angle)
                segment(p, [(x + 17 * math.cos(t), 439 + 17 * math.sin(t)),
                            (x + 36 * math.cos(t), 439 + 36 * math.sin(t))],
                        s["bright"], 4)
        shape(p, [(798, 361), (854, 378), (860, 394), (804, 388)],
              s["bright"])
        shape(p, [(180, 381), (219, 374), (220, 398), (172, 401)],
              "#FE6471")
        self._emblem(p, s, 517, 381, 24)

    def _weapon(self, p, s):
        ellipse(p, 508, 500, 305, 28, "#111427")
        shape(p, [(169, 295), (690, 295), (738, 314), (787, 324),
                  (819, 350), (743, 373), (704, 368), (628, 390),
                  (460, 375), (351, 399), (242, 366), (169, 358)],
              s["dark"], s["bright"], 4)
        shape(p, [(236, 313), (681, 309), (738, 331),
                  (625, 347), (267, 350)], s["secondary"], s["accent"], 3)
        shape(p, [(441, 379), (527, 379), (562, 494),
                  (464, 495)], "#172138", s["accent"], 3)
        shape(p, [(287, 360), (375, 361), (326, 418),
                  (214, 434), (168, 402)], "#1D2840", s["bright"], 3)
        shape(p, [(731, 317), (883, 299), (904, 315),
                  (893, 341), (753, 349)], "#18243C", s["bright"], 3)
        segment(p, [(256, 332), (692, 332)], s["bright"], 4)
        for x in range(336, 651, 33):
            segment(p, [(x, 353), (x + 13, 366)], s["accent"], 2)
        shape(p, [(341, 294), (398, 267), (548, 267),
                  (590, 295)], "#172139", s["accent"], 3)
        self._emblem(p, s, 575, 339, 22)

    def _outfit(self, p, s):
        ellipse(p, 496, 503, 212, 29, "#111427")
        ellipse(p, 500, 183, 47, 63, "#D5B4A8", s["bright"], 2)
        shape(p, [(447, 199), (435, 136), (474, 111),
                  (525, 113), (566, 146), (551, 199),
                  (520, 157), (476, 155)], s["dark"], s["bright"])
        shape(p, [(454, 237), (374, 255), (325, 365), (353, 395),
                  (417, 324), (414, 405), (433, 439), (566, 441),
                  (590, 402), (581, 326), (657, 392), (688, 363),
                  (621, 261), (544, 236)], s["dark"], s["accent"], 4)
        shape(p, [(454, 242), (498, 274), (545, 242),
                  (558, 418), (439, 419)], s["secondary"], s["bright"], 2)
        shape(p, [(458, 437), (496, 437), (491, 510), (446, 510)],
              "#1B263C", s["bright"], 2)
        shape(p, [(506, 437), (544, 437), (556, 510), (509, 510)],
              "#1B263C", s["bright"], 2)
        segment(p, [(379, 335), (418, 349)], s["bright"], 4)
        segment(p, [(591, 348), (646, 342)], s["bright"], 4)
        segment(p, [(440, 411), (558, 411)], s["accent"], 3)
        self._emblem(p, s, 500, 343, 29)

    def _mask(self, p, s):
        ellipse(p, 499, 348, 172, 191, "#182139", s["bright"], 3)
        shape(p, [(360, 331), (412, 273), (584, 273),
                  (638, 331), (624, 439), (562, 479),
                  (437, 479), (373, 438)], s["dark"], s["accent"], 5)
        shape(p, [(388, 327), (478, 337), (475, 365),
                  (405, 364)], "#0E1527", s["bright"], 3)
        shape(p, [(523, 337), (613, 327), (597, 364),
                  (526, 365)], "#0E1527", s["bright"], 3)
        shape(p, [(455, 397), (502, 377), (547, 398),
                  (526, 444), (474, 444)], s["secondary"], s["bright"], 2)
        segment(p, [(404, 390), (433, 438), (467, 452)], s["accent"], 3)
        segment(p, [(594, 390), (567, 438), (531, 452)], s["accent"], 3)
        self._emblem(p, s, 500, 306, 20)
        for side in (-1, 1):
            x = 500 + side * 166
            segment(p, [(x, 345), (x + side * 83, 365),
                        (x + side * 99, 409)], s["accent"], 5)

    def _backpack(self, p, s):
        ellipse(p, 506, 504, 203, 30, "#111427")
        shape(p, [(412, 213), (387, 177), (354, 190),
                  (335, 264), (340, 441), (380, 441), (403, 283)],
              "#151F38", s["accent"], 4)
        shape(p, [(587, 213), (612, 177), (644, 190),
                  (662, 264), (661, 441), (621, 441), (596, 283)],
              "#151F38", s["accent"], 4)
        shape(p, [(402, 221), (445, 193), (555, 194), (598, 222),
                  (627, 306), (606, 466), (392, 466), (371, 302)],
              s["dark"], s["bright"], 4)
        shape(p, [(405, 292), (600, 292), (586, 402), (414, 402)],
              s["secondary"], s["accent"], 3)
        shape(p, [(435, 407), (568, 407), (568, 456), (434, 456)],
              "#1A2541", s["bright"], 2)
        shape(p, [(434, 227), (562, 227), (573, 268), (423, 268)],
              "#1B2742", s["accent"], 2)
        segment(p, [(500, 228), (500, 275)], s["bright"], 3)
        ellipse(p, 502, 430, 8, 8, s["accent"])
        self._emblem(p, s, 500, 350, 29)


def validate_loadout_payload(data):
    """Only locally previewable slot selections; never accept game install data."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("Unsupported NAMELESS loadout file")
    if data.get("kind") != "preview-only" or data.get("game_files_modified") is not False:
        raise ValueError("Only NAMELESS preview-only loadouts can be imported")
    slots = data.get("slots")
    if not isinstance(slots, dict) or set(slots) != set(SLOTS):
        raise ValueError("Loadout must define exactly five cosmetic slots")
    for slot, pack in slots.items():
        if not isinstance(pack, str) or pack not in PACK_NAMES:
            raise ValueError("Unknown REDUX selected for " + slot)
    return dict(slots)


def build_loadout_payload(slots):
    if not isinstance(slots, dict) or set(slots) != set(SLOTS):
        raise ValueError("Invalid NAMELESS loadout")
    return {
        "format": FORMAT,
        "kind": "preview-only",
        "game": "ROB RUN",
        "game_files_modified": False,
        "slots": validate_loadout_payload({
            "format": FORMAT, "kind": "preview-only",
            "game_files_modified": False, "slots": slots,
        }),
    }


class CosmeticGarage(QDialog):
    """Mix cosmetics from all four themes across five independently saved slots."""
    def __init__(self, parent=None, initial_pack="SAKURA DREAM"):
        super().__init__(parent)
        if initial_pack not in PACK_NAMES:
            initial_pack = PACK_NAMES[0]
        self.setWindowTitle("NAMELESS REDUX  /  COSMETIC GARAGE")
        self._settings = QSettings("NAMELESS", "NAMELESS REDUX")
        self._restoring = False
        self.resize(1230, 835)
        self.setMinimumSize(900, 670)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 25, 26, 22)
        layout.setSpacing(14)
        heading = QLabel("COSMETIC GARAGE  /  BUILD YOUR OWN LOOK")
        heading.setObjectName("garageHeading")
        layout.addWidget(heading)
        caption = QLabel(
            "Five independent cosmetic slots • four REDUX themes • original local concepts")
        caption.setObjectName("garageCaption")
        layout.addWidget(caption)

        row = QHBoxLayout()
        row.setSpacing(19)
        self.canvas = CosmeticCanvas(pack=initial_pack)
        row.addWidget(self.canvas, 3)

        side = QFrame()
        side.setObjectName("garageSidebar")
        controls = QVBoxLayout(side)
        controls.setContentsMargins(18, 18, 18, 18)
        controls.setSpacing(9)
        select_title = QLabel("PREVIEW CATEGORY")
        select_title.setObjectName("garageLabel")
        controls.addWidget(select_title)
        self.category_select = QComboBox()
        self.category_select.addItems([SLOT_TITLES[s] for s in SLOTS])
        self.category_select.setCurrentIndex(1)
        controls.addWidget(self.category_select)

        subheading = QLabel("YOUR CUSTOM COSMETIC MIX")
        subheading.setObjectName("garageLabel")
        controls.addWidget(subheading)
        self.slot_selects = {}
        for slot in SLOTS:
            label = QLabel(SLOT_TITLES[slot])
            label.setObjectName("garageSlot")
            controls.addWidget(label)
            choice = QComboBox()
            choice.addItems(PACK_NAMES)
            choice.setCurrentText(initial_pack)
            choice.currentTextChanged.connect(
                lambda name, key=slot: self.on_slot_changed(key, name))
            self.slot_selects[slot] = choice
            controls.addWidget(choice)
        controls.addSpacing(6)

        self.concept_name = QLabel()
        self.concept_name.setObjectName("garageConcept")
        self.concept_name.setWordWrap(True)
        controls.addWidget(self.concept_name)
        self.details = QLabel()
        self.details.setObjectName("garageCaption")
        self.details.setWordWrap(True)
        controls.addWidget(self.details)
        controls.addStretch()
        row.addWidget(side, 2)
        layout.addLayout(row, 1)

        buttons = QHBoxLayout()
        self.png_button = QPushButton("EXPORT CONCEPT PNG")
        self.png_button.clicked.connect(self.export_png)
        buttons.addWidget(self.png_button)
        self.export_button = QPushButton("EXPORT MY LOADOUT JSON")
        self.export_button.clicked.connect(self.export_loadout)
        buttons.addWidget(self.export_button)
        self.import_button = QPushButton("IMPORT LOADOUT JSON")
        self.import_button.clicked.connect(self.import_loadout)
        buttons.addWidget(self.import_button)
        buttons.addStretch()
        close = QPushButton("CLOSE")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self.status = QLabel(
            "These are original NAMELESS concept drawings. No ROB RUN game files are modified.")
        self.status.setObjectName("garageStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.category_select.currentIndexChanged.connect(self.update_preview)
        self.restore_local_loadout()
        self.update_preview()
        self.setStyleSheet("""
            QDialog { background: #101427; color: #F4F5FF; }
            QLabel { color: #ECEAFF; background: transparent; }
            QLabel#garageHeading { font-size: 22px; font-weight: 900; }
            QLabel#garageCaption, QLabel#garageStatus {
                color: #B4BBD7; font-size: 12px;
            }
            QLabel#garageLabel { color: #D7B9FD; font-size: 13px; font-weight: 800; }
            QLabel#garageSlot { color: #D6D8EC; font-size: 11px; font-weight: 700; }
            QLabel#garageConcept { color: #F4D8FF; font-size: 16px; font-weight: 800; }
            QFrame#garageSidebar {
                background: #1B203C; border: 1px solid #50527A;
                border-radius: 14px;
            }
            QComboBox, QPushButton {
                color: #F7F2FF; background: #2A294B;
                border: 1px solid #69618E; border-radius: 8px;
                padding: 9px 12px;
            }
            QPushButton:hover { background: #41365E; }
            QComboBox::drop-down { border: none; }
            QWidget#cosmeticConceptCanvas {
                border: 1px solid #666092; border-radius: 12px;
            }
        """)

    def loadout_slots(self):
        return {slot: self.slot_selects[slot].currentText() for slot in SLOTS}

    def on_slot_changed(self, slot, pack):
        if slot == SLOTS[self.category_select.currentIndex()]:
            self.update_preview()
        if not self._restoring:
            self.save_local_loadout()

    def save_local_loadout(self):
        """Persist only the five safe preview selections in NAMELESS settings."""
        payload = build_loadout_payload(self.loadout_slots())
        self._settings.setValue(
            "cosmetic_garage/loadout", json.dumps(payload, sort_keys=True))
        self._settings.sync()

    def restore_local_loadout(self):
        """Ignore malformed or legacy data instead of crashing the garage."""
        raw = self._settings.value("cosmetic_garage/loadout", "")
        if not raw:
            return
        try:
            payload = json.loads(str(raw))
            self.apply_loadout(payload)
        except (ValueError, TypeError, KeyError):
            self._settings.remove("cosmetic_garage/loadout")

    def update_preview(self, *_):
        slot = SLOTS[self.category_select.currentIndex()]
        pack = self.slot_selects[slot].currentText()
        self.canvas.set_concept(pack, slot)
        self.concept_name.setText(COSMETIC_TITLES[pack][slot])
        self.details.setText(PACK_STYLE[pack]["subtitle"] +
                             "\n\nOriginal design proposal; not a ROB RUN game asset.")

    def apply_loadout(self, data):
        slots = validate_loadout_payload(data)
        self._restoring = True
        try:
            for slot, pack in slots.items():
                self.slot_selects[slot].setCurrentText(pack)
        finally:
            self._restoring = False
        self.update_preview()
        self.save_local_loadout()

    def export_png(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export original cosmetic concept",
            "nameless-" + self.canvas.slot + "-concept.png", "PNG (*.png)")
        if not filename:
            return
        if not self.canvas.snapshot().save(filename, "PNG"):
            QMessageBox.warning(self, "Export failed", "Could not write PNG.")
        else:
            self.status.setText("Original concept PNG saved. No game files touched.")

    def export_loadout(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export NAMELESS-only cosmetic loadout",
            "nameless-cosmetic-loadout.json", "JSON (*.json)")
        if not filename:
            return
        try:
            payload = build_loadout_payload(self.loadout_slots())
            Path(filename).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            self.status.setText("NAMELESS preview loadout exported. No game modifications.")
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def import_loadout(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import NAMELESS-only cosmetic loadout", "", "JSON (*.json)")
        if not filename:
            return
        try:
            path = Path(filename)
            if path.stat().st_size > 32 * 1024:
                raise ValueError("Loadout file must be smaller than 32 KiB")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.apply_loadout(data)
            self.status.setText(
                "Five preview slots restored • ROB RUN files were not changed.")
        except (OSError, ValueError, UnicodeError) as exc:
            QMessageBox.warning(self, "Import failed", str(exc))
