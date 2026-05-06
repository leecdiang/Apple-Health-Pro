import sys
import os
import zipfile
import pandas as pd
import xml.etree.ElementTree as ET
import time
import gc
import math
import psutil

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QFileDialog, 
    QScrollArea, QCheckBox, QMessageBox, QFrame, 
    QDateEdit, QStackedWidget, QTextEdit, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QDate, QTimer, 
    QPoint, QRectF, QRect, QPropertyAnimation, 
    QVariantAnimation, pyqtProperty
)
from PyQt6.QtGui import (
    QColor, QFont, QFontDatabase, QPainter, QPen
)

if sys.platform == 'darwin':
    os.environ["QT_MAC_WANTS_LAYER"] = "1"

# ==========================================
# 0. 资源监控线程 (精准对标 Windows 任务管理器版)
# ==========================================
class ResourceMonitorThread(QThread):
    update_sig = pyqtSignal(float, float, float)
    
    def __init__(self):
        super().__init__()
        self.process = psutil.Process(os.getpid())
        self.running = True
        # 精准获取你的 12700H 逻辑线程数 (20)
        self.core_count = psutil.cpu_count(logical=True) or 1
        self.total_sys_mem = psutil.virtual_memory().total

    def run(self):
        # 预热抛弃第一次无效数据
        self.process.cpu_percent(interval=None) 
        while self.running:
            try:
                # 🌟 绝杀：绝不使用 time.sleep！
                # 让 psutil 亲自监听这 1 秒钟内所有 C 底层线程的算力总和
                raw_cpu = self.process.cpu_percent(interval=1.0)
                
                # 算法完美对标任务管理器：该进程过去1秒所有线程总耗时 / CPU 总逻辑线程数
                cpu_pct = raw_cpu / self.core_count

                ram_rss = self.process.memory_info().rss
                ram_mb = ram_rss / (1024 * 1024)
                ram_pct = (ram_rss / self.total_sys_mem) * 100
                
                self.update_sig.emit(cpu_pct, ram_pct, ram_mb)
            except Exception:
                pass

    def stop(self): 
        self.running = False
        
# ==========================================
# 1. 核心数据解析与导出引擎 (深度内存优化版)
# ==========================================
class CleanStream:
    def __init__(self, stream): 
        self.stream = stream
        
    def read(self, size=-1):
        chunk = self.stream.read(size)
        if chunk:
            return chunk.replace(b'\x0b', b'')
        return chunk


class ParseThread(QThread):
    log_sig = pyqtSignal(str)
    done_sig = pyqtSignal(object, list, str, str, str) 
    err_sig = pyqtSignal(str)
    
    def __init__(self, zip_path): 
        super().__init__()
        self.zip_path = zip_path
        
    def run(self):
        try:
            self.log_sig.emit("[SYSTEM] Scanning ZIP architecture...")
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                xml_filename = None
                max_size = 0
                for info in zip_ref.infolist():
                    name = info.filename
                    if not name.lower().endswith('.xml') or name.lower().endswith('export_cda.xml'): 
                        continue
                        
                    try: 
                        decoded_name = name.encode('cp437').decode('utf-8')
                    except Exception:
                        try: 
                            decoded_name = name.encode('cp437').decode('gbk')
                        except Exception: 
                            decoded_name = name
                    
                    base_name = os.path.basename(decoded_name).lower()
                    if base_name in ["export.xml", "导出.xml", "輸出.xml"]:
                        xml_filename = name
                        self.log_sig.emit(f"[DETECTED] Source match: {decoded_name}")
                        break
                        
                    if info.file_size > max_size: 
                        max_size = info.file_size
                        xml_filename = name
                        
                if not xml_filename: 
                    self.err_sig.emit("CRITICAL: No valid health data XML found.")
                    return
                else:
                    if max_size > 0 and base_name not in ["export.xml", "导出.xml", "輸出.xml"]:
                        size_mb = max_size / 1024 / 1024
                        self.log_sig.emit(f"[DETECTED] Size match: {size_mb:.2f} MB")

                types, values, units, dates, sources = [], [], [], [], []

                with zip_ref.open(xml_filename) as f:
                    clean_stream = CleanStream(f) 
                    context = ET.iterparse(clean_stream, events=('end',))
                    try:
                        event, root = next(context)
                        count = 0
                        for event, elem in context:
                            if elem.tag in ['Record', 'Workout']:
                                sn = elem.attrib.get('sourceName')
                                if not sn:
                                    continue
                                
                                if elem.tag == 'Record':
                                    tp = elem.attrib.get('type', '')
                                    val = elem.attrib.get('value', '')
                                    unit = elem.attrib.get('unit', '')
                                else:
                                    tp = elem.attrib.get('workoutActivityType', 'Workout')
                                    val = elem.attrib.get('duration', '')
                                    unit = elem.attrib.get('durationUnit', 'min')

                                types.append(sys.intern(str(tp)))
                                values.append(val)
                                units.append(sys.intern(str(unit)))
                                dates.append(elem.attrib.get('startDate', ''))
                                sources.append(sys.intern(str(sn)))
                                
                                count += 1
                                if count % 500000 == 0: 
                                    self.log_sig.emit(f"[INDEXING] {count} records synced...")
                                
                                elem.clear()
                                root.clear()
                    except ET.ParseError: 
                        pass
            
            self.log_sig.emit("[SYSTEM] Structuring DataFrame & Optimizing RAM...")
            df = pd.DataFrame({
                'type': types,
                'value': values,
                'unit': units,
                'startdate': dates,
                'sourcename': sources
            })
            
            del types, values, units, dates, sources
            gc.collect()
            
            if not df.empty:
                for col in ['sourcename', 'type', 'unit']:
                    if col in df.columns:
                        df[col] = df[col].astype('category')
            
            if not df.empty:
                valid_dates = df['startdate'].dropna().str[:10]
                if not valid_dates.empty:
                    min_date = valid_dates.min()
                    max_date = valid_dates.max()
                else:
                    min_date = "2005-08-20"
                    max_date = QDate.currentDate().toString("yyyy-MM-dd")
            else: 
                min_date = "2005-08-20"
                max_date = QDate.currentDate().toString("yyyy-MM-dd")
                
            sources_list = sorted(df['sourcename'].unique().tolist()) if not df.empty else []
            self.done_sig.emit(df, sources_list, self.zip_path, min_date, max_date)
            
        except Exception as e: 
            self.err_sig.emit(f"SYSTEM ERROR: {str(e)}")


