"""One cancellable job at a time, with distinct completion and failure states."""
from __future__ import annotations
import argparse
import sys
import time
import zipfile
from pathlib import Path
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate, QTimer, QUrl
from PyQt6.QtGui import QAction, QDesktopServices, QIcon, QPalette, QColor
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QFileDialog, QLineEdit,
    QCheckBox, QListWidget, QListWidgetItem, QProgressBar, QPlainTextEdit, QScrollArea)
from . import __version__, IS_PREVIEW
from .core import Cancelled, ExportOptions, export_archive, scan_archive
from .materials import Canvas, GlassSurface, NativeMaterials
from .widgets import ResourceHUD, ProgressRing, CapsuleButton, AppearanceButton
from .dates import DateField


def resources():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def friendly_error(exc):
    if isinstance(exc, PermissionError):
        return "没有权限读取文件或写入此位置，请更换文件或输出文件夹。"
    if isinstance(exc, FileNotFoundError):
        return "文件已移动或不存在，请重新选择。"
    if isinstance(exc, zipfile.BadZipFile):
        return "ZIP 文件损坏或格式不正确，请重新从健康 App 导出。"
    return str(exc) or type(exc).__name__


class Worker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    progress = pyqtSignal(int, int)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation, self.last_progress = operation, 0.0

    def report(self, current, total, count):
        now = time.monotonic()
        if now-self.last_progress > .1 or current == total:
            self.last_progress = now
            self.progress.emit(min(99, int(100*current/total)) if total else 0, count)

    def run(self):
        try:
            self.succeeded.emit(self.operation(cancel=self.isInterruptionRequested, progress=self.report))
        except Cancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(friendly_error(exc))
        finally:
            self.operation = None


