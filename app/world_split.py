"""Draggable before/after comparison with live image grading, preview only."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QImage, QPixmap
from PySide6.QtWidgets import QWidget

class SplitPreview(QWidget):
    positionChanged = Signal(float)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.before=QImage();self.after=QImage();self.ratio=.5
        self.setMinimumHeight(250)
        self.setMouseTracking(True)
    def set_images(self,before,after):
        self.before=before;self.after=after;self.update()
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:self._move(event.position().x())
    def mouseMoveEvent(self,event):
        if event.buttons() & Qt.LeftButton:self._move(event.position().x())
    def _move(self,x):
        self.ratio=max(.03,min(.97,x/max(1,self.width())))
        self.positionChanged.emit(self.ratio);self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(),QColor("#0D0B17"))
        w,h=self.width(),self.height()
        if not self.before.isNull() and not self.after.isNull():
            for image,left,right in ((self.before,0,int(w*self.ratio)),
                                     (self.after,int(w*self.ratio),w)):
                pix=QPixmap.fromImage(image).scaled(w,h,Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
                source_x=max(0,(pix.width()-w)//2)
                p.save();p.setClipRect(left,0,right-left,h)
                p.drawPixmap(-source_x,-max(0,(pix.height()-h)//2),pix)
                p.restore()
        split=int(w*self.ratio)
        p.setPen(QPen(QColor("#FFB7EA"),2));p.drawLine(split,0,split,h)
        p.setBrush(QColor("#25172D"));p.setPen(QPen(QColor("#FFB7EA"),2))
        p.drawEllipse(split-17,h//2-17,34,34)
        p.setPen(QColor("white"));p.drawText(split-10,h//2+5,"‹ ›")
        p.setPen(QColor("#FFFFFF"));p.drawText(18,25,"BEFORE")
        p.drawText(max(split+10,w-62),25,"AFTER")
        p.end()
