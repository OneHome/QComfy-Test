from PyQt5.QtCore import pyqtSlot, pyqtProperty, QPointF, QSize, QObject
from PyQt5.QtGui import QImage
from enum import Enum
import io
import numpy as np

import PIL.Image

class CanvasTool(Enum):
    BRUSH = 1
    ERASE = 2
    LINE = 3
    RECT = 4
    ELLIPSE = 5
    FILL = 6
    SELECT = 7
    MOVE = 8

class CanvasOperation(Enum):
    UPDATE_STROKE = 1
    STROKE = 2
    LOAD = 3
    SAMPLE_COLOR = 4
    UPDATE_SHAPE = 5
    FILL = 6
    UNDO = 7
    CLEAR = 8
    MOVE_UPDATE = 9
    MOVE_COMMIT = 10

class CanvasChanges():
    def __init__(self):
        self.reset = False
        self.layer = 1
        self.tool = CanvasTool.ERASE
        self.brush = None
        self.strokes = []
        self.shape = None
        self.fill = None
        self.move = None
        self.selection = None
        self.undo = 0
        self.redo = 0

        self.operations = set()

        self.setup = QSize()

class CanvasWrapper(QObject):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas

def alignQPointF(point):
    return QPointF(point.toPoint())

def PILtoQImage(pil):
    data = pil.convert("RGBA").tobytes("raw", "RGBA")
    img = QImage(data, pil.size[0], pil.size[1], QImage.Format_RGBA8888)
    img.convertTo(QImage.Format_ARGB32_Premultiplied)
    return img

def AlphatoQImage(pil):
    pil = PIL.Image.merge("RGBA", [pil]*4)
    data = pil.tobytes("raw", "RGBA")
    img = QImage(data, pil.size[0], pil.size[1], QImage.Format_RGBA8888)
    img.convertTo(QImage.Format_ARGB32_Premultiplied)
    return img

def QImagetoPIL(img):
    if img.format() == QImage.Format_Grayscale8:
        size = (img.size().width(), img.size().height())
        total = size[0]*size[1]
        return PIL.Image.frombytes("L", size, img.bits().asarray(total), "raw", "L")
    else:
        img = img.convertToFormat(QImage.Format_RGBA8888)
        size = (img.size().width(), img.size().height())
        total = size[0]*size[1]*4
        return PIL.Image.frombytes("RGBA", size, img.bits().asarray(total), "raw", "RGBA")

def QImagetoCV2(img):
    img = img.convertToFormat(QImage.Format_RGBA8888)
    size = (img.size().width(), img.size().height())
    total = size[0]*size[1]*4
    arr = np.array(img.bits().asarray(total)).reshape(size[1], size[0], 4)
    return arr

def CV2toQImage(mat):
    width, height, _ = mat.shape
    data = mat.tobytes()
    img = QImage(data, width, height, QImage.Format_RGBA8888)
    img.convertTo(QImage.Format_ARGB32_Premultiplied)
    return img