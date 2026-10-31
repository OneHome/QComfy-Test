from PyQt5.QtCore import Qt, QPointF, QRectF, QSizeF, QPoint
from PyQt5.QtQuick import QQuickFramebufferObject
from PyQt5.QtGui import QRadialGradient, QColor, QPainter, QPolygonF, QOpenGLPaintDevice, QImage, QRadialGradient, QGuiApplication, QPen
import OpenGL.GL as gl
import PIL.Image
import copy
import time

#import cv2
#import numpy as np
#np.seterr("ignore")

from canvas.shared import *

FILL_TOLERANCE = 48 # summed (premultiplied) RGBA difference accepted by the bucket fill
FILL_UNDER = 32 # max pixels the fill reaches under the soft edge of neighbouring strokes (no halo)
FILL_BARRIER = 230 # pixels at least this opaque (alpha 0-255) stop that growth
UNDO_LIMIT = 20

class CanvasRendererBuffer():
    def __init__(self, size, buffer):
        self.buffer = buffer
        self.size = size
        self.opacity = 1.0
        self.visible = True
        self.source = None
        self.cached = None

        self.initial = True

    def initialize(self):
        if self.initial:
            self.initial = False
            self.buffer.bind()
            gl.glClearColor(0, 0, 0, 0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)

    def getImage(self):
        if self.cached == None:
            self.cached = self.buffer.toImage()
        return self.cached

    def getThumbnail(self, size=128):
        img = self.getImage().scaledToWidth(size, mode=Qt.SmoothTransformation)
        return img

    def beginPaint(self):
        self.buffer.bind()
        self.cached = None
        self.device = QOpenGLPaintDevice(self.size)
        self.painter = QPainter(self.device)
        self.painter.beginNativePainting()
        return self.painter
    
    def endPaint(self):
        self.painter.endNativePainting()
        self.painter.end()
        self.device = None
    