class ExportThread(QThread):
    log_sig = pyqtSignal(str)
    progress_sig = pyqtSignal(int)
    done_sig = pyqtSignal()
    
    def __init__(self, df, selected_sources, zip_path, start_date_str, end_date_str, privacy_mode):
        super().__init__()
        self.df = df
        self.selected_sources = selected_sources
        self.zip_path = zip_path
        self.start_date_str = start_date_str
        self.end_date_str = end_date_str
        self.privacy_mode = privacy_mode
        self.CHUNK_SIZE = 880000

    def run(self):
        try:
            self.log_sig.emit("[SYSTEM] Multi-dimensional export initiated.")
            filtered_df = self.df[self.df['sourcename'].isin(self.selected_sources)].copy()
            
            dates_str = filtered_df['startdate'].str[:10] 
            date_mask = (dates_str >= self.start_date_str) & (dates_str <= self.end_date_str)
            filtered_df = filtered_df[date_mask]
            
            if filtered_df.empty: 
                self.log_sig.emit("[ERROR] No data falls within the selected date range.")
                self.done_sig.emit()
                return

            if self.privacy_mode:
                if filtered_df['sourcename'].dtype.name == 'category':
                    filtered_df['sourcename'] = filtered_df['sourcename'].cat.remove_unused_categories()
                    
                unique_sources = filtered_df['sourcename'].unique()
                source_map = {name: f"AppleHealthPro_Device_{i+1:02d}" for i, name in enumerate(unique_sources)}
                
                if filtered_df['sourcename'].dtype.name == 'category':
                    filtered_df['sourcename'] = filtered_df['sourcename'].cat.rename_categories(source_map)
                else:
                    filtered_df['sourcename'] = filtered_df['sourcename'].map(source_map)

            out_dir = os.path.dirname(self.zip_path)
            groups = {
                '1_Heart_Cardio': ['heartrate', 'restingheartrate', 'heartratevariability', 'walkingheartrateaverage'], 
                '2_Body_Metrics': ['bodymass', 'bmi', 'bodyfat', 'leanbodymass', 'bodywatermass'], 
                '3_Daily_Activity': ['stepcount', 'activeenergy', 'basalenergy', 'distance', 'flights'],
                '4_Sleep_Recovery': ['sleepanalysis'],
                '5_Mobility_Gait': ['walkingspeed', 'steplength', 'asymmetry', 'support', 'steadiness'],
                '6_Reproductive': ['menstrual', 'ovulation', 'cervical'],
                '7_Vitals_Respiratory': ['oxygensaturation', 'respiratoryrate', 'bodytemperature', 'bloodpressure'],
                '8_Running_Dynamics': ['runningpower', 'verticaloscillation', 'groundcontact', 'runningstridelength', 'runningspeed'],
                '9_Cycling_Stats': ['cyclingpower', 'cadence', 'cyclingspeed', 'functionalthreshold'],
                '10_Swimming_Water': ['swimming', 'strokecount', 'underwater', 'watertemperature'],
                '11_Workouts_Training': ['workout', 'hkworkout', 'running', 'walking', 'cycling', 'strength'],
                '12_Environment_Senses': ['timeindaylight', 'environmentalaudio', 'headphoneaudio'], 
                '13_Nutrition_Hydration': ['dietary', 'water', 'caffeine'],
                '14_Mindfulness_Mental': ['mindful', 'stateofmind'],
                '15_Symptoms_Illness': ['symptom'] 
            }

            total_groups = len(groups)
            for current_idx, (base_name, keys) in enumerate(groups.items(), 1):
                pattern = '|'.join(keys)
                subset = filtered_df[filtered_df['type'].str.lower().str.contains(pattern, na=False)]
                
                if not subset.empty:
                    if 'Reproductive' in base_name:
                        subset.loc[:, 'value'] = subset['value'].str.replace('HKCategoryValueVaginalBleeding', '', regex=False)
                    
                    row_count = len(subset)
                    if row_count > self.CHUNK_SIZE:
                        num_parts = math.ceil(row_count / self.CHUNK_SIZE)
                        for i in range(num_parts):
                            chunk = subset.iloc[i * self.CHUNK_SIZE : (i + 1) * self.CHUNK_SIZE]
                            chunk_file = os.path.join(out_dir, f"{base_name}_Part{i+1}.csv")
                            chunk.to_csv(chunk_file, index=False, encoding='utf-8-sig')
                    else:
                        file_path = os.path.join(out_dir, f"{base_name}.csv")
                        subset.to_csv(file_path, index=False, encoding='utf-8-sig')
                        self.log_sig.emit(f"[SUCCESS] Saved {base_name}.csv")
                
                self.progress_sig.emit(int((current_idx / total_groups) * 100))

            self.log_sig.emit("[SUCCESS] All operations finished.")
            self.done_sig.emit()
        except Exception as e: 
            self.log_sig.emit(f"[ERROR] Export failed: {str(e)}")
            self.done_sig.emit()


