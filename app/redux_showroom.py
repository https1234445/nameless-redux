"""Original interactive concept showroom for NAMELESS REDUX.

Every pixel and sound here is generated locally. Nothing accesses ROB RUN files,
processes, memory, networking or anti-cheat. This is NOT an in-game mod.
"""
from __future__ import annotations
from ui_controls import ClickOnlyComboBox

import io
import math
import random
import struct
import tempfile
import wave
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QLinearGradient,
                          QPainter, QPen, QPolygonF, QRadialGradient)
from redux_armory import CosmeticGarage

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,
                               QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

SCENE_W = 960
SCENE_H = 540
PACKS = {
    "SAKURA DREAM": {
        "sky": ("#2D204B", "#B66D9D", "#F9B7C7"),
        "accent": "#FFD4E4", "glow": "#F49ABD",
        "ground": "#3C304F", "kind": "petals",
        "description": "Rose dusk / blossom finish / velvet shot / drifting petals",
        "particles": 12, "life": .65,
    },
    "NEON NIGHT": {
        "sky": ("#080F2B", "#251F59", "#63357A"),
        "accent": "#62F8FF", "glow": "#C36AFF",
        "ground": "#09152E", "kind": "sparks",
        "description": "Electric skyline / circuit finish / synth pulse / neon sparks",
        "particles": 10, "life": .50,
    },
    "FROSTBITE": {
        "sky": ("#102B46", "#507F9B", "#C2E8EE"),
        "accent": "#E9FDFF", "glow": "#83E4F6",
        "ground": "#244B67", "kind": "ice",
        "description": "Polar horizon / ice finish / crisp shot / crystal fragments",
        "particles": 8, "life": .55,
    },
    "CRIMSON": {
        "sky": ("#250E21", "#8B2941", "#EA805D"),
        "accent": "#FFE4B1", "glow": "#FF9062",
        "ground": "#381F29", "kind": "embers",
        "description": "Blood-orange dusk / ember finish / warm hit / floating ash",
        "particles": 10, "life": .50,
    },
}


def color(hex_code, alpha=255):
    result = QColor(hex_code)
    result.setAlpha(alpha)
    return result


def polygon(painter, coords, fill, border=None, width=1):
    painter.setBrush(QBrush(color(fill) if isinstance(fill, str) else fill))
    painter.setPen(QPen(color(border), width) if border else Qt.NoPen)
    painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in coords]))


def line(painter, x1, y1, x2, y2, shade, thickness=2):
    painter.setPen(QPen(color(shade), thickness, Qt.SolidLine, Qt.RoundCap))
    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def original_shot_wav(pack_name):
    """Generate original short WAV bytes, reproducibly, without media assets."""
    if pack_name not in PACKS:
        raise ValueError("Unknown REDUX")
    sample_rate = 22050
    count = int(sample_rate * .24)
    options = {
        "SAKURA DREAM": (460, .12, .22),
        "NEON NIGHT": (230, .35, .30),
        "FROSTBITE": (710, .18, .25),
        "CRIMSON": (165, .45, .38),
    }
    pitch, noise_level, loudness = options[pack_name]
    rng = random.Random(sum(ord(c) for c in pack_name))
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        data = bytearray()
        for index in range(count):
            t = index / sample_rate
            envelope = (1 - math.exp(-t * 250)) * math.exp(-t * 19)
            sweep = pitch * (1 - .48 * min(1, t / .24))
            tone = math.sin(2 * math.pi * sweep * t)
            harmonic = math.sin(2 * math.pi * (pitch * 1.52) * t) * .22
            hiss = (rng.random() * 2 - 1) * noise_level
            value = max(-1, min(1, (tone + harmonic + hiss) * envelope * loudness))
            data.extend(struct.pack("<h", int(value * 32767)))
        wav.writeframes(bytes(data))
    return out.getvalue()


