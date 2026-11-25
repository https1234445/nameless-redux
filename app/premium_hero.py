"""Original premium editorial hero artwork for the NAMELESS desktop dashboard.

Vector artwork only: no game textures, copyrighted media or network assets.
"""
from math import sin, cos, pi
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QLinearGradient, QRadialGradient, QPolygonF
from PySide6.QtWidgets import QWidget


def col(hexcode, alpha=255):
    c = QColor(hexcode)
    c.setAlpha(alpha)
    return c


class PremiumHero(QWidget):
    """Cinematic neon landscape with readable dark left-side text space."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("premiumHero")
        self.setMinimumHeight(302)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if w < 1 or h < 1:
            return
        p.save()
        p.scale(w / 1000.0, h / 360.0)
        path = QRectF(0, 0, 1000, 360)
        bg = QLinearGradient(0, 0, 1000, 360)
        bg.setColorAt(0, col("#0B1024"))
        bg.setColorAt(.45, col("#17163A"))
        bg.setColorAt(.75, col("#30245A"))
        bg.setColorAt(1, col("#0D2340"))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(path, 20, 20)
        p.setClipRect(path)

        # Cinematic lavender atmosphere and electric moon.
        halo = QRadialGradient(QPointF(805, 138), 235)
        halo.setColorAt(0, col("#D7A8FF", 125))
        halo.setColorAt(.45, col("#A67AF8", 50))
        halo.setColorAt(1, col("#927BFF", 0))
        p.setBrush(halo)
        p.drawEllipse(QPointF(805, 138), 235, 235)
        p.setBrush(col("#D9D0FF", 195))
        p.drawEllipse(QPointF(810, 112), 60, 60)
        p.setBrush(col("#A8A0EC", 135))
        p.drawEllipse(QPointF(822, 105), 53, 53)

        # Distant mountains and neon architecture, all originally drawn.
        p.setBrush(col("#31254D"))
        p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in
            [(360,275),(475,194),(564,258),(659,184),(763,254),
             (856,181),(1000,264),(1000,360),(360,360)]]))
        p.setBrush(col("#141C3C"))
        p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in
            [(405,306),(530,236),(634,299),(745,223),(845,281),
             (931,224),(1000,261),(1000,360),(405,360)]]))
        for i in range(10):
            x = 605 + i * 40
            top = 158 + ((i * 43) % 97)
            p.fillRect(QRectF(x, top, 30, 215), col("#111832"))
            p.setPen(QPen(col("#9578E7", 150), 1))
            p.drawLine(QPointF(x, top), QPointF(x + 30, top))
            for j in range(5):
                p.fillRect(QRectF(x+7, top+12+j*20, 4, 7),
                           col("#69DDEB", 145 if (i+j)%3 else 50))
        p.setPen(QPen(col("#73E5ED", 155), 2))
        p.drawLine(QPointF(560, 295), QPointF(1000, 295))
        p.setBrush(col("#10172E"))
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in
            [(370,328),(570,296),(840,312),(1000,280),(1000,360),(370,360)]]))

        # A concept-only sports coupe silhouette anchors the artwork.
        p.setBrush(col("#0C1125"))
        p.drawEllipse(QPointF(776, 324), 190, 19)
        p.setBrush(col("#282849"))
        p.setPen(QPen(col("#BA98FF"), 3))
        p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in
            [(594,285),(629,256),(694,251),(735,221),(833,222),
             (882,257),(932,267),(956,290),(947,315),(591,315)]]))
        p.setBrush(col("#121D37"))
        p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in
            [(733,252),(750,232),(826,231),(859,257)]]))
        p.setPen(QPen(col("#6FF2EF"), 3))
        p.drawLine(QPointF(604, 296), QPointF(935, 296))
        p.setPen(Qt.NoPen)
        p.setBrush(col("#0B1021"))
        for x in (674, 878):
            p.drawEllipse(QPointF(x,315), 26, 26)
            p.setBrush(col("#9A8CE3"))
            p.drawEllipse(QPointF(x,315), 13, 13)
            p.setBrush(col("#0B1021"))

        # Dark readability veil: foreground copy is added as normal Qt labels.
        veil = QLinearGradient(0, 0, 750, 0)
        veil.setColorAt(0, col("#090E20", 252))
        veil.setColorAt(.50, col("#0B1024", 242))
        veil.setColorAt(.78, col("#0B1024", 145))
        veil.setColorAt(1, col("#0B1024", 0))
        p.fillRect(path, veil)
        p.setPen(QPen(col("#B695FF", 120), 1))
        p.drawRoundedRect(QRectF(1, 1, 998, 358), 20, 20)
        p.restore()
