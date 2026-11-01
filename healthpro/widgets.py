"""Task-only animation and low-frequency process telemetry for the desktop UI."""
import os
import math
from PyQt6.QtCore import Qt, QTimer, QRectF, QLineF, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QPen, QLinearGradient, QPainterPath
from PyQt6.QtWidgets import QAbstractButton, QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel
import psutil


class KeyboardButton(QAbstractButton):
    """Show focus only after keyboard navigation, never a permanent dotted outline."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.keyboard_focus = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def focusInEvent(self, event):
        self.keyboard_focus = event.reason() in (Qt.FocusReason.TabFocusReason,
            Qt.FocusReason.BacktabFocusReason, Qt.FocusReason.ShortcutFocusReason)
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        self.keyboard_focus = False
        super().focusOutEvent(event)
        self.update()

    def mousePressEvent(self, event):
        self.keyboard_focus = False
        super().mousePressEvent(event)
        self.update()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
        else:
            super().keyPressEvent(event)


class AppearanceButton(KeyboardButton):
    """Compact appearance control; no menu or persistent label in the toolbar."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(34, 34)
        self.set_appearance(False)

    def set_appearance(self, dark):
        self.dark = dark
        self.next_mode = 1 if dark else 2
        hint = "切换到浅色" if dark else "切换到深色"
        self.setToolTip(hint)
        self.setAccessibleName(hint)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fg = QColor("#F4F5F8" if self.dark else "#353D4B")
        fill = QColor("#30343F" if self.dark else "#FFFFFF")
        fill.setAlpha(210 if self.isDown() else 160 if self.underMouse() else 90)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.drawEllipse(QRectF(1, 1, 32, 32))
        if self.hasFocus() and self.keyboard_focus:
            p.setPen(QPen(QColor("#F29DB5" if self.dark else "#923A52"), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(1, 1, 32, 32))
        p.setPen(QPen(fg, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if not self.dark:
            p.drawEllipse(QRectF(13, 13, 8, 8))
            for i in range(8):
                angle = i * math.pi / 4
                p.drawLine(QLineF(17+6.5*math.cos(angle), 17+6.5*math.sin(angle),
                                 17+9*math.cos(angle), 17+9*math.sin(angle)))
        else:
            moon, cutout = QPainterPath(), QPainterPath()
            moon.addEllipse(QRectF(9.5, 9.5, 15, 15))
            cutout.addEllipse(QRectF(15, 6, 14, 14))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fg)
            p.drawPath(moon.subtracted(cutout))


class CapsuleButton(KeyboardButton):
    """Paint geometry directly: macOS style polishing cannot square off this button."""
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.dark = False
        self.setMinimumWidth(136)
        self.setFixedHeight(42)

    def set_theme(self, dark):
        self.dark = dark
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        fill = "#943B53"
        text = "#FFFFFF"
        if not self.isEnabled():
            fill, text = ("#30343F", "#ADB4C3") if self.dark else ("#E9ECF2", "#727B8A")
        elif self.isDown():
            fill = "#782F43"
        elif self.underMouse():
            fill = "#AB4965"
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(fill))
        p.drawRoundedRect(rect, rect.height()/2, rect.height()/2)
        if self.hasFocus() and self.keyboard_focus:
            p.setPen(QPen(QColor("#F29DB5" if self.dark else "#923A52"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), self.height()/2, self.height()/2)
        p.setPen(QColor(text))
        font = self.font(); font.setPixelSize(12); font.setWeight(600); p.setFont(font)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())


class MiniRing(QWidget):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.color = QColor(color)
        self.dark = False
        self.pct = 0.0

    def set_pct(self, value):
        self.pct = max(0.0, min(100.0, value))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(3, 3, 18, 18)
        p.setPen(QPen(QColor("#555861" if self.dark else "#D9DDE5"), 3))
        p.drawEllipse(rect)
        p.setPen(QPen(self.color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, 90 * 16, -int(self.pct * 3.6 * 16))


class ResourceHUD(QFrame):
    """Percent CPU is normalized to all logical cores, as in the public v8.7 UI."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("resourceHUD")
        self.process = psutil.Process(os.getpid())
        self.cores = psutil.cpu_count(logical=True) or 1
        self.total_memory = psutil.virtual_memory().total
        self.process.cpu_percent(interval=None)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(14)
        self.cpu_ring = MiniRing("#BF5266")
        self.ram_ring = MiniRing("#3981E8")
        self.cpu_label, self.ram_label = QLabel("—"), QLabel("—")
        for ring, label, title in [(self.cpu_ring, self.cpu_label, "CPU"),
                                   (self.ram_ring, self.ram_label, "内存")]:
            layout.addWidget(ring)
            column = QVBoxLayout()
            column.setSpacing(1)
            caption = QLabel(title)
            caption.setObjectName("caption")
            label.setObjectName("hudValue")
            column.addWidget(caption)
            column.addWidget(label)
            layout.addLayout(column)
        self.setToolTip("CPU：本应用所有线程的 CPU 时间 ÷ 逻辑核心数，范围 0–100%。\n"
                        "内存：本应用当前 RSS；蓝色圆环表示占整机物理内存的比例。每 1.5 秒采样。")
        self.setAccessibleName("本应用资源占用")
        self.timer = QTimer(self)
        self.timer.setInterval(1500)
        self.timer.setTimerType(Qt.TimerType.CoarseTimer)
        self.timer.timeout.connect(self.sample)

    def sample(self):
        try:
            # interval=None is nonblocking; never sleep on the GUI thread.
            cpu = min(100.0, self.process.cpu_percent(interval=None) / self.cores)
            rss = self.process.memory_info().rss
            mb = rss / (1024 * 1024)
            self.cpu_label.setText(f"{cpu:.1f}%")
            self.ram_label.setText(f"{mb:.0f} MB" if mb < 1024 else f"{mb / 1024:.2f} GB")
            self.cpu_ring.set_pct(cpu)
            self.ram_ring.set_pct(100 * rss / self.total_memory)
        except (psutil.Error, OSError):
            self.cpu_label.setText("—")
            self.ram_label.setText("—")
            self.cpu_ring.set_pct(0)
            self.ram_ring.set_pct(0)

    def set_theme(self, dark):
        for ring in (self.cpu_ring, self.ram_ring):
            ring.dark = dark
            ring.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.sample()
        self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)


class ProgressRing(KeyboardButton):
    COLORS = {"idle": ("#8E919C", "#9EA2AE"), "scan": ("#BA6A0D", "#F6B449"),
              "export": ("#963B52", "#F08DAB"), "ready": ("#22845C", "#59DFA2"),
              "success": ("#22845C", "#59DFA2"), "error": ("#C33842", "#FF747C"),
              "cancelled": ("#787C89", "#A8ADBA")}
    LABELS = {"idle": "选择文件", "scan": "正在索引", "export": "正在导出", "ready": "就绪",
              "success": "已完成", "error": "未完成", "cancelled": "已取消"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(164, 164)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.phase, self.dark, self.reduced_motion = "idle", False, False
        self._progress, self.angle = 0.0, 0.0
        self.indeterminate = False
        self.timer = QTimer(self)
        self.timer.setInterval(40)  # 25 fps while busy; zero animation ticks when idle.
        self.timer.timeout.connect(self.tick)
        self.animation = QPropertyAnimation(self, b"progress", self)
        self.animation.setDuration(240)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.set_state("idle", 0)

    @pyqtProperty(float)
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, value):
        self._progress = max(0, min(100, value))
        self.update()

    def set_state(self, phase, percent=None):
        self.phase = phase
        self.indeterminate = percent is None and phase in {"scan", "export"}
        self.animation.stop()
        if percent is not None:
            if self.reduced_motion or not self.isVisible() or phase not in {"scan", "export"}:
                self.progress = float(percent)
            else:
                self.animation.setStartValue(self.progress)
                self.animation.setEndValue(float(percent))
                self.animation.start()
        self.setAccessibleName("导入健康数据 · " + self.LABELS[phase] +
                               (f" {percent}%" if percent is not None else ""))
        self.setToolTip("选择 Apple 健康导出 ZIP；也可以按空格或回车。" if phase not in {"scan", "export"}
                        else "正在处理，请使用“取消”按钮结束任务。")
        self.update_timer()
        self.update()

    def set_theme(self, dark, reduced_motion=False):
        self.dark, self.reduced_motion = dark, reduced_motion
        if reduced_motion and self.animation.state() == QPropertyAnimation.State.Running:
            end = self.animation.endValue()
            self.animation.stop()
            self.progress = end
        self.update_timer()
        self.update()

    def update_timer(self):
        if self.indeterminate and self.isVisible() and not self.reduced_motion:
            self.timer.start()
        else:
            self.timer.stop()

    def tick(self):
        self.angle = (self.angle + 5) % 360
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_timer()

    def hideEvent(self, event):
        self.timer.stop()
        if self.animation.state() == QPropertyAnimation.State.Running:
            end = self.animation.endValue()
            self.animation.stop()
            self.progress = end
        super().hideEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self.COLORS[self.phase][int(self.dark)])
        rect = QRectF(14, 14, 136, 136)
        p.setPen(QPen(QColor("#363B46" if self.dark else "#E6E9EF"), 9,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawEllipse(rect)
        sheen = QLinearGradient(14, 14, 150, 150)
        sheen.setColorAt(0, color.lighter(125))
        sheen.setColorAt(1, color)
        p.setPen(QPen(sheen, 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        if self.indeterminate:
            p.drawArc(rect, int((90 - self.angle) * 16), -100 * 16)
        elif self.progress > 0:
            p.drawArc(rect, 90 * 16, -int(self.progress * 3.6 * 16))
        if self.phase == "idle":
            p.setPen(QPen(color, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            path = QPainterPath()
            path.moveTo(82, 78); path.lineTo(82, 54)
            path.moveTo(72, 64); path.lineTo(82, 54); path.lineTo(92, 64)
            path.moveTo(66, 80); path.lineTo(66, 87); path.lineTo(98, 87); path.lineTo(98, 80)
            p.drawPath(path)
            primary = "导入"
            text_rect = QRectF(25, 99, 114, 25)
            size = 15
        else:
            primary = "•••" if self.indeterminate else f"{self.progress:.0f}%"
            text_rect = QRectF(22, 50, 120, 42)
            size = 27
        p.setPen(QColor("#F3F4F8" if self.dark else "#222631"))
        font = p.font(); font.setPixelSize(size); font.setWeight(600); p.setFont(font)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, primary)
        if self.phase != "idle":
            font.setPixelSize(12); font.setWeight(500); p.setFont(font)
            p.setPen(color)
            p.drawText(QRectF(22, 96, 120, 24), Qt.AlignmentFlag.AlignCenter, self.LABELS[self.phase])
        if self.hasFocus() and self.keyboard_focus:
            p.setBrush(Qt.BrushStyle.NoBrush)
            halo = QColor(color); halo.setAlpha(65)
            p.setPen(QPen(halo, 5))
            p.drawEllipse(QRectF(5, 5, 154, 154))