class CanvasRenderer(QQuickFramebufferObject.Renderer):
    def __init__(self, size):
        super().__init__()
        self.changes = None
        self.display = None
        self.buffer = None
        self.size = None
        self.setup(size)
    
    def setup(self, size):
        if self.size and self.size != size:
            self.invalidateFramebufferObject()

        self.size = size

        self.layers = {}
        self.layersOrder = []

        self.activeTool = None
        self.activeBrush = None
        self.activeSelection = None
        self.activeLayer = -1

        self.changed = False
        self.sample = None

        self.undoStack = []
        self.redoStack = []
        self.dirty = False
        self.floating = None

    def createBuffer(self, size):
        buffer = super().createFramebufferObject(size)
        return CanvasRendererBuffer(size, buffer)
    
    def resizeBuffer(self, buffer, newSize):
        newBuffer = super().createFramebufferObject(newSize)
        oldBuffer = buffer.buffer
        buffer.buffer = newBuffer
        buffer.size = newSize

        painter = buffer.beginPaint()
        gl.glClearColor(0, 0, 0, 0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        painter.drawImage(0,0,oldBuffer.toImage())
        buffer.endPaint()
    
    def getLayer(self, key):
        return self.layers[key]
        
    def createFramebufferObject(self, size):
        #print("CREATE", self.size)
        self.display = self.createBuffer(self.size)
        self.buffer = self.createBuffer(self.size)

        self.states = []

        return self.display.buffer
    
    def synchronize(self, canvas):
        if canvas.synchronize(self):
            self.changes = canvas.getChanges()

    def render(self):
        if not self.size or self.size.width() == 1:
            return
        
        gl.glClearColor(0, 0, 0, 0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        self.display.initialize()
        self.buffer.initialize()
        for key in self.layers:
            self.layers[key].initialize()

        if not self.layersOrder or not self.display:
            return

        if self.changes.operations:
            self.applyOperations()

        self.renderDisplay()

        if CanvasOperation.SAMPLE_COLOR in self.changes.operations and self.changes.strokes:
            point = self.changes.strokes[-1].toPoint()
            if point.x() >= 0 and point.x() < self.size.width() and point.y() >= 0 and point.y() < self.size.height():
                self.sample = self.display.getImage().pixelColor(point)

    def renderDisplay(self):
        painter = self.display.beginPaint()
        gl.glClearColor(0, 0, 0, 0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        for key in self.layersOrder:
            layer = self.layers[key]
            if not layer.visible:
                continue
            layerImage = layer.getImage()

            if key == self.activeLayer and not self.activeBrush._exclusive:
                layerImage = QImage(layerImage)
                layerPainter = QPainter(layerImage)
                if self.floating is not None:
                    layerPainter.drawImage(self.floating["origin"] + self.floating.get("offset", QPoint(0, 0)), self.floating["image"])
                layerPainter.setOpacity(self.activeBrush.opacity)
                layerPainter.setCompositionMode(self.activeBrush.mode)
                layerPainter.drawImage(0, 0, self.buffer.getImage())
                layerPainter.end()
            
            painter.drawImage(0,0,layerImage)

        if self.activeBrush._exclusive:
            painter.setCompositionMode(self.activeBrush.mode)
            painter.drawImage(0,0,self.buffer.getImage())

        self.display.endPaint()

    def applySources(self):
        for key in self.layersOrder:
            layer = self.layers[key]
            if layer.source:
                painter = layer.beginPaint()
                painter.drawImage(0,0,layer.source)
                layer.endPaint()
                layer.source = None

    def snapshot(self):
        # images of the layers an edit can touch
        if self.activeBrush is not None and self.activeBrush._exclusive:
            keys = list(self.layersOrder)
        else:
            keys = [self.activeLayer] if self.activeLayer in self.layers else []
        return {key: self.layers[key].getImage() for key in keys}

    def pushUndo(self):
        self.undoStack.append(self.snapshot())
        del self.undoStack[:-UNDO_LIMIT]
        self.redoStack.clear()

    def clearLayerBuffer(self, layer, image=None):
        painter = layer.beginPaint()
        gl.glClearColor(0, 0, 0, 0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        if image is not None:
            painter.drawImage(0, 0, image)
        layer.endPaint()

    def applyHistory(self, source, destination):
        if not source:
            return
        state = source.pop()
        destination.append({key: self.layers[key].getImage() for key in state if key in self.layers})
        for key, image in state.items():
            if key in self.layers:
                self.clearLayerBuffer(self.layers[key], image)
        self.changed = True

    def applyClear(self):
        if self.activeLayer in self.layers:
            self.pushUndo()
            self.clearLayerBuffer(self.layers[self.activeLayer])
            self.changed = True

    @staticmethod
    def connectedRegion(mask, x, y):
        """Pixels of `mask` (bool array) connected to (x, y): scanline flood fill, numpy only."""
        if not mask[y, x]:
            return None
        h, w = mask.shape
        out = np.zeros_like(mask)
        stack = [(x, y)]
        while stack:
            sx, sy = stack.pop()
            if out[sy, sx] or not mask[sy, sx]:
                continue
            bad = np.flatnonzero(~mask[sy])
            i = int(np.searchsorted(bad, sx))
            left = int(bad[i-1]) + 1 if i > 0 else 0
            right = int(bad[i]) if i < len(bad) else w
            out[sy, left:right] = True
            for ny in (sy-1, sy+1):
                if 0 <= ny < h:
                    cand = mask[ny, left:right] & ~out[ny, left:right]
                    if cand.any():
                        starts = np.flatnonzero(cand & ~np.concatenate(([False], cand[:-1])))
                        for st in starts:
                            stack.append((left + int(st), ny))
        return out

    @staticmethod
    def dilate(mask):
        grown = mask.copy()
        grown[1:] |= mask[:-1]
        grown[:-1] |= mask[1:]
        grown[:, 1:] |= mask[:, :-1]
        grown[:, :-1] |= mask[:, 1:]
        return grown

    @classmethod
    def fillArray(cls, arr, x, y, color, opacity, erase=False):
        """Bucket fill on a straight-alpha RGBA uint8 array, in place. Returns False if nothing changed.
        Pixels are compared in premultiplied space (so nearly transparent soft edges join the region). When
        filling an empty area, the fill also goes UNDER the soft (partially transparent) edge of the strokes
        around it, which removes the halo; when recoloring a shape, its antialiased fringe takes the new color."""
        alpha = arr[..., 3]
        a = alpha[..., None].astype(np.int16)
        pre = np.concatenate([arr[..., :3].astype(np.int16) * a // 255, a], axis=2)
        seed_pre = pre[y, x].copy()
        seed = arr[y, x].astype(np.int16)
        mask = np.abs(pre - seed_pre).sum(axis=2) <= FILL_TOLERANCE
        region = cls.connectedRegion(mask, x, y)
        if region is None or not region.any():
            return False

        if erase:
            arr[region] = 0
            return True

        r, g, b = color
        fa = float(opacity)

        if seed[3] < 128:
            # reach through the partially transparent pixels (soft edge) around the region, up to FILL_UNDER px
            soft = (alpha > 0) & (alpha < FILL_BARRIER)
            under = region.copy()
            for _ in range(FILL_UNDER):
                grown = cls.dilate(under) & (soft | region)
                if np.array_equal(grown, under):
                    break
                under = grown
            ring = under & ~region
        else:
            grown = region
            for _ in range(2):
                grown = cls.dilate(grown)
            ring = grown & ~region
            near = np.abs(arr[..., :3].astype(np.int16) - seed[:3]).sum(axis=2) <= FILL_TOLERANCE * 2
            fringe = ring & near & (alpha > 0)

        if seed[3] < 128 and ring.any():
            p = arr[ring].astype(np.float32) / 255.0
            pa = p[:, 3:4]
            out_a = pa + fa * (1.0 - pa)
            out_rgb = (p[:, :3] * 255.0 * pa + np.array([r, g, b], np.float32) * fa * (1.0 - pa)) / np.maximum(out_a, 1e-6)
            arr[ring] = np.clip(np.concatenate([out_rgb, out_a * 255.0], axis=1) + 0.5, 0, 255).astype(np.uint8)

        arr[region] = (r, g, b, int(round(fa * 255)))
        if seed[3] >= 128:
            arr[fringe, 0] = r
            arr[fringe, 1] = g
            arr[fringe, 2] = b
        return True

    def applyFill(self, point):
        if self.activeBrush is None or self.activeBrush._exclusive or self.activeLayer not in self.layers:
            return
        layer = self.layers[self.activeLayer]
        image = layer.getImage()
        x, y = int(point.x()), int(point.y())
        if not (0 <= x < image.width() and 0 <= y < image.height()):
            return

        arr = np.array(QImagetoPIL(image))
        erase = self.activeBrush.mode == QPainter.CompositionMode_DestinationOut
        c = self.activeBrush._color
        if not self.fillArray(arr, x, y, (c.red(), c.green(), c.blue()), self.activeBrush.opacity, erase):
            return

        self.pushUndo()
        self.clearLayerBuffer(layer, PILtoQImage(PIL.Image.fromarray(arr, "RGBA")))
        self.changed = True

    def applyMove(self, delta, selection):
        # lift the selection (or the whole layer) the first time, then keep it floating at the new offset
        if self.activeBrush is None or self.activeBrush._exclusive or self.activeLayer not in self.layers:
            return
        layer = self.layers[self.activeLayer]
        if self.floating is None:
            image = layer.getImage()
            rect = (selection.toAlignedRect() if selection is not None else image.rect()).intersected(image.rect())
            if rect.isEmpty():
                return
            self.pushUndo()
            hole = QImage(image)
            painter = QPainter(hole)
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, Qt.transparent)
            painter.end()
            self.floating = {"image": image.copy(rect), "origin": rect.topLeft()}
            self.clearLayerBuffer(layer, hole)
        self.floating["offset"] = QPoint(int(delta[0]), int(delta[1]))

    def applyMoveCommit(self):
        floating = self.floating
        self.floating = None
        if floating is None or self.activeLayer not in self.layers:
            return
        painter = self.layers[self.activeLayer].beginPaint()
        painter.drawImage(floating["origin"] + floating.get("offset", QPoint(0, 0)), floating["image"])
        self.layers[self.activeLayer].endPaint()
        self.changed = True

    def applyShape(self):
        start, end = self.changes.shape
        brush = self.activeBrush
        color = QColor(brush._color)
        color.setAlphaF(1.0)

        painter = self.buffer.beginPaint()
        gl.glClearColor(0, 0, 0, 0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self.activeTool == CanvasTool.LINE:
            painter.setPen(QPen(color, brush.size, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(start, end)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            rect = QRectF(start, end).normalized()
            if self.activeTool == CanvasTool.RECT:
                painter.drawRect(rect)
            else:
                painter.drawEllipse(rect)
        self.buffer.endPaint()
        self.dirty = True

    def applyOperations(self):
        self.activeLayer = self.changes.layer
        self.activeBrush = self.changes.brush
        self.activeTool = self.changes.tool
        
        if CanvasOperation.LOAD in self.changes.operations:
            self.applySources()

        if CanvasOperation.UNDO in self.changes.operations:
            for _ in range(self.changes.undo):
                self.applyHistory(self.undoStack, self.redoStack)
            for _ in range(self.changes.redo):
                self.applyHistory(self.redoStack, self.undoStack)

        if CanvasOperation.CLEAR in self.changes.operations:
            self.applyClear()

        if CanvasOperation.FILL in self.changes.operations and self.changes.fill is not None:
            self.applyFill(self.changes.fill)

        if CanvasOperation.MOVE_UPDATE in self.changes.operations and self.changes.move is not None:
            self.applyMove(self.changes.move, self.changes.selection)

        if CanvasOperation.MOVE_COMMIT in self.changes.operations:
            self.applyMoveCommit()

        if CanvasOperation.UPDATE_STROKE in self.changes.operations and self.changes.strokes:
            painter = self.buffer.beginPaint()
            brush = self.activeBrush
            
            while self.changes.strokes:
                p = self.changes.strokes.pop(0)

                gradient = QRadialGradient(p.x(), p.y(), brush.size/2)

                steps = max(int(brush.size//4), 3)
                for i in range(0, steps+1):
                    r = i/steps                   
                    if r == 1.0:
                        c =  brush.getDabColor(r)
                        gradient.setColorAt(0.999,c)
                        c.setAlphaF(0.0)
                        gradient.setColorAt(1.0, c)
                    else:
                        gradient.setColorAt(r, brush.getDabColor(r))


                painter.setPen(Qt.NoPen)
                painter.setBrush(gradient)

                painter.drawEllipse(p, brush.size, brush.size)

            self.buffer.endPaint()
            self.dirty = True

        if CanvasOperation.UPDATE_SHAPE in self.changes.operations and self.changes.shape:
            self.applyShape()
        
        if CanvasOperation.STROKE in self.changes.operations:
            if self.dirty:
                self.pushUndo()
                self.dirty = False
            if self.activeBrush._exclusive: # HACK for subprompts
                if self.activeBrush._mode == QPainter.CompositionMode_DestinationOut:
                    for key in self.layersOrder:
                        painter = self.layers[key].beginPaint()
                        painter.setOpacity(self.activeBrush.opacity)
                        painter.setCompositionMode(self.activeBrush.mode)
                        painter.drawImage(0,0,self.buffer.getImage())
                        self.layers[key].endPaint()
                else:
                    for key in self.layersOrder:
                        if key == self.activeLayer:
                            mode = self.activeBrush.mode
                        else:
                            mode = QPainter.CompositionMode_DestinationOut
                        painter = self.layers[key].beginPaint()
                        painter.setOpacity(self.activeBrush.opacity)
                        painter.setCompositionMode(mode)
                        painter.drawImage(0,0,self.buffer.getImage())
                        self.layers[key].endPaint()
            else:
                painter = self.layers[self.activeLayer].beginPaint()
                painter.setOpacity(self.activeBrush.opacity)
                painter.setCompositionMode(self.activeBrush.mode)
                painter.drawImage(0,0,self.buffer.getImage())
                self.layers[self.activeLayer].endPaint()
            
            self.buffer.beginPaint()
            gl.glClearColor(0, 0, 0, 0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            self.buffer.endPaint()
            self.changed = True