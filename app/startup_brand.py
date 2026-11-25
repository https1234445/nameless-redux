"""Branded startup splash and runtime window icon for NAMELESS REDUX.

This only appears after Windows allows the executable to run. It cannot
suppress or replace Windows Defender SmartScreen.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSplashScreen


def brand_pixmap(width=720, height=390):
    image = QPixmap(width, height)
    image.fill(QColor("#0C1020"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    gradient = QLinearGradient(0, 0, width, height)
    gradient.setColorAt(0, QColor("#111C34"))
    gradient.setColorAt(0.55, QColor("#19142D"))
    gradient.setColorAt(1, QColor("#08121D"))
    painter.fillRect(image.rect(), gradient)
    painter.setPen(QPen(QColor("#5B456F"), 2))
    painter.drawRoundedRect(15, 15, width - 30, height - 30, 20, 20)
    painter.setPen(QColor("#92E6EF"))
    painter.setFont(QFont("Segoe UI", 15, QFont.Bold))
    painter.drawText(58, 88, "N  /  R")
    painter.setPen(QColor("#F7F3FF"))
    painter.setFont(QFont("Segoe UI", 40, QFont.Black))
    painter.drawText(55, 185, "NAMELESS")
    painter.setPen(QColor("#B2A3E8"))
    painter.setFont(QFont("Segoe UI", 25, QFont.Bold))
    painter.drawText(58, 233, "R E D U X")
    painter.setPen(QColor("#B8C4DC"))
    painter.setFont(QFont("Segoe UI", 12))
    painter.drawText(58, 285, "ROB RUN COMPANION  /  FPS LAB  /  PING LAB")
    painter.fillRect(58, height - 69, width - 116, 3, QColor("#323C5C"))
    painter.fillRect(58, height - 69, int((width - 116) * .72), 3,
                     QColor("#91E4ED"))
    painter.setPen(QColor("#A7B1C9"))
    painter.drawText(58, height - 35, "INITIALIZING YOUR WORKSPACE")
    painter.end()
    return image


def app_icon():
    pix = QPixmap(128, 128)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#17152D"))
    p.setPen(QPen(QColor("#8FE7F2"), 5))
    p.drawRoundedRect(7, 7, 114, 114, 24, 24)
    p.setPen(QColor("#F5F0FF"))
    p.setFont(QFont("Segoe UI", 57, QFont.Black))
    p.drawText(pix.rect(), Qt.AlignCenter, "N")
    p.end()
    return QIcon(pix)


def startup_splash():
    splash = QSplashScreen(brand_pixmap())
    splash.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    splash.show()
    return splash
