"""Compact date popover with neutral weekdays and keyboard navigation."""
from PyQt6.QtCore import QDate, QPoint, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPainterPath
from PyQt6.QtWidgets import QApplication, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox, QPushButton
from .widgets import KeyboardButton


def supported_date(day):
    """Keep Qt navigation within the datetime.date export engine's range."""
    return day.isValid() and 1 <= day.year() <= 9999


class DayButton(KeyboardButton):
    def __init__(self, popup):
        super().__init__(popup)
        self.popup = popup
        self.day = QDate()
        self.setFixedSize(36, 36)
        self.clicked.connect(lambda: popup.choose(self.day))

    def keyPressEvent(self, event):
        offsets = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1,
                   Qt.Key.Key_Up: -7, Qt.Key.Key_Down: 7}
        if event.key() in offsets:
            self.popup.focus_day(self.day.addDays(offsets[event.key()]))
        elif event.key() in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            self.popup.focus_day(self.day.addMonths(-1 if event.key() == Qt.Key.Key_PageUp else 1))
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        if not self.day.isValid():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = self.popup.owner.dark
        selected = self.day == self.popup.owner.date()
        rect = QRectF(2, 2, 32, 32)
        p.setPen(Qt.PenStyle.NoPen)
        if selected or self.underMouse() or self.hasFocus():
            p.setBrush(QColor("#943B53" if selected else ("#383D49" if dark else "#ECEFF5")))
            p.drawEllipse(rect)
        color = "#F4F5F8" if dark else "#20232D"
        if self.day.month() != self.popup.month.month():
            color = "#8D95A5" if dark else "#9299A5"
        if selected:
            color = "#FFFFFF"
        p.setPen(QColor(color))
        font = self.font(); font.setPixelSize(13); font.setWeight(500); p.setFont(font)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self.day.day()))
        if self.day == QDate.currentDate() and not selected:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#F29DB5" if dark else "#923A52"))
            p.drawEllipse(QRectF(16.5, 30, 3, 3))


class DatePopover(QFrame):
    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.owner = owner
        self.month = QDate(owner.date().year(), owner.date().month(), 1)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("datePopover")
        self.setAccessibleName(owner.accessibleName() + "日历")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)
        nav = QHBoxLayout(); nav.setSpacing(6)
        self.previous, self.next = QPushButton("‹"), QPushButton("›")
        for button, name in ((self.previous, "上个月"), (self.next, "下个月")):
            button.setObjectName("monthArrow")
            button.setFixedSize(30, 30)
            button.setAccessibleName(name)
        self.previous.clicked.connect(lambda: self.shift_month(-1))
        self.next.clicked.connect(lambda: self.shift_month(1))
        self.year_picker, self.month_picker = QComboBox(), QComboBox()
        self.year_picker.setAccessibleName("年份")
        self.month_picker.setAccessibleName("月份")
        self.year_picker.setMaxVisibleItems(10)
        self.month_picker.addItems([f"{month}月" for month in range(1, 13)])
        self.year_picker.currentIndexChanged.connect(self.change_month)
        self.month_picker.currentIndexChanged.connect(self.change_month)
        nav.addWidget(self.previous)
        nav.addWidget(self.year_picker, 1)
        nav.addWidget(self.month_picker, 1)
        nav.addWidget(self.next)
        layout.addLayout(nav)
        grid = QGridLayout(); grid.setSpacing(3)
        for col, name in enumerate("一二三四五六日"):
            label = QLabel(name); label.setObjectName("weekday")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(label, 0, col)
        self.days = []
        for index in range(42):
            button = DayButton(self)
            grid.addWidget(button, 1 + index//7, index%7)
            self.days.append(button)
        layout.addLayout(grid)
        today = QPushButton("今天")
        today.setAccessibleName("选择今天")
        today.clicked.connect(lambda: self.choose(QDate.currentDate()))
        layout.addWidget(today, 0, Qt.AlignmentFlag.AlignCenter)
        self.refresh()
        self.apply_theme()
        self.setFixedSize(self.sizeHint())

    def apply_theme(self):
        dark = self.owner.dark
        text, muted, entry = ("#F4F5F8", "#ABB3C3", "#323743") if dark else ("#20232D", "#6C7586", "#F0F2F7")
        self.setStyleSheet(f"""
            QWidget {{ color: {text}; font-size: 13px; }}
            QLabel {{ background: transparent; border: none; }}
            QLabel#weekday {{ color: {muted}; font-size: 11px; min-height: 22px; }}
            QComboBox {{ background: transparent; border: none; padding: 5px 2px; min-height: 22px; font-weight: 600; }}
            QComboBox::drop-down {{ border: none; width: 13px; }}
            QComboBox QAbstractItemView {{ background: {entry}; color: {text}; selection-background-color: #943B53; selection-color: white; border: none; padding: 5px; }}
            QPushButton {{ background: {entry}; border: none; border-radius: 13px; padding: 5px 14px; min-height: 20px; }}
            QPushButton#monthArrow {{ background: transparent; font-size: 23px; padding: 0; min-height: 0; }}
            QPushButton:hover {{ background: {entry}; color: {text}; }}
            QPushButton:focus, QComboBox:focus {{ border: 1px solid {muted}; border-radius: 8px; }}
        """)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#272B35" if self.owner.dark else "#FFFFFF"))
        p.setPen(QPen(QColor("#4C5361" if self.owner.dark else "#DCE1E9"), 1))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 20, 20)

    def refresh(self):
        self.year_picker.blockSignals(True); self.month_picker.blockSignals(True)
        self.year_picker.clear()
        for year in range(max(1, self.month.year()-100), min(9999, self.month.year()+100)+1):
            self.year_picker.addItem(f"{year}年", year)
        self.year_picker.setCurrentIndex(self.year_picker.findData(self.month.year()))
        self.month_picker.setCurrentIndex(self.month.month()-1)
        self.year_picker.blockSignals(False); self.month_picker.blockSignals(False)
        first = self.month.addDays(1-self.month.dayOfWeek())
        for index, button in enumerate(self.days):
            button.day = first.addDays(index)
            button.setEnabled(supported_date(button.day))
            button.setText(str(button.day.day()))
            button.setAccessibleName(button.day.toString("yyyy年M月d日"))
            button.update()
        self.previous.setEnabled(supported_date(self.month.addMonths(-1)))
        self.next.setEnabled(supported_date(self.month.addMonths(1)))

    def change_month(self):
        year = self.year_picker.currentData()
        if year is not None:
            day = QDate(year, self.month_picker.currentIndex()+1, 1)
            if supported_date(day):
                self.month = day
                self.refresh()

    def shift_month(self, offset):
        target = self.month.addMonths(offset)
        if supported_date(target):
            self.month = target
            self.refresh()

    def focus_day(self, date):
        if not supported_date(date):
            return
        if (date.year(), date.month()) != (self.month.year(), self.month.month()):
            self.month = QDate(date.year(), date.month(), 1)
            self.refresh()
        for button in self.days:
            if button.day == date:
                button.setFocus(Qt.FocusReason.TabFocusReason)
                break

    def choose(self, date):
        if supported_date(date):
            self.owner.setDate(date)
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