class ShowroomCanvas(QWidget):
    """Fixed virtual 16:9 scene with bounded original impact effects."""
    fired = Signal(str)

    def __init__(self, parent=None, pack="SAKURA DREAM"):
        super().__init__(parent)
        self.setObjectName("reduxShowroomCanvas")
        self.setMinimumSize(520, 300)
        self.setMouseTracking(True)
        self.pack = "SAKURA DREAM"
        self.motion_enabled = True
        self.frame = 0
        self.particles = []
        self.last_hit = QPointF(670, 256)
        self.flash = 0
        self._rng = random.Random(2027)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.step)
        self.set_pack(pack)

    def showEvent(self, event):
        super().showEvent(event)
        if self.motion_enabled:
            self._timer.start()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def set_motion_enabled(self, enabled):
        self.motion_enabled = bool(enabled)
        if self.motion_enabled and self.isVisible():
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def set_pack(self, name):
        if name not in PACKS:
            raise ValueError("Unknown REDUX: " + str(name))
        self.pack = name
        self.particles.clear()
        self.flash = 0
        self.frame = 0
        self.update()

    def fire_at(self, point):
        spec = PACKS[self.pack]
        x = max(50., min(SCENE_W - 50., float(point.x())))
        y = max(70., min(SCENE_H - 135., float(point.y())))
        self.last_hit = QPointF(x, y)
        self.flash = .14
        for _ in range(spec["particles"]):
            angle = self._rng.uniform(0, 2 * math.pi)
            velocity = self._rng.uniform(75, 220)
            self.particles.append({
                "x": x, "y": y,
                "vx": math.cos(angle) * velocity,
                "vy": math.sin(angle) * velocity - 55,
                "age": 0., "life": spec["life"],
                "size": self._rng.uniform(3., 8.),
                "angle": self._rng.uniform(0, 360),
            })
        # Avoid unbounded allocations on very rapid clicks.
        self.particles = self.particles[-64:]
        self.fired.emit(self.pack)
        self.update()
        return spec["particles"]

    def step(self, dt=.033):
        self.frame += 1
        self.flash = max(0., self.flash - dt)
        remaining = []
        for particle in self.particles:
            particle["age"] += dt
            if particle["age"] >= particle["life"]:
                continue
            particle["x"] += particle["vx"] * dt
            particle["y"] += particle["vy"] * dt
            particle["vy"] += 95 * dt
            particle["angle"] += 160 * dt
            remaining.append(particle)
        self.particles = remaining
        self.update()

    def _coordinates(self, point):
        scale = min(self.width() / SCENE_W, self.height() / SCENE_H)
        left = (self.width() - SCENE_W * scale) / 2
        top = (self.height() - SCENE_H * scale) / 2
        return QPointF((point.x() - left) / scale, (point.y() - top) / scale)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.fire_at(self._coordinates(event.position()))
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0A0D19"))
        scale = min(self.width() / SCENE_W, self.height() / SCENE_H)
        p.translate((self.width() - SCENE_W * scale) / 2,
                    (self.height() - SCENE_H * scale) / 2)
        p.scale(scale, scale)
        self.draw_scene(p)
        p.end()

    def snapshot(self):
        image = QImage(SCENE_W, SCENE_H, QImage.Format_ARGB32)
        image.fill(QColor("#0A0D19"))
        painter = QPainter(image)
        self.draw_scene(painter)
        painter.end()
        return image

    def draw_scene(self, p):
        p.setRenderHint(QPainter.Antialiasing, True)
        spec = PACKS[self.pack]
        gradient = QLinearGradient(0, 0, 0, SCENE_H)
        for idx, stop in enumerate(spec["sky"]):
            gradient.setColorAt(idx / 2, color(stop))
        p.fillRect(QRectF(0, 0, SCENE_W, SCENE_H), gradient)
        if self.pack == "NEON NIGHT":
            self._neon_world(p, spec)
        elif self.pack == "FROSTBITE":
            self._frost_world(p, spec)
        elif self.pack == "CRIMSON":
            self._crimson_world(p, spec)
        else:
            self._sakura_world(p, spec)
        self._weather(p, spec)
        self._targets(p, spec)
        self._weapon(p, spec)
        self._impacts(p, spec)
        self._hud(p, spec)

    def _sun(self, p, x, y, radius, tint):
        halo = QRadialGradient(QPointF(x, y), radius * 2.8)
        halo.setColorAt(0, color(tint, 110))
        halo.setColorAt(.42, color(tint, 38))
        halo.setColorAt(1, color(tint, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(x, y), radius * 2.8, radius * 2.8)
        p.setBrush(color(tint, 195))
        p.drawEllipse(QPointF(x, y), radius, radius)

    def _mountains(self, p, far, near):
        polygon(p, [(0, 360), (0, 270), (128, 328), (259, 234),
                    (387, 326), (535, 250), (702, 345), (830, 278),
                    (960, 347), (960, 540), (0, 540)], far)
        polygon(p, [(0, 400), (0, 344), (145, 386), (318, 328),
                    (460, 410), (661, 354), (807, 390), (960, 330),
                    (960, 540), (0, 540)], near)

    def _sakura_world(self, p, spec):
        self._sun(p, 736, 159, 49, "#FFE5D1")
        self._mountains(p, "#936587", spec["ground"])
        polygon(p, [(0, 460), (170, 420), (408, 446), (678, 414),
                    (960, 460), (960, 540), (0, 540)], "#28253E")
        # Original stylized cherry tree, not a texture from any game.
        line(p, 102, 445, 134, 227, "#36273D", 24)
        line(p, 132, 305, 66, 222, "#36273D", 15)
        line(p, 133, 269, 235, 183, "#36273D", 15)
        line(p, 94, 268, 25, 183, "#36273D", 10)
        for x, y, radius in [(57, 184, 53), (128, 176, 70), (209, 181, 57),
                             (86, 229, 60), (180, 228, 54), (20, 252, 40)]:
            p.setBrush(color("#EE91BC", 210))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(x, y), radius, radius * .67)
            p.setBrush(color("#FFD3DF", 85))
            p.drawEllipse(QPointF(x - 10, y - 13), radius * .66, radius * .40)

    def _neon_world(self, p, spec):
        self._sun(p, 745, 127, 47, "#A785FF")
        # Neon city silhouettes, windows and road are drawn with vectors.
        for i in range(16):
            x = i * 65
            height = 70 + ((i * 47) % 145)
            p.fillRect(QRectF(x, 385 - height, 51, height + 120), color("#0C1531"))
            line(p, x, 385 - height, x + 51, 385 - height, "#6A45B1", 2)
            for wy in range(395 - height, 384, 20):
                for wx in range(x + 9, x + 48, 14):
                    if ((wx + wy + i) // 10) % 3:
                        p.fillRect(QRectF(wx, wy, 5, 8), color("#56F2F7", 160))
        polygon(p, [(0, 451), (960, 451), (960, 540), (0, 540)], "#0A122A")
        for x in range(-450, 1500, 95):
            line(p, x, 540, 480 + (x - 480) * .14, 451, "#4D3A98", 1)
        line(p, 0, 451, 960, 451, "#60E8F1", 2)

    def _frost_world(self, p, spec):
        self._sun(p, 737, 134, 43, "#E9FAFF")
        self._mountains(p, "#78A7BB", "#315D79")
        polygon(p, [(0, 392), (176, 260), (292, 395), (421, 218),
                    (580, 398), (740, 275), (960, 402), (960, 540),
                    (0, 540)], "#A6D2E1")
        polygon(p, [(176, 260), (225, 333), (180, 315), (127, 326)],
                "#F3FCFF")
        polygon(p, [(421, 218), (480, 308), (428, 284), (365, 307)],
                "#F3FCFF")
        polygon(p, [(740, 275), (793, 343), (739, 321), (689, 344)],
                "#F3FCFF")
        polygon(p, [(0, 452), (153, 413), (370, 468), (632, 420),
                    (960, 459), (960, 540), (0, 540)], "#D9F2F4")

    def _crimson_world(self, p, spec):
        self._sun(p, 741, 189, 64, "#FFD18B")
        self._mountains(p, "#6D2E46", "#392032")
        polygon(p, [(0, 453), (140, 423), (337, 452), (538, 411),
                    (771, 461), (960, 432), (960, 540), (0, 540)], "#281927")
        for x in range(50, 960, 135):
            line(p, x, 444, x + 9, 415 - (x % 40), "#B64448", 4)
            line(p, x + 9, 415 - (x % 40), x + 28, 448, "#542638", 3)

    def _weather(self, p, spec):
        tint = spec["accent"]
        for index in range(27):
            drift = self.frame * (.7 if spec["kind"] in ("petals", "ice") else 1.3)
            x = (index * 157 + 31 + drift * (index % 3 + 1)) % 1000 - 20
            y = (index * 89 + 33 + drift * (index % 5 + 1) * .35) % 520
            p.setPen(Qt.NoPen)
            p.setBrush(color(tint, 130 if index % 3 else 65))
            if spec["kind"] == "petals":
                p.save()
                p.translate(x, y)
                p.rotate((index * 27 + self.frame * 1.2) % 360)
                p.drawEllipse(QRectF(-4, -2, 9, 5))
                p.restore()
            elif spec["kind"] == "ice":
                p.drawEllipse(QPointF(x, y), 2 + index % 3, 2 + index % 3)
            else:
                p.drawEllipse(QPointF(x, y), 1 + index % 2, 2 + index % 2)

    def _targets(self, p, spec):
        for cx, cy, radius in [(605, 265, 34), (768, 329, 25), (486, 309, 20)]:
            p.setPen(QPen(color(spec["accent"], 185), 2))
            p.setBrush(color("#111429", 85))
            p.drawEllipse(QPointF(cx, cy), radius, radius)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), radius * .63, radius * .63)
            line(p, cx - 9, cy, cx + 9, cy, spec["accent"], 1)
            line(p, cx, cy - 9, cx, cy + 9, spec["accent"], 1)

    def _weapon(self, p, spec):
        # Concept-only vector prop: no ROB RUN meshes or extracted textures.
        polygon(p, [(625, 470), (786, 413), (890, 431), (950, 468),
                    (960, 540), (690, 540)], "#11182A", "#6D7294", 2)
        polygon(p, [(680, 448), (813, 406), (890, 415), (918, 437),
                    (765, 497), (685, 481)], "#2A344C", spec["glow"], 2)
        polygon(p, [(780, 494), (830, 475), (848, 540), (780, 540)],
                "#192037")
        polygon(p, [(853, 415), (936, 397), (955, 411), (895, 434)],
                "#15223B", spec["accent"], 2)
        line(p, 707, 459, 848, 421, spec["accent"], 4)
        line(p, 718, 473, 821, 443, spec["glow"], 2)
        for x in (742, 767, 792):
            line(p, x, 448 - (x - 742) * .26,
                 x + 7, 462 - (x - 742) * .26, spec["glow"], 2)
        if self.flash:
            alpha = int(210 * (self.flash / .14))
            p.setPen(Qt.NoPen)
            p.setBrush(color(spec["accent"], max(0, min(255, alpha))))
            polygon(p, [(938, 406), (963, 377), (957, 411), (990, 423),
                        (956, 430)], spec["accent"])

    def _impacts(self, p, spec):
        for part in self.particles:
            fraction = 1 - part["age"] / part["life"]
            opacity = max(0, int(255 * fraction))
            p.save()
            p.translate(part["x"], part["y"])
            p.rotate(part["angle"])
            p.setPen(Qt.NoPen)
            p.setBrush(color(spec["accent"], opacity))
            size = part["size"]
            if spec["kind"] == "petals":
                p.drawEllipse(QRectF(-size, -size * .38, size * 2, size * .76))
            elif spec["kind"] == "ice":
                polygon(p, [(-size, 0), (0, -size), (size, 0),
                            (0, size)], spec["accent"])
            elif spec["kind"] == "sparks":
                p.drawRect(QRectF(-size * .2, -size * 1.4, size * .4, size * 2.8))
            else:
                p.drawEllipse(QPointF(0, 0), size * .6, size * .6)
            p.restore()
        if self.flash:
            p.setPen(QPen(color(spec["accent"], 180), 3))
            p.setBrush(Qt.NoBrush)
            radius = 12 + 38 * (1 - self.flash / .14)
            p.drawEllipse(self.last_hit, radius, radius)

    def _hud(self, p, spec):
        p.fillRect(QRectF(0, 0, SCENE_W, 66), color("#080B17", 185))
        p.setPen(color("#FFFFFF"))
        p.setFont(QFont("Segoe UI", 16, QFont.Bold))
        p.drawText(QRectF(29, 12, 560, 32), Qt.AlignVCenter, self.pack)
        p.setPen(color(spec["accent"]))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(30, 39, 720, 20), Qt.AlignVCenter,
                   "INTERACTIVE CONCEPT / CLICK THE SCENE TO TEST IMPACTS")
        p.setPen(color("#FFFFFF", 165))
        p.drawText(QRectF(700, 16, 233, 30), Qt.AlignRight | Qt.AlignVCenter,
                   "LOCAL SHOWROOM  /  NO GAME MOD")
        p.fillRect(QRectF(0, 518, SCENE_W, 22), color("#080B17", 185))
        p.setPen(color("#FFFFFF", 155))
        p.drawText(QRectF(18, 519, 915, 20), Qt.AlignVCenter,
                   "ORIGINAL VECTOR ART  ·  SIMULATED COSMETICS  ·  FPS-FIRST EFFECT BUDGET")


