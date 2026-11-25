"""WORLD REBORN: interactive cinematic home, using bundled artwork.

Preview-only. Never edits ROB RUN or its assets.
"""
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (QWidget, QLabel, QFrame, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QSlider, QScrollArea, QGraphicsDropShadowEffect)
from art_pack import art_candidates
from world_split import SplitPreview

PACKS = [
    ("SAKURA DREAM", "Spring vibes, soft light and cherry petals.", "sakura_dream.jpg", "#F58ACA"),
    ("NEON NIGHT", "City lights, deep neon and cyber atmosphere.", "neon_night.jpg", "#BB78FA"),
    ("FROSTBITE", "Cold terrain, snow and frozen style.", "frostbite.jpg", "#8CCFFF"),
    ("CRIMSON", "Burning sky, warm shadows and bold contrast.", "crimson.jpg", "#FF817F"),
]

def art(name):
    for path in art_candidates(name):
        if path.is_file():
            image = QImage(str(path))
            if not image.isNull():
                return image
    return QImage()

class ArtLabel(QLabel):
    def __init__(self, image=None, height=160):
        super().__init__()
        self.image = image if image is not None else QImage()
        self.setMinimumHeight(height)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background:#11101D; border-radius:11px;")
    def set_image(self, image):
        self.image = image
        self.update_image()
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_image()
    def update_image(self):
        if not self.image.isNull() and self.width()>0 and self.height()>0:
            pix = QPixmap.fromImage(self.image).scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            left = max(0, (pix.width()-self.width())//2)
            top = max(0, (pix.height()-self.height())//2)
            crop = pix.copy(left, top, self.width(), self.height())
            self.setPixmap(crop)
        else:
            self.setText("PREVIEW UNAVAILABLE")

class WorldReborn(QWidget):
    """Reference-inspired collection screen. All actions remain NAMELESS-only."""
    open_collection = Signal()
    open_visual_lab = Signal()
    open_cosmetics = Signal(str)
    apply_look = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pack = 0
        self.angle = 0
        self.controls = {}
        self.setObjectName("rebornRoot")
        self.setStyleSheet("""
            QWidget#rebornRoot {background:#0B0911;color:#F8EAF6;}
            QFrame#worldPanel {background:#14101B;border:1px solid #4D344D;border-radius:13px;}
            QLabel#worldHeading {font-size:28px;font-weight:900;color:#F7F0F8;}
            QLabel#worldMuted {font-size:12px;color:#C9B9C9;}
            QLabel#worldPack {font-size:16px;font-weight:800;color:#FFFFFF;}
            QPushButton {background:#241625;color:#FFE8FA;border:1px solid #6B3D66;
                border-radius:8px;padding:7px;font-weight:700;}
            QPushButton:hover {background:#472244;border-color:#FF91D8;}
            QPushButton#worldPrimary {background:#77205D;border:2px solid #FF81D0;
                color:#FFFFFF;font-size:14px;font-weight:900;padding:12px;}
            QSlider::groove:horizontal {height:5px;background:#4A3D4C;border-radius:2px;}
            QSlider::handle:horizontal {background:#FFFFFF;width:16px;margin:-6px 0;border-radius:8px;}
            QSlider::sub-page:horizontal {background:#E66AB9;}
        """)
        outer=QVBoxLayout(self)
        outer.setContentsMargins(8,8,8,8)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:0;}")
        outer.addWidget(scroll)
        body=QWidget()
        scroll.setWidget(body)
        root=QVBoxLayout(body)
        root.setContentsMargins(7,7,7,12)
        root.setSpacing(13)

        heading=QLabel("Redux Collection")
        heading.setObjectName("worldHeading")
        root.addWidget(heading)
        subtitle=QLabel("Four unique worlds. One ride.")
        subtitle.setObjectName("worldMuted")
        root.addWidget(subtitle)

        top=QHBoxLayout()
        top.setSpacing(13)
        root.addLayout(top,3)
        grid=QGridLayout()
        grid.setSpacing(10)
        top.addLayout(grid,5)
        self.cards=[]
        for idx,(name,description,filename,color) in enumerate(PACKS):
            card=QFrame()
            card.setObjectName("worldPanel")
            cl=QVBoxLayout(card)
            cl.setContentsMargins(6,6,6,9)
            cl.setSpacing(5)
            cover=ArtLabel(art(filename),145)
            cl.addWidget(cover,1)
            label=QLabel(name.title())
            label.setObjectName("worldPack")
            cl.addWidget(label)
            hint=QLabel(description)
            hint.setObjectName("worldMuted")
            hint.setWordWrap(True)
            cl.addWidget(hint)
            button=QPushButton("SELECT WORLD")
            button.clicked.connect(lambda checked=False,i=idx:self.select_pack(i))
            cl.addWidget(button)
            grid.addWidget(card,idx//2,idx%2)
            self.cards.append((card,button))

        hero=QFrame()
        hero.setObjectName("worldPanel")
        top.addWidget(hero,8)
        hl=QVBoxLayout(hero)
        hl.setContentsMargins(12,10,12,11)
        hl.setSpacing(9)
        self.hero_image=ArtLabel(height=300)
        hl.addWidget(self.hero_image,1)
        self.hero_title=QLabel()
        self.hero_title.setObjectName("worldHeading")
        hl.addWidget(self.hero_title)
        self.hero_desc=QLabel()
        self.hero_desc.setObjectName("worldMuted")
        self.hero_desc.setWordWrap(True)
        hl.addWidget(self.hero_desc)
        angles=QHBoxLayout()
        angles.setSpacing(6)
        hl.addLayout(angles)
        self.angle_buttons=[]
        for idx,label in enumerate(("FULL VIEW","DETAIL 1","DETAIL 2","DETAIL 3","DETAIL 4")):
            b=QPushButton(label)
            b.clicked.connect(lambda checked=False,i=idx:self.select_angle(i))
            angles.addWidget(b)
            self.angle_buttons.append(b)
        actions=QHBoxLayout()
        hl.addLayout(actions)
        preview=QPushButton("▷  PREVIEW HERE")
        preview.setObjectName("worldPrimary")
        preview.clicked.connect(self.open_collection.emit)
        actions.addWidget(preview,2)
        cosmetics=QPushButton("COSMETICS")
        cosmetics.clicked.connect(lambda:self.open_cosmetics.emit(PACKS[self.pack][0]))
        actions.addWidget(cosmetics,1)
        apply=QPushButton("✓  ACTIVATE IN NAMELESS")
        apply.clicked.connect(lambda:self.apply_look.emit(PACKS[self.pack][0]))
        hl.addWidget(apply)
        for caption in ("✓  Custom Livery", "✓  Unique Atmosphere",
                        "✓  Matching Visuals", "✓  Preview Ready"):
            item=QLabel(caption)
            item.setStyleSheet("color:#EAB5DB;font-size:12px;padding-left:8px;")
            hl.addWidget(item)
        disclaimer=QLabel("CONCEPT PREVIEW ONLY  •  NO ROB RUN FILES CHANGED")
        disclaimer.setObjectName("worldMuted")
        hl.addWidget(disclaimer)

        bottom=QFrame()
        bottom.setObjectName("worldPanel")
        root.addWidget(bottom,2)
        bl=QVBoxLayout(bottom)
        bl.setContentsMargins(12,12,12,12)
        bl.setSpacing(10)
        header=QHBoxLayout()
        bl.addLayout(header)
        visual=QLabel("☷  Visual Lab")
        visual.setObjectName("worldHeading")
        header.addWidget(visual)
        intro=QLabel("Tune the look. See the difference.")
        intro.setObjectName("worldMuted")
        header.addWidget(intro)
        header.addStretch()
        full=QPushButton("OPEN FULL VISUAL LAB")
        full.clicked.connect(self.open_visual_lab.emit)
        header.addWidget(full)
        comparison=QHBoxLayout()
        comparison.setSpacing(14)
        bl.addLayout(comparison)
        self.split=SplitPreview()
        comparison.addWidget(self.split,7)
        control_frame=QFrame()
        control_frame.setObjectName("worldPanel")
        comparison.addWidget(control_frame,4)
        controls=QVBoxLayout(control_frame)
        controls.setContentsMargins(12,10,12,10)
        for key,minimum,maximum,default in (
            ("Brightness",-100,100,18),("Contrast",-100,100,24),
            ("Saturation",-100,100,37),("Temperature",-100,100,12)):
            line=QHBoxLayout()
            controls.addLayout(line)
            text=QLabel(key)
            text.setMinimumWidth(86)
            line.addWidget(text)
            slider=QSlider(Qt.Horizontal)
            slider.setRange(minimum,maximum)
            slider.setValue(default)
            slider.valueChanged.connect(self.update_after)
            line.addWidget(slider,1)
            val=QLabel(f"{default:+d}")
            val.setMinimumWidth(34)
            line.addWidget(val)
            self.controls[key]=(slider,val)
        self.source=art("rob_run_preview.jpg")
        if self.source.isNull():
            self.source=art("sakura_dream.jpg")
        self.select_pack(0)
        self.update_after()

    def select_pack(self,index):
        self.pack=index
        self.angle=0
        name,desc,filename,color=PACKS[index]
        self.hero_title.setText(name)
        self.hero_desc.setText("SIGNATURE REDUX  /  "+desc)
        for i,(card,button) in enumerate(self.cards):
            active=i==index
            card.setStyleSheet("QFrame#worldPanel {background:#1B1120;border:"+
                ("2px solid "+color if active else "1px solid #51394F")+
                ";border-radius:13px;}")
            button.setText("✓ SELECTED" if active else "SELECT WORLD")
        self.select_angle(0)

    def select_angle(self,index):
        self.angle=index
        image=art(PACKS[self.pack][2])
        if index and not image.isNull():
            w,h=image.width(),image.height()
            regions=((0,0,w,h),(0,0,w//2,h//2),(w//2,0,w//2,h//2),
                     (0,h//2,w//2,h//2),(w//2,h//2,w//2,h//2))
            x,y,cw,ch=regions[index]
            image=image.copy(x,y,cw,ch)
        self.hero_image.set_image(image)
        for i,b in enumerate(self.angle_buttons):
            b.setStyleSheet("border:2px solid #FF8BD6;background:#532449;" if i==index else "")

    def update_after(self,*_):
        if self.source.isNull():
            return
        values={key:slider.value() for key,(slider,label) in self.controls.items()}
        for key,(slider,label) in self.controls.items():
            label.setText(f"{slider.value():+d}")
        img=self.source.scaled(480,270,Qt.KeepAspectRatio,Qt.SmoothTransformation).convertToFormat(QImage.Format_RGB32)
        bright=values["Brightness"]*1.25
        contrast=1+values["Contrast"]/150
        saturation=max(0,1+values["Saturation"]/100)
        temp=values["Temperature"]*.45
        for y in range(img.height()):
            for x in range(img.width()):
                p=QColor(img.pixel(x,y))
                rr,gg,bb=p.red(),p.green(),p.blue()
                gray=.2126*rr+.7152*gg+.0722*bb
                rr=(gray+(rr-gray)*saturation-127)*contrast+127+bright+temp
                gg=(gray+(gg-gray)*saturation-127)*contrast+127+bright
                bb=(gray+(bb-gray)*saturation-127)*contrast+127+bright-temp
                img.setPixelColor(x,y,QColor(max(0,min(255,int(rr))),
                    max(0,min(255,int(gg))),max(0,min(255,int(bb)))))
        self.split.set_images(self.source,img)