class DateField(KeyboardButton):
    dateChanged = pyqtSignal(QDate)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._date = QDate.currentDate()
        self.dark = False
        self.popup = None
        self.setMinimumWidth(145)
        self.setFixedHeight(34)
        self.setText(self._date.toString("yyyy年M月d日"))
        self.clicked.connect(self.open_calendar)

    def date(self):
        return QDate(self._date)

    def setDate(self, date):
        if not supported_date(date) or date == self._date:
            return
        self._date = QDate(date)
        self.setText(date.toString("yyyy年M月d日"))
        self.setToolTip(date.toString("yyyy-MM-dd"))
        self.dateChanged.emit(self.date())
        self.update()

    def set_theme(self, dark):
        self.dark = dark
        if self.popup:
            self.popup.apply_theme()
        self.update()

    def open_calendar(self):
        if self.popup:
            self.popup.close()
            self.popup.deleteLater()
        self.popup = DatePopover(self)
        point = self.mapToGlobal(QPoint(0, self.height()+6))
        screen = QApplication.screenAt(point) or QApplication.primaryScreen()
        bounds = screen.availableGeometry()
        x = min(max(point.x(), bounds.left()+8), bounds.right()-self.popup.width()-8)
        y = point.y()
        if y+self.popup.height() > bounds.bottom()-8:
            y = self.mapToGlobal(QPoint(0, 0)).y()-self.popup.height()-6
        self.popup.move(x, max(bounds.top()+8, y))
        self.popup.show()
        self.popup.focus_day(self.date())

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setBrush(QColor("#30343F" if self.dark else "#F2F4F8"))
        p.setPen(Qt.PenStyle.NoPen)
        if self.hasFocus() and self.keyboard_focus:
            p.setPen(QPen(QColor("#F29DB5" if self.dark else "#923A52"), 1.5))
        p.drawRoundedRect(rect, 11, 11)
        p.setPen(QColor("#F4F5F8" if self.dark else "#20232D"))
        font = self.font(); font.setPixelSize(12); p.setFont(font)
        p.drawText(rect.adjusted(12, 0, -27, 0), Qt.AlignmentFlag.AlignVCenter, self.text())
        p.setPen(QPen(QColor("#9CA5B6" if self.dark else "#7D8799"), 1.6,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        path = QPainterPath(); x, y = self.width()-20, self.height()/2-2
        path.moveTo(x-3, y); path.lineTo(x+1, y+4); path.lineTo(x+5, y)
        p.drawPath(path)