class ReduxShowroom(QDialog):
    """Switch between four concepts, shoot effects and export original artwork."""
    def __init__(self, parent=None, initial_pack="SAKURA DREAM",
                 reduce_motion=False):
        super().__init__(parent)
        self.setWindowTitle("NAMELESS REDUX  /  LIVE CONCEPT SHOWROOM")
        self.resize(1080, 800)
        self.setMinimumSize(710, 615)
        self._sound_dir = None
        self._sound = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(13)

        header = QHBoxLayout()
        title = QLabel("REDUX / LIVE SHOWROOM")
        title.setObjectName("showroomTitle")
        header.addWidget(title)
        header.addStretch()
        self.pack_select = ClickOnlyComboBox()
        self.pack_select.setObjectName("showroomPackSelect")
        self.pack_select.addItems(list(PACKS))
        header.addWidget(self.pack_select)
        layout.addLayout(header)

        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setObjectName("showroomDescription")
        layout.addWidget(self.description)
        self.canvas = ShowroomCanvas(self, pack=initial_pack)
        layout.addWidget(self.canvas, 1)

        actions = QHBoxLayout()
        self.fire_button = QPushButton("TEST IMPACT  /  FIRE")
        self.fire_button.setObjectName("showroomFire")
        self.fire_button.clicked.connect(
            lambda: self.canvas.fire_at(QPointF(605, 265)))
        actions.addWidget(self.fire_button)

        self.motion_check = QCheckBox("Motion")
        self.motion_check.setChecked(not reduce_motion)
        self.motion_check.toggled.connect(self.canvas.set_motion_enabled)
        actions.addWidget(self.motion_check)
        self.audio_check = QCheckBox("Original shot audio")
        self.audio_check.setChecked(True)
        actions.addWidget(self.audio_check)
        actions.addStretch()

        self.save_button = QPushButton("SAVE CONCEPT PNG")
        self.save_button.clicked.connect(self.save_snapshot)
        actions.addWidget(self.save_button)
        garage = QPushButton("COSMETIC GARAGE  ↗")
        garage.clicked.connect(self.open_cosmetics)
        actions.addWidget(garage)
        close_button = QPushButton("CLOSE")
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        layout.addLayout(actions)

        self.status = QLabel(
            "Concept-only demo. No ROB RUN files, processes or accounts are modified.")
        self.status.setWordWrap(True)
        self.status.setObjectName("showroomStatus")
        layout.addWidget(self.status)

        self.pack_select.currentTextChanged.connect(self.change_pack)
        self.canvas.fired.connect(self.shot_fired)
        self.pack_select.setCurrentText(initial_pack)
        self.change_pack(initial_pack)
        self.canvas.set_motion_enabled(not reduce_motion)

        self.setStyleSheet("""
            QDialog { background: #101427; color: #F4F5FF; }
            QLabel { color: #E9E9FF; }
            QLabel#showroomTitle { font-size: 20px; font-weight: 800; }
            QLabel#showroomDescription { color: #D3CCE7; font-size: 13px; }
            QLabel#showroomStatus { color: #B6BDD6; font-size: 11px; }
            QComboBox, QPushButton {
                background: #262747; border: 1px solid #64608B;
                border-radius: 9px; color: #F6F1FF;
                padding: 10px 14px; font-size: 12px;
            }
            QComboBox::drop-down { border: none; }
            QPushButton:hover { background: #38355D; }
            QPushButton#showroomFire {
                background: #A78DEB; color: #151325; font-weight: 800;
            }
            QCheckBox { color: #E9E9FF; spacing: 7px; }
            QWidget#reduxShowroomCanvas {
                background: #101427; border: 1px solid #6A5C99;
                border-radius: 12px;
            }
        """)

    def change_pack(self, name):
        if name not in PACKS:
            return
        self.canvas.set_pack(name)
        self.description.setText(PACKS[name]["description"] +
                                 "  /  preview-only, not installed in ROB RUN")
        self.status.setText(
            "Original " + PACKS[name]["kind"] +
            " • " + str(PACKS[name]["particles"]) +
            " particles per hit • no in-game changes")

    def shot_fired(self, name):
        self.status.setText(
            name + " impact simulated in NAMELESS • " +
            str(PACKS[name]["particles"]) + " particles • no ROB RUN changes")
        if self.audio_check.isChecked():
            self.play_original_audio(name)

    def play_original_audio(self, name):
        try:
            from PySide6.QtMultimedia import QSoundEffect
            if self._sound_dir is None:
                self._sound_dir = tempfile.TemporaryDirectory(
                    prefix="nameless_showroom_")
            path = Path(self._sound_dir.name) / (
                name.lower().replace(" ", "-") + ".wav")
            if not path.exists():
                path.write_bytes(original_shot_wav(name))
            if self._sound is None:
                self._sound = QSoundEffect(self)
                self._sound.setVolume(.24)
            if self._sound.source() != QUrl.fromLocalFile(str(path)):
                self._sound.setSource(QUrl.fromLocalFile(str(path)))
            self._sound.play()
        except (ImportError, OSError, RuntimeError):
            self.audio_check.setChecked(False)
            self.status.setText(
                "Original audio unavailable on this device; visual demo still works.")

    def open_cosmetics(self):
        """Move from world effects to original cosmetic concept designs."""
        garage = CosmeticGarage(self, initial_pack=self.canvas.pack)
        garage.exec()

    def save_snapshot(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save original Redux concept artwork",
            self.canvas.pack.lower().replace(" ", "-") + "-concept.png",
            "PNG image (*.png)")
        if not filename:
            return
        try:
            if not self.canvas.snapshot().save(filename, "PNG"):
                raise OSError("PNG export failed")
            self.status.setText("Concept artwork saved • no game files touched")
        except OSError as exc:
            QMessageBox.warning(self, "Could not export concept", str(exc))

    def closeEvent(self, event):
        self.canvas._timer.stop()
        if self._sound is not None:
            self._sound.stop()
            self._sound.setSource(QUrl())
        if self._sound_dir is not None:
            self._sound_dir.cleanup()
            self._sound_dir = None
        super().closeEvent(event)
