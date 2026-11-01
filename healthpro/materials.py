"""Native AppKit glass around Qt controls; opaque, readable cross-platform fallback."""
import ctypes
from pathlib import Path
import sys
from PyQt6.QtCore import QTimer, Qt, QRectF
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QPen, QPainterPath
from PyQt6.QtWidgets import QApplication, QFrame, QWidget


class NativeMaterials:
    def __init__(self):
        self.lib = None
        self.error = ""
        self._path_done = None
        if sys.platform != "darwin" or QApplication.platformName() != "cocoa":
            return
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        candidates = [root / "native/libhealthpro_glass.dylib", root / "build/native/libhealthpro_glass.dylib"]
        try:
            path = next(p for p in candidates if p.exists())
            lib = ctypes.CDLL(str(path))
            lib.hp_glass_attach.argtypes = [ctypes.c_void_p]
            lib.hp_glass_attach.restype = ctypes.c_void_p
            lib.hp_glass_sync.argtypes = [ctypes.c_void_p, ctypes.c_int]
            lib.hp_glass_sync.restype = None
            lib.hp_glass_detach.argtypes = [ctypes.c_void_p]
            lib.hp_glass_detach.restype = None
            lib.hp_glass_kind.argtypes = [ctypes.c_void_p]
            lib.hp_glass_kind.restype = ctypes.c_int
            lib.hp_glass_valid.argtypes = [ctypes.c_void_p]
            lib.hp_glass_valid.restype = ctypes.c_int
            lib.hp_glass_appearance_matches.argtypes = [ctypes.c_void_p, ctypes.c_int]
            lib.hp_glass_appearance_matches.restype = ctypes.c_int
            lib.hp_window_appearance.argtypes = [ctypes.c_void_p, ctypes.c_int]
            lib.hp_window_appearance.restype = None
            lib.hp_window_appearance_matches.argtypes = [ctypes.c_void_p, ctypes.c_int]
            lib.hp_window_appearance_matches.restype = ctypes.c_int
            lib.hp_accessibility.argtypes = []
            lib.hp_accessibility.restype = ctypes.c_int
            callback_type = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
            self._path_callback = callback_type(self._path_selected)
            lib.hp_choose_path.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int,
                                          ctypes.c_int, callback_type]
            lib.hp_choose_path.restype = None
            self.lib = lib
        except (OSError, StopIteration, AttributeError) as exc:
            self.error = str(exc) or "Native material adapter is not built"

    def preferences(self):
        return self.lib.hp_accessibility() if self.lib else 0

    def set_window_appearance(self, owner, mode):
        if self.lib:
            self.lib.hp_window_appearance(int(owner.winId()), mode)

    def choose_path(self, owner, directory, folders, dark, completion):
        if self._path_done is not None:
            return
        self._path_done = completion
        self.lib.hp_choose_path(int(owner.winId()), str(directory).encode("utf-8"),
                                folders, dark, self._path_callback)

    def _path_selected(self, value):
        done, self._path_done = self._path_done, None
        path = value.decode("utf-8") if value else ""
        if done:
            # Complete after AppKit has unwound the sheet callback.
            QTimer.singleShot(0, lambda: done(path))


class Canvas(QWidget):
    dark = False
    solid = False
    glass_surfaces = ()

    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        colors = ("#172536", "#242330", "#3B263A") if self.dark else ("#DAE6F6", "#EEF0F7", "#EEDDE8")
        if self.solid:
            painter.fillRect(self.rect(), QColor(colors[1]))
        else:
            for stop, color in zip((0, .55, 1), colors):
                gradient.setColorAt(stop, QColor(color))
            painter.fillRect(self.rect(), gradient)
        # Native child QNSViews share Qt's backing store. Clear only the material
        # shapes so their backing-store pixels cannot cover the AppKit backdrop.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for surface in self.glass_surfaces:
            if surface.handle and surface.isVisible():
                shape = QPainterPath()
                shape.addRoundedRect(QRectF(surface.geometry()), 22, 22)
                painter.fillPath(shape, QColor(0, 0, 0, 0))


class GlassSurface(QFrame):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.handle = None
        self.dark = self.solid = False
        self.backend = "fallback"
        self.setObjectName("glassSurface")
        if self.bridge.lib:
            self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors)
            self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.sync_timer = QTimer(self)
        self.sync_timer.setSingleShot(True)
        self.sync_timer.timeout.connect(self.sync_native)

    def configure(self, dark, solid):
        changed = self.dark != dark
        self.dark, self.solid = dark, solid
        # Recreate the compositor only on appearance transitions, not on samples
        # or resize. An attached glass can retain its previous light backdrop.
        if solid or changed:
            self.detach_native()
        if self.isVisible():
            self.sync_native()
        self.update()

    def sync_native(self):
        if not self.isVisible() or self.solid or not self.bridge.lib:
            return
        if not self.handle:
            self.handle = self.bridge.lib.hp_glass_attach(int(self.winId()))
            if not self.handle:
                return
            self.backend = "liquid-glass" if self.bridge.lib.hp_glass_kind(self.handle) == 2 else "vibrancy"
        self.bridge.lib.hp_glass_sync(self.handle, self.dark)
        self.parentWidget().update()
        self.update()

    def detach_native(self):
        self.sync_timer.stop()
        if self.handle:
            self.bridge.lib.hp_glass_detach(self.handle)
            self.handle = None
        self.backend = "fallback"
        if self.parentWidget():
            self.parentWidget().update()

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_timer.start(0)

    def hideEvent(self, event):
        self.detach_native()
        super().hideEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sync_timer.start(0)

    def moveEvent(self, event):
        super().moveEvent(event)
        self.sync_timer.start(0)

    def paintEvent(self, event):
        if self.handle:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        fill = QLinearGradient(0, 0, 0, self.height())
        colors = ("#30323A", "#262830") if self.dark else ("#FFFFFF", "#F0F2F6")
        for stop, color in zip((0, 1), colors):
            fill.setColorAt(stop, QColor(color))
        painter.setBrush(QColor(colors[0]) if self.solid else fill)
        border = "#82858F" if self.solid else ("#494C56" if self.dark else "#FFFFFF")
        painter.setPen(QPen(QColor(border), 1))
        painter.drawRoundedRect(rect, 22, 22)