class DropCard(QFrame):
    file_dropped = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("fileCard")
        self.setAcceptDrops(True)

    def valid_drop(self, event):
        urls = event.mimeData().urls()
        return (self.isEnabled() and len(urls) == 1 and urls[0].isLocalFile()
                and urls[0].toLocalFile().lower().endswith(".zip"))

    def dragEnterEvent(self, event):
        if self.valid_drop(event):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if self.valid_drop(event):
            self.file_dropped.emit(event.mimeData().urls()[0].toLocalFile())
            event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.index = self.worker = self.outcome = self.result = self.demo_path = None
        self.operation = ""
        self.last_input_directory = Path.home()/"Downloads"
        self.close_pending = False
        self.setWindowTitle(f"Apple Health Pro · {__version__}" + (" 审核版" if IS_PREVIEW else ""))
        self.setMinimumSize(900, 620)
        self.resize(1020, 780)
        self.materials = NativeMaterials()
        self.accessibility_flags = self.materials.preferences()
        self.setWindowIcon(QIcon(str(resources()/"icon.png")))
        self.build_ui()
        self.build_menu()
        QApplication.instance().styleHints().colorSchemeChanged.connect(lambda _: self.apply_theme())
        self.apply_theme()
        self.update_selection()
        self.preference_timer = QTimer(self)
        self.preference_timer.setInterval(2000)
        self.preference_timer.timeout.connect(self.refresh_accessibility)
        self.preference_timer.start()

    @staticmethod
    def label(text, name="", wrap=False):
        widget = QLabel(text)
        widget.setTextFormat(Qt.TextFormat.PlainText)
        widget.setWordWrap(wrap)
        widget.setObjectName(name)
        return widget

    def build_menu(self):
        menu = self.menuBar().addMenu("文件")
        self.open_action = QAction("选择文件…", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.browse_input)
        menu.addAction(self.open_action)
        self.demo_action = QAction("载入演示数据（全部为合成记录）", self)
        self.demo_action.triggered.connect(self.load_demo)
        menu.addAction(self.demo_action)
        self.reset_action = QAction("更换数据", self)
        self.reset_action.triggered.connect(self.reset)
        menu.addAction(self.reset_action)
        quit_action = QAction("退出", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)

    def build_ui(self):
        self.canvas = Canvas()
        self.setCentralWidget(self.canvas)
        layout = QVBoxLayout(self.canvas)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(16)

        self.toolbar = GlassSurface(self.materials)
        header = QHBoxLayout(self.toolbar)
        header.setContentsMargins(22, 12, 18, 12)
        header.setSpacing(18)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(self.label("Apple Health Pro", "brand"))
        header.addLayout(titles)
        header.addStretch()
        self.resource_hud = ResourceHUD()
        header.addWidget(self.resource_hud)
        self.theme_mode = 0
        self.theme_button = AppearanceButton()
        self.theme_button.clicked.connect(lambda: self.set_theme_mode(self.theme_button.next_mode))
        header.addWidget(self.theme_button)
        layout.addWidget(self.toolbar)

        body = QWidget()
        body.setObjectName("body")
        columns = QHBoxLayout(body)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(16)
        sidebar = QWidget()
        sidebar.setFixedWidth(240)
        left = QVBoxLayout(sidebar)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(14)
        self.file_card = DropCard()
        self.file_card.file_dropped.connect(self.process_zip)
        fc = QVBoxLayout(self.file_card)
        fc.setContentsMargins(18, 16, 18, 18)
        fc.setSpacing(8)
        fc.addSpacing(12)
        self.ring = ProgressRing()
        self.ring.clicked.connect(self.browse_input)
        fc.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignHCenter)
        self.file_name = self.label("Apple 健康数据", "cardTitle", True)
        self.file_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_name.setMaximumHeight(48)
        fc.addWidget(self.file_name)
        self.file_meta = self.label("拖入 ZIP 文件", "muted", True)
        self.file_meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fc.addWidget(self.file_meta)
        self.browse_button = QPushButton("选择文件…")
        self.browse_button.setObjectName("secondary")
        self.browse_button.setMinimumHeight(34)
        self.browse_button.clicked.connect(self.browse_input)
        fc.addWidget(self.browse_button)
        left.addWidget(self.file_card)

        summary = QFrame()
        summary.setObjectName("summary")
        sc = QVBoxLayout(summary)
        sc.setContentsMargins(0, 20, 0, 8)
        sc.setSpacing(6)
        metric = QHBoxLayout()
        self.record_label = self.label("—", "bigNumber")
        metric.addWidget(self.record_label)
        metric.addStretch()
        metric.addWidget(self.label("条记录", "muted"))
        sc.addLayout(metric)
        self.date_summary = self.label("", "muted", True)
        self.coverage_label = self.label("", "caption", True)
        sc.addWidget(self.date_summary)
        self.coverage_label.hide()
        fc.addWidget(summary)
        left.addStretch()
        self.demo_banner = self.label("", "demo", True)
        left.addWidget(self.demo_banner)
        local_note = self.label("本地处理", "caption")
        local_note.setToolTip("健康数据不会上传。v" + __version__)
        left.addWidget(local_note)
        columns.addWidget(sidebar)

        right = QVBoxLayout()
        right.setSpacing(14)
        source_card = QFrame()
        source_card.setObjectName("contentCard")
        src = QVBoxLayout(source_card)
        src.setContentsMargins(18, 16, 18, 14)
        src.setSpacing(10)
        src_header = QHBoxLayout()
        src_header.addWidget(self.label("数据来源", "section"))
        src_header.addStretch()
        self.selected_label = self.label("尚未导入", "muted")
        src_header.addWidget(self.selected_label)
        src.addLayout(src_header)
        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索来源")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("搜索数据来源")
        self.search.textChanged.connect(self.filter_sources)
        tools.addWidget(self.search, 1)
        self.select_all, self.select_none = QPushButton("全选"), QPushButton("全不选")
        self.select_all.clicked.connect(lambda: self.set_sources(len(self.selected_sources()) != self.source_list.count()))
        self.select_none.clicked.connect(lambda: self.set_sources(False))
        tools.addWidget(self.select_all)
        self.select_none.hide()
        src.addLayout(tools)
        self.source_list = QListWidget()
        self.source_list.setAccessibleName("数据来源，空格键切换选择")
        self.source_list.setMinimumHeight(120)
        self.source_list.itemChanged.connect(self.update_selection)
        src.addWidget(self.source_list, 1)
        self.empty_sources = self.label("导入后选择来源", "muted", True)
        self.empty_sources.setAlignment(Qt.AlignmentFlag.AlignCenter)
        src.addWidget(self.empty_sources)
        right.addWidget(source_card, 1)

        export_card = QFrame()
        export_card.setObjectName("contentCard")
        form = QVBoxLayout(export_card)
        form.setContentsMargins(18, 16, 18, 16)
        form.setSpacing(10)
        form.addWidget(self.label("导出", "section"))
        date_row = QHBoxLayout()
        self.date_start, self.date_end = DateField(), DateField()
        for field, name in [(self.date_start,"开始日期"), (self.date_end,"结束日期")]:
            field.setAccessibleName(name)
            field.setDate(QDate.currentDate())
            field.dateChanged.connect(self.update_selection)
        date_row.addWidget(self.label("日期", "muted"))
        date_row.addWidget(self.date_start, 1)
        date_row.addWidget(self.label("至", "muted"))
        date_row.addWidget(self.date_end, 1)
        self.all_dates = QPushButton("全部日期")
        self.all_dates.clicked.connect(self.use_all_dates)
        date_row.addWidget(self.all_dates)
        form.addLayout(date_row)
        dest_row = QHBoxLayout()
        dest_row.addWidget(self.label("保存", "muted"))
        self.destination = QLineEdit(str(Path.home()/"Downloads"))
        self.destination.setAccessibleName("输出文件夹")
        self.destination.setReadOnly(True)
        dest_row.addWidget(self.destination, 1)
        self.choose_destination = QPushButton("选择位置…")
        self.choose_destination.clicked.connect(self.browse_destination)
        dest_row.addWidget(self.choose_destination)
        form.addLayout(dest_row)
        self.options_toggle = QPushButton("更多选项")
        self.options_toggle.setCheckable(True)
        self.options_toggle.setToolTip("来源名称匿名化和 Excel 安全文本默认开启；点此修改。")
        form.addWidget(self.options_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        self.advanced_options = QWidget()
        options = QHBoxLayout(self.advanced_options)
        options.setContentsMargins(0, 0, 0, 0)
        options.setSpacing(20)
        self.options_toggle.toggled.connect(self.advanced_options.setVisible)
        self.privacy = QCheckBox("匿名化来源名称")
        self.privacy.setChecked(True)
        self.privacy.setToolTip("只替换来源名；日期和健康数值仍是敏感信息。")
        self.excel_safe = QCheckBox("Excel 安全文本")
        self.excel_safe.setChecked(True)
        self.excel_safe.setToolTip("保护公式前缀文本；机器分析需原始文本时可关闭。")
        options.addWidget(self.privacy)
        options.addWidget(self.excel_safe)
        options.addStretch()
        form.addWidget(self.advanced_options)
        self.advanced_options.hide()
        right.addWidget(export_card)
        columns.addLayout(right, 1)
        body.setMinimumHeight(460)
        body_scroll = QScrollArea()
        body_scroll.setObjectName("bodyScroll")
        body_scroll.setWidgetResizable(True)
        body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body_scroll.setWidget(body)
        body_scroll.viewport().setAutoFillBackground(False)
        layout.addWidget(body_scroll, 1)

        self.status_card = GlassSurface(self.materials)
        sl = QVBoxLayout(self.status_card)
        sl.setContentsMargins(18, 14, 18, 14)
        sl.setSpacing(8)
        status_row = QHBoxLayout()
        status_row.setSpacing(12)
        copy = QVBoxLayout()
        copy.setSpacing(3)
        self.status_label = self.label("准备就绪", "status", True)
        self.selection_hint = self.label("先选择一个健康数据 ZIP 文件。", "caption", True)
        copy.addWidget(self.status_label)
        copy.addWidget(self.selection_hint)
        self.selection_hint.hide()
        status_row.addLayout(copy, 1)
        self.open_output = QPushButton("打开结果")
        self.open_output.clicked.connect(self.reveal_output)
        self.open_output.hide()
        status_row.addWidget(self.open_output)
        self.details_button = QPushButton("详情")
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self.toggle_details)
        status_row.addWidget(self.details_button)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.cancel_job)
        self.cancel_button.hide()
        status_row.addWidget(self.cancel_button)
        self.execute_button = CapsuleButton("导出 CSV")
        self.execute_button.setObjectName("primary")
        self.execute_button.setMinimumWidth(136)
        self.execute_button.setFixedHeight(42)
        self.execute_button.clicked.connect(self.start_export)
        status_row.addWidget(self.execute_button)
        sl.addLayout(status_row)
        self.progress = QProgressBar()
        self.progress.setRange(0,100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.hide()
        self.overlap_details = self.label("", "caption", True)
        self.overlap_details.hide()
        sl.addWidget(self.overlap_details)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(200)
        self.log.setMaximumHeight(100)
        self.log.setAccessibleName("处理详情")
        self.log.hide()
        sl.addWidget(self.log)
        layout.addWidget(self.status_card)
        self.canvas.glass_surfaces = (self.toolbar, self.status_card)

    def refresh_accessibility(self):
        flags = self.materials.preferences()
        if flags != self.accessibility_flags:
            self.accessibility_flags = flags
            self.apply_theme()

    def set_theme_mode(self, mode):
        self.theme_mode = mode
        self.apply_theme()

    def apply_theme(self):
        if not hasattr(self, "status_card"):
            return
        dark = self.theme_mode == 2 or (self.theme_mode == 0 and
                QApplication.instance().styleHints().colorScheme() == Qt.ColorScheme.Dark)
        solid = bool(self.accessibility_flags & 5)
        bg,panel,text,muted,border,entry = (("#1D1F26","#272A33","#F4F5F8","#ADB4C3","#3C404C","#30343F") if dark
            else ("#F3F4F7","#FFFFFF","#20232D","#626B7C","#E3E6EC","#F2F4F8"))
        accent = "#F29DB5" if dark else "#923A52"
        if self.accessibility_flags & 4:
            muted = "#DFE3EA" if dark else "#353D4B"
            border = "#929BAC" if dark else "#747D8B"
        self.canvas.dark, self.canvas.solid = dark, solid
        self.canvas.update()
        self.theme_button.set_appearance(dark)
        self.resource_hud.set_theme(dark)
        self.execute_button.set_theme(dark)
        self.date_start.set_theme(dark)
        self.date_end.set_theme(dark)
        self.ring.set_theme(dark, bool(self.accessibility_flags & 2))
        palette = QPalette()
        for role,color in [(QPalette.ColorRole.Window,bg),(QPalette.ColorRole.WindowText,text),
            (QPalette.ColorRole.Base,entry),(QPalette.ColorRole.AlternateBase,panel),(QPalette.ColorRole.Text,text),
            (QPalette.ColorRole.Button,panel),(QPalette.ColorRole.ButtonText,text),
            (QPalette.ColorRole.Highlight,"#96394A"),(QPalette.ColorRole.HighlightedText,"#FFFFFF")]:
            palette.setColor(role,QColor(color))
        QApplication.instance().setPalette(palette)
        tick = (resources()/"assets"/"check.svg").as_posix()
        chevron = (resources()/"assets"/"chevron.svg").as_posix()
        self.setStyleSheet(f"""
            QWidget {{ color: {text}; }}
            QMainWindow, QFrame#glassSurface {{ background: transparent; }}
            QScrollArea#bodyScroll, QScrollArea#bodyScroll > QWidget, QWidget#body {{ background: transparent; border: none; }}
            QLabel {{ background: transparent; border: none; }}
            QLabel#brand {{ font-size: 23px; font-weight: 700; }}
            QLabel#muted {{ color: {muted}; font-size: 12px; }}
            QLabel#caption {{ color: {muted}; font-size: 11px; }}
            QLabel#hudValue {{ font-size: 13px; font-weight: 600; }}
            QLabel#section {{ font-size: 13px; font-weight: 600; }}
            QLabel#cardTitle {{ font-size: 13px; font-weight: 600; }}
            QLabel#bigNumber {{ font-size: 28px; font-weight: 600; }}
            QLabel#demo {{ color: {accent}; font-size: 11px; font-weight: 500; }}
            QLabel#status {{ font-size: 13px; font-weight: 600; }}
            QLabel#notice {{ background: {entry}; color: {muted}; padding: 8px 10px; border-radius: 10px; font-size: 11px; }}
            QFrame#contentCard, QFrame#fileCard {{ background: {panel}; border: 1px solid {border}; border-radius: 18px; }}
            QFrame#resourceHUD {{ background: transparent; border: none; }}
            QPushButton {{ background: {entry}; border: 1px solid transparent; border-radius: 13px; padding: 6px 12px; font-size: 12px; font-weight: 500; min-height: 18px; }}
            QPushButton:hover {{ border-color: {border}; color: {accent}; }}
            QPushButton:pressed {{ background: {border}; }}
            QPushButton:focus {{ border: 2px solid {accent}; }}
            QPushButton#secondary {{ color: {accent}; }}
            QPushButton:disabled {{ background: {entry}; color: {muted}; border-color: transparent; }}
            QLineEdit, QComboBox {{ background: {entry}; border: 1px solid transparent; border-radius: 10px; padding: 6px 9px; min-height: 18px; font-size: 12px; }}
            QLineEdit:focus, QComboBox:focus {{ border: 2px solid {accent}; }}
            QComboBox::drop-down {{ border: none; width: 24px; background: transparent; }}
            QComboBox::down-arrow {{ image: url("{chevron}"); width: 10px; height: 6px; }}
            QListWidget {{ background: {panel}; border: none; padding: 0; outline: none; font-size: 13px; }}
            QListWidget::item {{ padding: 10px 8px; border-radius: 9px; margin: 2px 0; }}
            QListWidget::item:hover, QListWidget::item:selected {{ background: {entry}; color: {text}; }}
            QListWidget::item:focus {{ border: 1px solid {accent}; }}
            QCheckBox {{ spacing: 8px; padding: 4px 0; font-size: 12px; }}
            QCheckBox::indicator, QListWidget::indicator {{ width: 16px; height: 16px; border: 1px solid {muted}; border-radius: 5px; background: {panel}; }}
            QCheckBox::indicator:checked, QListWidget::indicator:checked {{ background: #943B53; border-color: #943B53; image: url("{tick}"); }}
            QCheckBox:focus {{ border: 1px solid {accent}; border-radius: 5px; }}
            QProgressBar {{ background: {border}; border: none; border-radius: 1px; }}
            QProgressBar::chunk {{ background: {accent}; border-radius: 1px; }}
            QPlainTextEdit {{ background: transparent; color: {muted}; border: none; font-size: 11px; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
            QScrollBar::handle:vertical {{ background: {border}; border-radius: 3px; min-height: 25px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)
        # Qt stylesheet polishing can reset widget constraints; set the final size afterwards.
        self.execute_button.setFixedHeight(42)
        self.materials.set_window_appearance(self, self.theme_mode)
        for surface in (self.toolbar, self.status_card):
            surface.configure(dark, solid)

    def browse_input(self):
        if self.worker or self.close_pending:
            return
        if self.materials.lib:
            self.materials.choose_path(self, self.last_input_directory, False,
                                       self.canvas.dark, self.accept_input_path)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "选择 Apple 健康数据",
                str(self.last_input_directory), "ZIP 文件 (*.zip)")
            self.accept_input_path(path)

    def accept_input_path(self, path):
        if path and self.isVisible() and not self.close_pending:
            self.process_zip(path)

    def browse_destination(self):
        if self.worker or self.close_pending:
            return
        if self.materials.lib:
            self.materials.choose_path(self, self.destination.text(), True,
                                       self.canvas.dark, self.accept_destination_path)
        else:
            path = QFileDialog.getExistingDirectory(self, "选择输出位置", self.destination.text())
            self.accept_destination_path(path)

    def accept_destination_path(self, path):
        if path and not self.worker and not self.close_pending:
            self.destination.setText(path)
            self.destination.setToolTip(path)
            self.destination.setCursorPosition(0)

    def load_demo(self):
        if self.worker or self.close_pending:
            return
        from .demo import create_demo
        self.demo_path = create_demo().resolve()
        self.process_zip(str(self.demo_path))

    def clear_data(self):
        self.index = self.result = None
        self.ring.set_state("idle", 0)
        self.empty_sources.show()
        self.source_list.clear()
        self.search.clear()
        self.record_label.setText("—")
        self.date_summary.setText("")
        self.coverage_label.clear()
        self.open_output.hide()
        self.log.clear()
        self.progress.setValue(0)

    def reset(self):
        if self.worker:
            return
        self.clear_data()
        self.file_name.setText("Apple 健康数据")
        self.file_meta.setText("拖入 ZIP 文件")
        self.browse_button.setText("选择文件…")
        self.demo_banner.clear()
        self.status_label.setText("准备就绪")
        self.update_selection()

    def process_zip(self,path):
        if self.worker or self.close_pending:
            return False
        self.clear_data()
        file = Path(path).resolve()
        self.last_input_directory = file.parent
        self.file_name.setText(file.name)
        self.file_name.setToolTip(str(file))
        self.file_meta.setText("正在读取数据概览…")
        self.demo_banner.setText("演示 · 合成数据" if self.demo_path and file == self.demo_path else "")
        if self.demo_path and file == self.demo_path:
            self.file_name.setText("演示数据.zip")
        self.destination.setText(str(file.parent))
        self.destination.setCursorPosition(0)
        self.destination.setToolTip(str(file.parent))
        return self.start_job("scan",lambda **kw: scan_archive(file,**kw))

    def start_job(self,operation,callback):
        if self.worker:
            return False
        self.operation,self.outcome,self.result = operation,None,None
        self.ring.set_state(operation, None)
        self.open_output.hide()
        self.progress.setValue(0)
        self.log.clear()
        self.log.appendPlainText("本地处理，不上传健康数据。按开始日期筛选，保留原时区与结束时间。\n每次导出生成独立目录；保留各来源记录，不自动去重。\n来源名称匿名化仅替换来源名，日期与健康数值仍可能识别个人。")
        self.status_label.setText("正在读取…" if operation == "scan" else "正在导出…")
        self.worker = Worker(callback,self)
        self.worker.succeeded.connect(lambda r: self.set_outcome("success",r))
        self.worker.failed.connect(lambda e: self.set_outcome("error",e))
        self.worker.cancelled.connect(lambda: self.set_outcome("cancelled",None))
        self.worker.progress.connect(self.show_progress)
        self.worker.finished.connect(self.job_finished)
        self.set_busy(True)
        self.worker.start()
        return True

    def set_outcome(self,kind,result):
        self.outcome = kind,result

    def set_busy(self,busy):
        for w in [self.file_card,self.search,self.source_list,self.select_all,self.select_none,
                  self.date_start,self.date_end,self.all_dates,self.privacy,self.excel_safe,self.choose_destination]:
            w.setEnabled(not busy)
        self.open_action.setEnabled(not busy)
        self.demo_action.setEnabled(not busy)
        self.reset_action.setEnabled(not busy)
        self.cancel_button.setVisible(busy)
        self.cancel_button.setEnabled(busy)
        self.cancel_button.setText("取消")
        self.execute_button.setText("处理中…" if busy else "导出 CSV")
        self.update_selection()

    def show_progress(self,percent,count):
        self.progress.setValue(percent)
        self.ring.set_state(self.operation, percent)
        if not self.close_pending:
            verb = "读取" if self.operation == "scan" else "扫描"
            self.status_label.setText(f"正在{verb} · {count:,} 条记录 · {percent}%")

    def job_finished(self):
        worker,self.worker = self.worker,None
        if worker:
            worker.deleteLater()
        kind,result = self.outcome or ("error","任务意外结束，请重试。")
        self.outcome = None
        self.set_busy(False)
        if kind == "success":
            self.ring.set_state("ready" if self.operation == "scan" else "success", 100)
            self.progress.setValue(100)
            if self.operation == "scan":
                self.index = result
                self.fill_index()
            else:
                self.result = result
                self.status_label.setText(f"导出完成 · {result.rows:,} 条记录 · {result.csv_files} 个 CSV")
                self.open_output.show()
                self.log.appendPlainText(f"输出位置：{result.directory}\n记录数：{result.rows:,}\n未映射记录：{result.unmapped_rows:,}（已保留）\n多来源指标：{len(result.overlap_types)}\n包含 export_manifest.json，记录过滤条件与各文件校验值。")
        elif kind == "cancelled":
            self.ring.set_state("cancelled", 0)
            self.progress.setValue(0)
            self.status_label.setText("已取消 · 未发布本次结果")
            if self.operation == "scan":
                self.file_meta.setText("读取已取消，可以重新选择文件。")
        else:
            self.ring.set_state("error", 0)
            self.progress.setValue(0)
            self.status_label.setText("操作未完成 · "+result)
            self.log.appendPlainText(result)
            if self.operation == "scan":
                self.file_meta.setText("导入失败，请重新选择有效文件。")
        self.update_selection()
        if self.close_pending:
            self.close()

    def fill_index(self):
        index = self.index
        self.empty_sources.hide()
        self.file_meta.setText(f"{index.identity[0]/1024**2:.1f} MB · ZIP")
        self.file_meta.setToolTip(f"XML {index.xml_size/1024**2:.1f} MB · 完整性检查通过")
        self.browse_button.setText("更换文件")
        self.record_label.setText(f"{index.total_records:,}")
        self.date_summary.setText(f"{len(index.sources)} 个来源 · {len(index.types)} 种指标")
        unknown = index.categories["16_Other_Unmapped"]
        notes = [f"未映射 {unknown:,} 条（导出时保留）"] if unknown else ["所有已读取类型均有明确分类"]
        if index.missing_end_dates:
            notes.append(f"{index.missing_end_dates:,} 条缺少结束时间（保留为空）")
        if index.skipped_tags:
            notes.append("未读取的元素："+", ".join(f"{k} × {v}" for k,v in index.skipped_tags.items()))
        self.coverage_label.setText("\n".join(notes))
        self.source_list.blockSignals(True)
        self.source_list.clear()
        for name,info in sorted(index.sources.items()):
            item = QListWidgetItem(f"{name}    {info.count:,} 条")
            item.setData(Qt.ItemDataRole.UserRole,name)
            item.setToolTip(f"{name}\n{info.first_day} — {info.last_day}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.source_list.addItem(item)
        self.source_list.blockSignals(False)
        self.use_all_dates()
        self.status_label.setText("选择来源即可导出")
        self.log.appendPlainText(f"已读取 {index.total_records:,} 条记录。\n日期按开始时间筛选，输出保留结束时间。\n"+"\n".join(notes))

    def selected_sources(self):
        return {self.source_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.source_list.count())
                if self.source_list.item(i).checkState() == Qt.CheckState.Checked}

    def set_sources(self,checked):
        if self.worker:
            return
        self.source_list.blockSignals(True)
        for i in range(self.source_list.count()):
            self.source_list.item(i).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.source_list.blockSignals(False)
        self.update_selection()

    def filter_sources(self,text):
        for i in range(self.source_list.count()):
            item = self.source_list.item(i)
            item.setHidden(text.casefold() not in item.data(Qt.ItemDataRole.UserRole).casefold())

    def use_all_dates(self):
        if self.index and not self.worker:
            for field,day in [(self.date_start,self.index.first_day),(self.date_end,self.index.last_day)]:
                field.setDate(QDate(day.year,day.month,day.day))

    def update_selection(self,*_):
        if not hasattr(self,"execute_button"):
            return
        selected = self.selected_sources()
        self.selected_label.setText(f"{len(selected)} / {self.source_list.count()}")
        self.select_all.setText("取消全选" if selected and len(selected) == self.source_list.count() else "全选")
        hint = "每次生成独立结果目录，保留已有导出。"
        valid = bool(self.index and selected and not self.worker)
        if self.worker:
            hint = "正在处理。取消或等待完成后可更改输入。"
        elif not self.index:
            hint = "先选择一个健康数据 ZIP 文件。"
        elif not selected:
            hint = "请选择至少一个来源后导出。"
        elif self.date_start.date() > self.date_end.date():
            hint,valid = "开始日期不能晚于结束日期。",False
        self.execute_button.setEnabled(valid)
        self.selection_hint.setText(hint)
        self.selection_hint.setVisible(bool(self.index and self.date_start.date() > self.date_end.date()))
        self.execute_button.setToolTip(hint)
        overlaps = self.index.overlapping_types(selected) if self.index else []
        self.overlap_details.setText(f"所选设备或 App 都记录了 {len(overlaps)} 项相同的健康指标。导出会保留每个来源的记录，不自动去重，因此不要直接跨来源相加。" if overlaps else "")
        self.overlap_details.setVisible(bool(overlaps) and self.details_button.isChecked())

    def start_export(self):
        if self.worker or not self.index or not self.execute_button.isEnabled():
            return False
        options = ExportOptions(self.selected_sources(),self.date_start.date().toPyDate(),
            self.date_end.date().toPyDate(),Path(self.destination.text()),self.privacy.isChecked(),self.excel_safe.isChecked())
        index = self.index
        return self.start_job("export",lambda **kw: export_archive(index,options,**kw))

    def cancel_job(self):
        if self.worker:
            self.worker.requestInterruption()
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText("正在取消…")
            self.status_label.setText("正在取消并清理临时文件…")

    def toggle_details(self,visible):
        self.log.setVisible(visible)
        self.overlap_details.setVisible(visible and bool(self.overlap_details.text()))
        self.details_button.setText("收起" if visible else "详情")

    def reveal_output(self):
        if self.result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.result.directory)))

    def closeEvent(self,event):
        if self.worker:
            self.close_pending = True
            self.cancel_job()
            self.status_label.setText("正在结束任务，清理完成后自动关闭…")
            event.ignore()
        else:
            self.resource_hud.timer.stop()
            self.preference_timer.stop()
            self.ring.timer.stop()
            self.ring.animation.stop()
            for surface in (self.toolbar, self.status_card):
                surface.detach_native()
            event.accept()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Apple Health Pro desktop")
    parser.add_argument("--demo",action="store_true",help="Load labelled synthetic data for local review")
    parser.add_argument("--smoke-test",metavar="REPORT_JSON",help="Verify frozen import/export with synthetic data, then exit")
    args = parser.parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Apple Health Pro")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("LEEcDiang")
    font = app.font()
    font.setPointSize(12)
    app.setFont(font)
    window = MainWindow()
    window.show()
    if args.smoke_test:
        from .smoke import run_smoke
        QTimer.singleShot(0,lambda: run_smoke(app,window,args.smoke_test))
    elif args.demo:
        QTimer.singleShot(0,window.load_demo)
    return app.exec()