# ==========================================
# 2. UI 组件库 (引入平滑属性动画引擎)
# ==========================================
class MiniRing(QWidget):
    def __init__(self, light_color="#9B2C2C", dark_color="#FF6961"):
        super().__init__()
        self.setFixedSize(14, 14) 
        self.light_color, self.dark_color = QColor(light_color), QColor(dark_color)
        self.color, self.bg_color, self.pct = self.light_color, QColor(0, 0, 0, 15), 0.0

    def set_pct(self, pct): 
        self.pct = max(0, min(100, pct))
        self.update()
        
    def set_theme(self, is_dark):
        self.bg_color = QColor(255, 255, 255, 30) if is_dark else QColor(0, 0, 0, 15)
        self.color = self.dark_color if is_dark else self.light_color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(2, 2, 10, 10)
        painter.setPen(QPen(self.bg_color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, 0, 360 * 16)
        painter.setPen(QPen(self.color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, 90 * 16, int(-(self.pct / 100.0) * 360 * 16))


class ProgressRing(QWidget):
    clicked = pyqtSignal()  # 🌟 1. 声明一个点击信号

    def __init__(self):
        super().__init__()
        self.setFixedSize(160, 160)
        self._progress = 0.0
        self._current_color = QColor("#86868B")
        self._is_pulsing, self._pulse_angle = False, 0
        self.state_text = "STANDBY"
        self.bg_color, self.text_color = QColor(230, 230, 235), QColor("#1D1D1F")

        self.prog_anim = QPropertyAnimation(self, b"progress")
        self.prog_anim.setDuration(1000) 
        self.color_anim = QVariantAnimation(self)
        self.color_anim.setDuration(800)
        self.color_anim.valueChanged.connect(self._on_color_changed)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_pulse)

    @pyqtProperty(float)
    def progress(self): 
        return self._progress
        
    @progress.setter
    def progress(self, value):
        self._progress = value
        self.update()

    def _on_color_changed(self, color):
        self._current_color = color
        self.update()

    def set_state(self, text, color_hex, progress=None):
        self.state_text = text
        self.color_anim.stop()
        self.color_anim.setStartValue(self._current_color)
        self.color_anim.setEndValue(QColor(color_hex))
        self.color_anim.start()

        if progress is not None: 
            self._is_pulsing = False
            self.timer.stop()
            self.prog_anim.stop()
            self.prog_anim.setStartValue(self._progress)
            self.prog_anim.setEndValue(float(progress))
            self.prog_anim.start()
        self.update()

    def start_pulse(self): 
        self._is_pulsing, self._progress, self._pulse_angle = True, 0, 0
        self.timer.start(16) 
        
    def stop_pulse(self):
        self._is_pulsing = False
        self.timer.stop()
        self.update()
        
    def update_pulse(self): 
        self._pulse_angle = (self._pulse_angle + 2) % 360
        self.update()

    def set_theme(self, is_dark):
        self.bg_color = QColor("#38383A") if is_dark else QColor(230, 230, 235)
        self.text_color = QColor("#F5F5F7") if is_dark else QColor("#1D1D1F")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(14, 14, -14, -14)
        painter.setPen(QPen(self.bg_color, 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, 0, 360 * 16)
        painter.setPen(QPen(self._current_color, 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        if self._is_pulsing: 
            painter.drawArc(rect, -self._pulse_angle * 16, 100 * 16)
        else: 
            painter.drawArc(rect, 90 * 16, int(-(self._progress / 100.0) * 360 * 16))
        painter.setPen(self.text_color)
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(12 if len(self.state_text) > 6 else 22)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.state_text)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit() # 发射点击信号
        super().mousePressEvent(event)


# ==========================================
# 3. 终极强迫症排版主窗口
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.dragPos, self._resize_dir = None, None
        self._resize_start_geom, self._edge_margin = QRect(), 6
        self.checkboxes, self.df, self.zip_path = [], None, None
        self.current_accent, self.success_color = "#9B2C2C", "#10B981"
        
        try: 
            self.is_dark_mode = (QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark)
        except Exception: 
            self.is_dark_mode = False
        
        self.init_typography()
        self.setMinimumSize(850, 550)
        self.resize(1050, 650)
        self.init_ui()
        self.apply_theme() 
        self.monitor_thread = ResourceMonitorThread()
        self.monitor_thread.update_sig.connect(self.update_hud)
        self.monitor_thread.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.pos())
            if isinstance(child, (QFrame, QLabel)) or child is None:
                self.dragPos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
            dir = self._get_resize_dir(event.pos())
            if dir:
                self._resize_dir = dir
                self._resize_start_geom = self.geometry()
                self._resize_start_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        g_pos = event.globalPosition().toPoint()
        if event.buttons() == Qt.MouseButton.LeftButton and self._resize_dir:
            self._do_resize(g_pos)
        elif event.buttons() == Qt.MouseButton.LeftButton and self.dragPos is not None:
            self.move(g_pos - self.dragPos)
        else:
            dir = self._get_resize_dir(self.mapFromGlobal(g_pos))
            self.setCursor(self._get_cursor_shape(dir) if dir else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event): 
        self.dragPos = None
        self._resize_dir = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        event.accept()

    def _get_resize_dir(self, pos):
        x, y, w, h, m = pos.x(), pos.y(), self.width(), self.height(), self._edge_margin
        if x < 0 or y < 0 or x > w or y > h: 
            return None
        dir = ""
        if y <= m: dir += "top"
        elif y >= h - m: dir += "bottom"
        if x <= m: dir += "left"
        elif x >= w - m: dir += "right"
        return dir or None

    def _get_cursor_shape(self, dir):
        shapes = {
            "top": Qt.CursorShape.SizeVerCursor, 
            "bottom": Qt.CursorShape.SizeVerCursor,
            "left": Qt.CursorShape.SizeHorCursor, 
            "right": Qt.CursorShape.SizeHorCursor,
            "topleft": Qt.CursorShape.SizeFDiagCursor, 
            "bottomright": Qt.CursorShape.SizeFDiagCursor,
            "topright": Qt.CursorShape.SizeBDiagCursor, 
            "bottomleft": Qt.CursorShape.SizeBDiagCursor
        }
        return shapes.get(dir, Qt.CursorShape.ArrowCursor)

    def _do_resize(self, global_pos):
        delta = global_pos - self._resize_start_pos
        rect = QRect(self._resize_start_geom)
        if "left" in self._resize_dir: rect.setLeft(rect.left() + delta.x())
        elif "right" in self._resize_dir: rect.setRight(rect.right() + delta.x())
        if "top" in self._resize_dir: rect.setTop(rect.top() + delta.y())
        elif "bottom" in self._resize_dir: rect.setBottom(rect.bottom() + delta.y())
        if rect.width() >= self.minimumWidth() and rect.height() >= self.minimumHeight(): 
            self.setGeometry(rect)

    def init_typography(self):
        self.font_family = "-apple-system, BlinkMacSystemFont, 'Segoe UI Variable', 'Segoe UI', 'Microsoft YaHei'"
        QApplication.setFont(QFont(self.font_family, 10))

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()

    def apply_theme(self):
        self.btn_theme.setText("☀️" if self.is_dark_mode else "🌙")
        self.ring.set_theme(self.is_dark_mode)
        self.ring_cpu.set_theme(self.is_dark_mode)
        self.ring_ram.set_theme(self.is_dark_mode)
        
        if self.is_dark_mode:
            c_bg = "#121214"
            c_panel = "#1C1C1E"
            c_card = "#242426"
            c_text = "#FFFFFF"
            c_sub = "#8E8E93"
            c_border = "#2C2C2E"
            c_hover = "rgba(255,255,255,0.08)"
            c_badge = "rgba(255,255,255,0.05)"
            
            self.current_accent = "#FF6961"
            self.success_color = "#32D74B"
            c_primary_bg = "#FF6961"
            c_primary_hover = "#FF453A"
            c_scroll_handle = "#5C5C60"
            c_check_border = "#5C5C60"
            
            c_close_bg = "#FF453A"
            c_close_hover = "#FF6961"
        else:
            c_bg = "#F5F5F7"
            c_panel = "#FFFFFF"
            c_card = "#F9F9FB"
            c_text = "#1D1D1F"
            c_sub = "#86868B"
            c_border = "#E5E5EA"
            c_hover = "rgba(0,0,0,0.05)"
            c_badge = "rgba(0,0,0,0.04)"
            
            self.current_accent = "#9B2C2C"
            self.success_color = "#10B981"
            c_primary_bg = "#9B2C2C"
            c_primary_hover = "#7A2323"
            c_scroll_handle = "#C7C7CC"
            c_check_border = "#C7C7CC"
            
            # 👇 将这里原本的交通灯红替换为你的品牌主色调
            c_close_bg = "#9B2C2C" 
            c_close_hover = "#7A2323"
        
        tick_b64 = "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIwIDYgOSAxNyA0IDEyIj48L3BvbHlsaW5lPjwvc3ZnPg=="
        
        self.setStyleSheet(f"""
            QWidget {{ font-family: "{self.font_family}"; color: {c_text}; }} 
            QFrame#bg_panel {{ background-color: {c_bg}; border-radius: 20px; border: 1px solid {c_border}; }} 
            QFrame#right_panel {{ background-color: {c_panel}; border-top-right-radius: 20px; border-bottom-right-radius: 20px; border-left: 1px solid {c_border}; }} 
            
            /* 🌟 独立的关闭按钮样式：纯正 Apple Red */
            QPushButton#btn_close {{ background: {c_close_bg}; color: #FFFFFF; border-radius: 12px; font-weight: 900; font-size: 15px; padding-bottom: 2px; border: none; }} 
            QPushButton#btn_close:hover {{ background: {c_close_hover}; }} 
            
            QPushButton#btn_theme {{ background: {c_hover}; color: {c_text}; border-radius: 12px; font-size: 14px; border: none; }} 
            QPushButton#btn_theme:hover {{ background: rgba(155,44,44,0.2); }} 
            
            QFrame#hud_badge {{ background-color: {c_badge}; border-radius: 11px; border: none; }} 
            QLabel#hud_text {{ color: {c_sub}; font-family: ui-monospace; font-size: 11px; font-weight: 700; border: none; }} 
            
            /* 🌟 大气的主副标题排版 */
            QLabel#app_logo_main {{ color: {self.current_accent}; font-size: 21px; font-weight: 900; opacity: 0.9; letter-spacing: -0.2px; border: none; }} 
            QLabel#app_logo_sub {{ color: {c_sub}; font-size: 10px; font-weight: 800; letter-spacing: 3px; border: none; }} 
            
            QLabel#section_title {{ font-size: 11px; color: {c_sub}; font-weight: 800; letter-spacing: 1.5px; border: none; margin: 0px; padding: 0px; }} 
            QLabel#dropzone {{ border: 2px dashed rgba(134, 134, 139, 0.25); border-radius: 16px; color: {c_sub}; font-weight: 600; font-size: 15px; padding: 60px 40px; }} 
            QLabel#dropzone:hover {{ background-color: rgba(155, 44, 44, 0.05); border-color: {self.current_accent}; color: {self.current_accent}; }} 
            QTextEdit#log_view {{ background: transparent; border: none; color: {c_sub}; font-family: ui-monospace; font-size: 11px; line-height: 1.5; }} 
            
            QScrollArea#inset_scroll {{ border: none; background-color: transparent; }}
            QScrollArea QWidget {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ border: none; background: transparent; width: 8px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: {c_scroll_handle}; border-radius: 4px; min-height: 40px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; background: none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
            
            QCheckBox {{ background: transparent; border-radius: 8px; padding: 8px 4px; spacing: 12px; margin: 0px; font-size: 14px; font-weight: 600; border: 1px solid transparent; }}
            QCheckBox:hover {{ background: {c_hover}; }}
            QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 6px; border: 1.5px solid {c_check_border}; background: {c_panel}; }}
            QCheckBox::indicator:checked {{ background: {c_primary_bg}; border-color: {c_primary_bg}; image: url("data:image/svg+xml;base64,{tick_b64}"); }} 
            
            QPushButton#btn_text_link {{ background: transparent; color: {self.current_accent}; font-size: 13px; font-weight: 700; border: none; padding: 0px 8px; }}
            QPushButton#btn_text_link:hover {{ color: {c_primary_hover}; background: {c_hover}; border-radius: 6px; }}
            
            QPushButton#btn_primary {{ background-color: {c_primary_bg}; color: white; border-radius: 14px; font-weight: 700; font-size: 15px; letter-spacing: 1px; border: none; }} 
            QPushButton#btn_primary:hover {{ background-color: {c_primary_hover}; }}
            QPushButton#btn_primary:disabled {{ background-color: {c_card}; color: {c_sub}; border: 1px solid {c_border}; }}
            
            QDateEdit {{ background: {c_card}; color: {self.current_accent}; border: 1px solid {c_border}; border-radius: 10px; min-height: 42px; max-height: 42px; font-size: 15px; font-weight: 700; qproperty-alignment: AlignCenter; }}
            QDateEdit > QLineEdit {{ background: transparent; border: none; qproperty-alignment: AlignCenter; }}
            QDateEdit:hover {{ border: 1px solid rgba(155, 44, 44, 0.4); background: {c_hover}; }}
            QDateEdit::up-button, QDateEdit::down-button {{ width: 0px; height: 0px; border: none; background: transparent; }}
        """)

    def update_hud(self, cpu_pct, ram_pct, ram_mb):
        self.ring_cpu.set_pct(cpu_pct)
        self.lbl_cpu.setText(f"CPU {cpu_pct:.1f}%")
        self.ring_ram.set_pct(ram_pct)
        self.lbl_ram.setText(f"RAM {ram_mb/1024:.2f} GB" if ram_mb >= 1024 else f"RAM {ram_mb:.0f} MB")

    def on_toggle_all(self):
        if not self.checkboxes: 
            return
        target = not self.checkboxes[0].isChecked()
        for cb in self.checkboxes: 
            cb.setChecked(target)

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.setMouseTracking(True)
        self.central_widget.setMouseTracking(True)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.bg_panel = QFrame()
        self.bg_panel.setObjectName("bg_panel")
        self.bg_panel.setMouseTracking(True)
        
        self.bg_layout = QHBoxLayout(self.bg_panel)
        self.bg_layout.setContentsMargins(0, 0, 0, 0)
        self.bg_layout.setSpacing(0)
        self.main_layout.addWidget(self.bg_panel)
        
        self.left_panel = QFrame()
        self.left_layout = QVBoxLayout(self.left_panel)
        # 🌟 缩小边距：留出更多内部空间
        self.left_layout.setContentsMargins(20, 20, 20, 20)
        self.bg_layout.addWidget(self.left_panel, stretch=4)
        
        left_header_widget = QWidget()
        left_header_widget.setFixedHeight(32)
        header_row = QHBoxLayout(left_header_widget)
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)
        
        self.btn_close = QPushButton("×")
        self.btn_close.setObjectName("btn_close") # 🌟 修改了 ObjectName
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.clicked.connect(self.close)
        header_row.addWidget(self.btn_close, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("btn_theme")
        self.btn_theme.setFixedSize(24, 24)
        self.btn_theme.clicked.connect(self.toggle_theme)
        header_row.addWidget(self.btn_theme, alignment=Qt.AlignmentFlag.AlignVCenter)
        header_row.addStretch()
        
        self.badge_cpu = QFrame()
        self.badge_cpu.setObjectName("hud_badge")
        lay_cpu = QHBoxLayout(self.badge_cpu)
        lay_cpu.setContentsMargins(8, 4, 10, 4)
        self.ring_cpu = MiniRing("#9B2C2C", "#FF6961")
        self.lbl_cpu = QLabel("CPU --%")
        self.lbl_cpu.setObjectName("hud_text")
        lay_cpu.addWidget(self.ring_cpu)
        lay_cpu.addWidget(self.lbl_cpu)
        header_row.addWidget(self.badge_cpu, alignment=Qt.AlignmentFlag.AlignVCenter)
        header_row.addStretch()
        
        self.badge_ram = QFrame()
        self.badge_ram.setObjectName("hud_badge")
        lay_ram = QHBoxLayout(self.badge_ram)
        lay_ram.setContentsMargins(8, 4, 10, 4)
        self.ring_ram = MiniRing("#007AFF", "#64D2FF")
        self.lbl_ram = QLabel("RAM -- GB")
        self.lbl_ram.setObjectName("hud_text")
        lay_ram.addWidget(self.ring_ram)
        lay_ram.addWidget(self.lbl_ram)
        header_row.addWidget(self.badge_ram, alignment=Qt.AlignmentFlag.AlignVCenter)
        header_row.addStretch()
        
        self.left_layout.addWidget(left_header_widget)
        self.stack = QStackedWidget()
        self.left_layout.addWidget(self.stack)
        
        self.page_drop = QWidget()
        drop_lay = QVBoxLayout(self.page_drop)
        self.lbl_dropzone = QLabel("Drop Health Data (.zip) Here\n\nOr Click to Browse")
        self.lbl_dropzone.setObjectName("dropzone")
        self.lbl_dropzone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_dropzone.mousePressEvent = self.on_click_browse
        drop_lay.addWidget(self.lbl_dropzone)
        self.stack.addWidget(self.page_drop)
        
        self.page_progress = QWidget()
        prog_lay = QVBoxLayout(self.page_progress)
        self.ring = ProgressRing()
        self.ring.clicked.connect(self.on_ring_clicked)
        prog_lay.addWidget(self.ring, alignment=Qt.AlignmentFlag.AlignCenter)
        self.log_view = QTextEdit()
        self.log_view.setObjectName("log_view")
        self.log_view.setReadOnly(True)
        prog_lay.addWidget(self.log_view)
        self.stack.addWidget(self.page_progress)
        
        self.left_layout.addSpacing(10)
        
        # 🌟 经典主副标题排版回归
        logo_container = QWidget()
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(6)
        
        lbl_main = QLabel("Apple Health Pro")
        lbl_main.setObjectName("app_logo_main")
        lbl_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_sub = QLabel("UNLOCK YOUR HEALTH DATA")
        lbl_sub.setObjectName("app_logo_sub")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        logo_layout.addWidget(lbl_main)
        logo_layout.addWidget(lbl_sub)
        self.left_layout.addWidget(logo_container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.right_panel = QFrame()
        self.right_panel.setObjectName("right_panel")
        self.right_layout = QVBoxLayout(self.right_panel)
        # 🌟 缩小边距：留出更多内部空间
        self.right_layout.setContentsMargins(20, 20, 20, 20)
        self.right_layout.setSpacing(15)
        self.bg_layout.addWidget(self.right_panel, stretch=6)
        
        right_header_widget = QWidget()
        right_header_widget.setFixedHeight(32)
        src_header = QHBoxLayout(right_header_widget)
        src_header.setContentsMargins(0, 0, 0, 0)
        
        lbl_source = QLabel("DATA SOURCES")
        lbl_source.setObjectName("section_title")
        src_header.addWidget(lbl_source, alignment=Qt.AlignmentFlag.AlignVCenter)
        src_header.addStretch()
        
        self.btn_toggle = QPushButton("Toggle All")
        self.btn_toggle.setObjectName("btn_text_link")
        self.btn_toggle.clicked.connect(self.on_toggle_all)
        src_header.addWidget(self.btn_toggle, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.right_layout.addWidget(right_header_widget)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("inset_scroll")
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll.setWidget(self.scroll_content)
        self.right_layout.addWidget(self.scroll, stretch=1)
        
        lbl_dr = QLabel("DATE RANGE")
        lbl_dr.setObjectName("section_title")
        self.right_layout.addWidget(lbl_dr)
        
        date_row = QHBoxLayout()
        self.date_start = QDateEdit()
        self.date_start.setDisplayFormat("yyyy-MM-dd")
        self.date_start.setCalendarPopup(False)
        self.date_start.setDate(QDate(2005, 8, 20))  # 🌟 设置默认起始日期

        self.date_end = QDateEdit()
        self.date_end.setDisplayFormat("yyyy-MM-dd")
        self.date_end.setCalendarPopup(False)
        self.date_end.setDate(QDate.currentDate())   # 🌟 设置默认结束日期为系统当天
        
        date_row.addWidget(self.date_start, stretch=1)
        date_row.addWidget(QLabel("→"))
        date_row.addWidget(self.date_end, stretch=1)
        self.right_layout.addLayout(date_row)
        
        self.cb_privacy = QCheckBox(" Mask Device Names")
        self.right_layout.addWidget(self.cb_privacy)
        self.btn_execute = QPushButton("EXECUTE EXPORT")
        self.btn_execute.setObjectName("btn_primary")
        self.btn_execute.setFixedHeight(55)
        self.btn_execute.clicked.connect(self.on_export)
        self.btn_execute.setEnabled(False)
        self.right_layout.addWidget(self.btn_execute)
        
        self.setAcceptDrops(True)
        
        for child in self.findChildren(QWidget):
            child.setMouseTracking(True)

    def dragEnterEvent(self, event): 
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].toLocalFile().endswith('.zip'): 
            self.process_zip(urls[0].toLocalFile())

    def on_click_browse(self, event):
        path, _ = QFileDialog.getOpenFileName(self, "Select ZIP", "", "ZIP Archive (*.zip)")
        if path: 
            self.process_zip(path)

    def process_zip(self, path):
        self.stack.setCurrentWidget(self.page_progress)
        self.ring.set_state("INDEXING", "#F59E0B")
        self.ring.start_pulse()
        self.log_view.clear()
        self.btn_execute.setEnabled(False)
        self.worker = ParseThread(path)
        self.worker.log_sig.connect(self.log_view.append)
        self.worker.done_sig.connect(self.on_parse_done)
        self.worker.start()

    def on_parse_done(self, df, sources, zip_path, min_date, max_date):
        self.df, self.zip_path = df, zip_path
        self.ring.stop_pulse()
        self.ring.set_state("READY", self.success_color, 100)
        self.ring.setCursor(Qt.CursorShape.PointingHandCursor)
        
        for i in reversed(range(self.scroll_layout.count())):
            if self.scroll_layout.itemAt(i).widget(): 
                self.scroll_layout.itemAt(i).widget().deleteLater()
                
        self.checkboxes = []
        for s in sources:
            cb = QCheckBox(s)
            self.scroll_layout.addWidget(cb)
            self.checkboxes.append(cb)
            
        self.scroll_layout.addStretch()
        self.date_start.setDate(QDate.fromString(min_date, "yyyy-MM-dd"))
        self.date_end.setDate(QDate.fromString(max_date, "yyyy-MM-dd"))
        self.btn_execute.setEnabled(True)

    def on_export(self):
        selected = [cb.text() for cb in self.checkboxes if cb.isChecked()]
        if not selected: 
            return
            
        self.btn_execute.setEnabled(False)
        self.btn_execute.setText("PROCESSING...")
        self.log_view.clear()
        self.ring.set_state("0%", self.current_accent, 0)
        self.ring.setCursor(Qt.CursorShape.ArrowCursor)
        
        self.exporter = ExportThread(self.df, selected, self.zip_path, 
                                     self.date_start.date().toString("yyyy-MM-dd"), 
                                     self.date_end.date().toString("yyyy-MM-dd"), 
                                     self.cb_privacy.isChecked())
        self.exporter.log_sig.connect(self.log_view.append)
        self.exporter.progress_sig.connect(lambda p: self.ring.set_state(f"{p}%", self.current_accent, p))
        self.exporter.done_sig.connect(self.on_export_done)
        self.exporter.start()

    def on_export_done(self):
        self.ring.set_state("COMPLETED", self.success_color, 100)
        self.ring.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_execute.setText("EXECUTE EXPORT")
        self.btn_execute.setEnabled(True)

    # 🌟 1. 接收到圆环点击信号后的判断逻辑
    def on_ring_clicked(self):
        # 只有在等待操作或完成状态下，才允许重置，防止打断正在进行的解析或导出
        if self.ring.state_text in ["COMPLETED", "READY"]:
            self.reset_app()

    # 🌟 2. 彻底重置 App 状态，并强制回收内存
    def reset_app(self):
        # 切换回拖拽上传页
        self.stack.setCurrentWidget(self.page_drop)
        
        # 重置圆环外观与光标
        self.ring.set_state("STANDBY", "#86868B", 0)
        self.ring.setCursor(Qt.CursorShape.ArrowCursor)
        
        # 清理日志区与按钮
        self.log_view.clear()
        self.btn_execute.setEnabled(False)
        self.btn_execute.setText("EXECUTE EXPORT")
        
        # 销毁右侧所有数据源勾选框
        for i in reversed(range(self.scroll_layout.count())):
            w = self.scroll_layout.itemAt(i).widget()
            if w: 
                w.deleteLater()
        self.checkboxes = []
        
        # 恢复默认日期
        self.date_start.setDate(QDate(2005, 8, 20))
        self.date_end.setDate(QDate.currentDate())
        
        # 彻底释放上一个 ZIP 的内存占用
        self.df = None
        self.zip_path = None
        gc.collect()

    def closeEvent(self, event): 
        self.monitor_thread.stop()
        self.monitor_thread.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'): 
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'): 
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    win = MainWindow()
    win.show()
    sys.exit(app.exec())