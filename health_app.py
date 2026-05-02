import sys, os, zipfile, pandas as pd, xml.etree.ElementTree as ET, time, io, math
import psutil
import gc
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QTextEdit, QLabel,
                             QFileDialog, QScrollArea, QCheckBox, QMessageBox, 
                             QFrame, QGraphicsDropShadowEffect, QDateEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QColor, QFont

if sys.platform == 'darwin':
    os.environ["QT_MAC_WANTS_LAYER"] = "1"

# ==========================================
# 0. System Monitor Thread
# ==========================================
class ResourceMonitorThread(QThread):
    update_sig = pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        self.process = psutil.Process(os.getpid())
        self.running = True
        self.core_count = psutil.cpu_count() or 1

    def run(self):
        self.process.cpu_percent(interval=None) 
        while self.running:
            time.sleep(1)
            try:
                cpu = self.process.cpu_percent(interval=None) / self.core_count
                ram = self.process.memory_info().rss / (1024 * 1024)
                self.update_sig.emit(cpu, ram)
            except:
                pass

    def stop(self):
        self.running = False

# ==========================================
# 0.5 Memory Optimization Core
# ==========================================
class CleanStream:
    def __init__(self, stream):
        self.stream = stream
    def read(self, size=-1):
        chunk = self.stream.read(size)
        if chunk:
            return chunk.replace(b'\x0b', b'')
        return chunk

# ==========================================
# 1. High-Performance Core Engine
# ==========================================
class ParseThread(QThread):
    log_sig = pyqtSignal(str)
    done_sig = pyqtSignal(object, list, str, str, str) 
    err_sig = pyqtSignal(str)

    def __init__(self, zip_path):
        super().__init__()
        self.zip_path = zip_path

    def run(self):
        try:
            self.log_sig.emit("<span style='color: #86868B;'>[SYSTEM]</span> Scanning ZIP architecture...")
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                xml_filename = None
                max_size = 0
                for info in zip_ref.infolist():
                    name = info.filename
                    if not name.lower().endswith('.xml') or name.lower().endswith('export_cda.xml'): continue
                    try: decoded_name = name.encode('cp437').decode('utf-8')
                    except:
                        try: decoded_name = name.encode('cp437').decode('gbk')
                        except: decoded_name = name

                    base_name = os.path.basename(decoded_name).lower()
                    if base_name in ["export.xml", "导出.xml", "輸出.xml"]:
                        xml_filename = name
                        self.log_sig.emit(f"<span style='color: #3B82F6;'>[DETECTED]</span> Source match: {decoded_name}")
                        break
                    if info.file_size > max_size:
                        max_size = info.file_size
                        xml_filename = name
                        
                if not xml_filename:
                    self.err_sig.emit("CRITICAL: No valid health data XML found.")
                    return
                else:
                    if max_size > 0 and base_name not in ["export.xml", "导出.xml", "輸出.xml"]:
                        self.log_sig.emit(f"<span style='color: #3B82F6;'>[DETECTED]</span> Size match: {max_size / 1024 / 1024:.2f} MB")

                attribute_list = []
                with zip_ref.open(xml_filename) as f:
                    clean_stream = CleanStream(f) 
                    context = ET.iterparse(clean_stream, events=('end',))
                    try:
                        event, root = next(context)
                        count = 0
                        for event, elem in context:
                            if elem.tag in ['Record', 'Workout']:
                                if elem.tag == 'Record':
                                    sn = elem.attrib.get('sourceName')
                                    tp = elem.attrib.get('type', '')
                                    val = elem.attrib.get('value', '')
                                    unit = elem.attrib.get('unit', '')
                                    sdate = elem.attrib.get('startDate', '')
                                else:
                                    sn = elem.attrib.get('sourceName')
                                    tp = elem.attrib.get('workoutActivityType', 'Workout')
                                    val = elem.attrib.get('duration', '')
                                    unit = elem.attrib.get('durationUnit', 'min')
                                    sdate = elem.attrib.get('startDate', '')

                                if sn:
                                    attribute_list.append({
                                        'type': sys.intern(str(tp)),
                                        'value': val, 
                                        'unit': sys.intern(str(unit)),
                                        'startdate': sdate,
                                        'sourcename': sys.intern(str(sn))
                                    })
                                    count += 1
                                    if count % 500000 == 0:
                                        self.log_sig.emit(f"<span style='color: #F59E0B;'>[INDEXING]</span> {count} records synced...")
                                
                                elem.clear()
                                root.clear()
                    except ET.ParseError: pass
            gc.collect()
            df = pd.DataFrame(attribute_list)
            sources = sorted(df['sourcename'].unique().tolist())
            
            if not df.empty:
                valid_dates = df['startdate'].dropna().str[:10]
                min_date = valid_dates.min() if not valid_dates.empty else "2014-09-01"
                max_date = valid_dates.max() if not valid_dates.empty else QDate.currentDate().toString("yyyy-MM-dd")
            else:
                min_date, max_date = "2014-09-01", QDate.currentDate().toString("yyyy-MM-dd")

            self.done_sig.emit(df, sources, self.zip_path, min_date, max_date)
            
        except Exception as e: 
            self.err_sig.emit(f"SYSTEM ERROR: {str(e)}")

class ExportThread(QThread):
    log_sig = pyqtSignal(str)
    done_sig = pyqtSignal()

    def __init__(self, df, selected_sources, zip_path, start_date_str, end_date_str, privacy_mode):
        super().__init__()
        self.df, self.selected_sources, self.zip_path = df, selected_sources, zip_path
        self.start_date_str, self.end_date_str, self.privacy_mode = start_date_str, end_date_str, privacy_mode
        self.CHUNK_SIZE = 880000

    def run(self):
        try:
            self.log_sig.emit(f"<br><span style='color: #3B82F6;'>[START]</span> Multi-dimensional export initiated.")
            filtered_df = self.df[self.df['sourcename'].isin(self.selected_sources)].copy()
            
            self.log_sig.emit(f"<span style='color: #86868B;'>[FILTER]</span> Applying dates: {self.start_date_str} to {self.end_date_str}")
            dates_str = filtered_df['startdate'].str[:10] 
            date_mask = (dates_str >= self.start_date_str) & (dates_str <= self.end_date_str)
            filtered_df = filtered_df[date_mask]
            
            if filtered_df.empty:
                self.log_sig.emit("<span style='color: #EF4444;'>[ABORT]</span> No data falls within the selected date range.")
                self.done_sig.emit(); return

            if self.privacy_mode:
                self.log_sig.emit("<span style='color: #10B981;'>[SHIELD]</span> Anonymizing device identities...")
                unique_sources = filtered_df['sourcename'].unique()
                source_map = {name: f"AppleHealthPro_Device_{i+1:02d}" for i, name in enumerate(unique_sources)}
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

            for base_name, keys in groups.items():
                pattern = '|'.join(keys)
                subset = filtered_df[filtered_df['type'].str.lower().str.contains(pattern, na=False)]
                if not subset.empty:
                    if 'Reproductive' in base_name:
                        subset.loc[:, 'value'] = subset['value'].str.replace('HKCategoryValueVaginalBleeding', '', regex=False)
                    row_count = len(subset)
                    if row_count > self.CHUNK_SIZE:
                        num_parts = math.ceil(row_count / self.CHUNK_SIZE)
                        self.log_sig.emit(f"<span style='color: #F59E0B;'>[SPLIT]</span> {base_name} ({row_count} rows) -> {num_parts} parts.")
                        for i in range(num_parts):
                            chunk = subset.iloc[i*self.CHUNK_SIZE : (i+1)*self.CHUNK_SIZE]
                            chunk_file = os.path.join(out_dir, f"{base_name}_Part{i+1}.csv")
                            chunk.to_csv(chunk_file, index=False, encoding='utf-8-sig')
                    else:
                        file_path = os.path.join(out_dir, f"{base_name}.csv")
                        subset.to_csv(file_path, index=False, encoding='utf-8-sig')
                        self.log_sig.emit(f"<span style='color: #10B981;'>[SUCCESS]</span> Saved {base_name}.csv")
                else:
                    self.log_sig.emit(f"<span style='color: #86868B;'>[SKIP]</span> {base_name} (No records)")
            self.log_sig.emit(f"<br><span style='color: #10B981;'>[COMPLETE]</span> Operations finished successfully.")
            self.log_sig.emit(f"<span style='color: #86868B;'>Out Dir: {out_dir}</span>")
            self.done_sig.emit()
        except Exception as e: self.log_sig.emit(f"<span style='color: #EF4444;'>[ERROR]</span> Export failed: {str(e)}")

# ==========================================
# 2. Studio-Grade UI
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.is_dark = False
        self.setWindowTitle("Apple Health Pro")
        self.setMinimumSize(950, 600) 
        self.resize(1050, 650)         
        
        self.init_ui()
        self.update_theme()
        
        self.monitor_thread = ResourceMonitorThread()
        self.monitor_thread.update_sig.connect(self.update_hud)
        self.monitor_thread.start()

    def update_hud(self, cpu, ram):
        self.lbl_monitor.setText(f"CPU: {cpu:.1f}%  |  RAM: {ram:.1f} MB")

    # 🟢 状态灯控制中心
    def update_status(self, state):
        if state == "IDLE":
            self.lbl_status.setText("● IDLE")
            self.lbl_status.setStyleSheet("color: #86868B; font-weight: 800; letter-spacing: 1px;")
        elif state == "INDEXING":
            self.lbl_status.setText("● INDEXING DATA...")
            self.lbl_status.setStyleSheet("color: #F59E0B; font-weight: 800; letter-spacing: 1px;") 
        elif state == "EXTRACTING":
            self.lbl_status.setText("● EXTRACTING CSV...")
            self.lbl_status.setStyleSheet("color: #3B82F6; font-weight: 800; letter-spacing: 1px;") 
        elif state == "COMPLETED":
            self.lbl_status.setText("● COMPLETED")
            self.lbl_status.setStyleSheet("color: #10B981; font-weight: 800; letter-spacing: 1px;") 

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.layout = QVBoxLayout(main_widget)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(25)

        # ====== 顶部区域重构 ======
        header_row = QHBoxLayout()
        title_vbox = QVBoxLayout()
        self.title_lbl = QLabel("Apple Health Pro")
        self.sub_title = QLabel("UNLOCK YOUR HEALTH DATA")
        title_vbox.addWidget(self.title_lbl)
        title_vbox.addWidget(self.sub_title)
        title_vbox.setSpacing(2)
        header_row.addLayout(title_vbox)
        
        header_row.addSpacing(30)
        
        # 🟢 专业级状态指示灯
        self.lbl_status = QLabel("● IDLE")
        self.lbl_status.setObjectName("status_led")
        self.lbl_status.setStyleSheet("color: #86868B; font-weight: 800; letter-spacing: 1px;")
        header_row.addWidget(self.lbl_status)
        
        header_row.addStretch()
        
        # 极其克制的 HUD 监视器 (纯文本)
        self.lbl_monitor = QLabel("CPU: --%  |  RAM: -- MB")
        self.lbl_monitor.setObjectName("hud_lbl")
        self.lbl_monitor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_row.addWidget(self.lbl_monitor)
        header_row.addSpacing(20)
        
        # 专业的 Theme 按钮
        self.btn_theme = QPushButton("Theme")
        self.btn_theme.setFixedSize(80, 36)
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.clicked.connect(self.switch_theme)
        header_row.addWidget(self.btn_theme)
        self.layout.addLayout(header_row)

        # ====== 核心分屏布局 ======
        self.split_layout = QHBoxLayout()
        self.split_layout.setSpacing(30)
        self.layout.addLayout(self.split_layout, stretch=1)

        # 🟢 左侧面板
        self.left_col = QVBoxLayout()
        self.left_col.setContentsMargins(0, 0, 0, 25) 
        self.left_col.setSpacing(20)
        self.split_layout.addLayout(self.left_col, stretch=1)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("System standing by...")
        self.left_col.addWidget(self.log_view, stretch=1)

        self.btn_select = QPushButton("SELECT DATA ARCHIVE (.ZIP)")
        self.btn_select.setObjectName("main_action")
        self.btn_select.setFixedHeight(65)
        self.btn_select.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_select.clicked.connect(self.on_select_file)
        self.left_col.addWidget(self.btn_select)

        # 🟢 右侧面板
        self.source_panel = QFrame()
        self.source_panel.setObjectName("main_card")
        self.source_panel.setVisible(False)
        self.split_layout.addWidget(self.source_panel, stretch=1)
        
        self.source_layout = QVBoxLayout(self.source_panel)
        self.source_layout.setContentsMargins(25, 25, 25, 25) 
        self.source_layout.setSpacing(20)
        
        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(25)
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(10)
        self.shadow.setColor(QColor(0, 0, 0, 25))
        self.source_panel.setGraphicsEffect(self.shadow)
        
        # 分区 1
        self.group_sources = QFrame()
        self.group_sources.setObjectName("sub_section")
        vbox_sources = QVBoxLayout(self.group_sources)
        vbox_sources.setContentsMargins(15, 15, 15, 15)
        
        ctrl_layout = QHBoxLayout()
        self.lbl_id = QLabel("IDENTIFIED SOURCES")
        self.lbl_id.setObjectName("section_title")
        ctrl_layout.addWidget(self.lbl_id)
        ctrl_layout.addStretch()
        self.btn_all = QPushButton("Select All"); self.btn_all.setObjectName("tool_btn")
        self.btn_none = QPushButton("Deselect All"); self.btn_none.setObjectName("tool_btn")
        self.btn_all.clicked.connect(lambda: self.toggle_all(True))
        self.btn_none.clicked.connect(lambda: self.toggle_all(False))
        ctrl_layout.addWidget(self.btn_all); ctrl_layout.addWidget(self.btn_none)
        vbox_sources.addLayout(ctrl_layout)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.viewport().setAutoFillBackground(False)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(4)
        self.scroll.setWidget(self.scroll_content)
        vbox_sources.addWidget(self.scroll)
        self.source_layout.addWidget(self.group_sources, stretch=1)
        
        # 分区 2 
        self.group_settings = QFrame()
        self.group_settings.setObjectName("sub_section")
        vbox_settings = QVBoxLayout(self.group_settings)
        vbox_settings.setContentsMargins(15, 15, 15, 15)
        vbox_settings.setSpacing(15)
        
        lbl_settings = QLabel("EXPORT SETTINGS")
        lbl_settings.setObjectName("section_title")
        vbox_settings.addWidget(lbl_settings)

        date_row = QHBoxLayout()
        self.lbl_date = QLabel("Date Range:")
        self.lbl_date.setObjectName("setting_label")
        
        self.date_start = QDateEdit()
        self.date_start.setDisplayFormat("yyyy/MM/dd")
        self.date_start.setDate(QDate(2014, 9, 1))
        self.date_start.setCursor(Qt.CursorShape.IBeamCursor)
        self.date_start.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_to = QLabel("→")
        self.lbl_to.setObjectName("to_badge")
        self.lbl_to.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.date_end = QDateEdit()
        self.date_end.setDisplayFormat("yyyy/MM/dd")
        self.date_end.setDate(QDate.currentDate())
        self.date_end.setCursor(Qt.CursorShape.IBeamCursor)
        self.date_end.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        date_row.addWidget(self.lbl_date)
        date_row.addWidget(self.date_start)
        date_row.addWidget(self.lbl_to)
        date_row.addWidget(self.date_end)
        date_row.addStretch()
        vbox_settings.addLayout(date_row)
        
        # 专业的无 Emoji 文本
        self.cb_privacy = QCheckBox("Mask Device Names / 隐藏设备名 ")
        self.cb_privacy.setChecked(False)
        self.cb_privacy.setCursor(Qt.CursorShape.PointingHandCursor)
        vbox_settings.addWidget(self.cb_privacy)
        
        self.source_layout.addWidget(self.group_settings)
        
        self.btn_export = QPushButton("EXECUTE EXPORT")
        self.btn_export.setObjectName("main_action")
        self.btn_export.setFixedHeight(65)
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.clicked.connect(self.on_export)
        self.source_layout.addWidget(self.btn_export)
        
        self.checkboxes = []

    def switch_theme(self):
        self.is_dark = not self.is_dark
        self.shadow.setColor(QColor(0, 0, 0, 50 if self.is_dark else 25))
        self.update_theme()

    def update_theme(self):
        accent_color = "#9B2C2C" 
        accent_trans = "rgba(155, 44, 44, 0.12)"
        
        if not self.is_dark:
            bg_color = "#F5F5F7"
            card_color = "#FFFFFF"
            sub_card_color = "#F9F9FB" 
            text_primary = "#1D1D1F"
            text_secondary = "#86868B"
            border_color = "#E5E5EA"
            log_bg = "#FFFFFF"
            hud_bg = "#E8E8ED"
            btn_text = "#FFFFFF"
            tool_btn_hover = "rgba(0, 0, 0, 0.04)"
        else:
            bg_color = "#000000"
            card_color = "#1C1C1E"
            sub_card_color = "#242426" 
            text_primary = "#F5F5F7"
            text_secondary = "#86868B"
            border_color = "#38383A"
            log_bg = "#1C1C1E"
            hud_bg = "#2C2C2E"
            btn_text = "#FFFFFF"
            tool_btn_hover = "rgba(255, 255, 255, 0.05)"
        
        tick_b64 = "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIwIDYgOSAxNyA0IDEyIj48L3BvbHlsaW5lPjwvc3ZnPg=="

        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {bg_color}; }}
            
            LABEL {{ color: {text_primary}; font-family: -apple-system, "SF Pro Text", sans-serif; font-weight: 500; }}
            QLabel#section_title {{ color: {text_secondary}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
            QLabel#setting_label {{ color: {text_primary}; font-size: 13px; font-weight: 600; }}
            QLabel#status_led {{ font-family: -apple-system, "SF Pro Text", sans-serif; }}
            
            QLabel#to_badge {{
                color: {text_secondary}; font-weight: 900; font-size: 16px;
                background-color: transparent; margin: 0px 8px;
            }}
            
            QLabel#hud_lbl {{ 
                background-color: {hud_bg}; color: {text_secondary}; 
                border-radius: 18px; padding: 0px 20px; 
                font-family: ui-monospace, "SF Mono", "Consolas", monospace; font-size: 12px; font-weight: 600;
            }}
            
            /* 专业的等宽字体日志台，减小字号，增加极客感 */
            QTextEdit {{ 
                background-color: {log_bg}; border-radius: 16px; padding: 18px; 
                border: 1px solid {border_color}; color: {text_primary}; 
                font-family: ui-monospace, "SF Mono", "Consolas", monospace; 
                font-size: 11px; line-height: 1.4;
            }}
            
            QPushButton {{ 
                background-color: transparent; color: {text_primary}; 
                border: 1px solid {border_color}; border-radius: 10px; font-weight: 600; font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {tool_btn_hover}; }}

            QPushButton#tool_btn {{ border: none; font-size: 13px; color: {accent_color}; padding: 6px 12px; }}
            QPushButton#tool_btn:hover {{ background-color: {tool_btn_hover}; border-radius: 6px; }}

            QPushButton#main_action {{ 
                background-color: {accent_color}; color: {btn_text}; 
                border: none; border-radius: 14px; font-weight: 700; font-size: 15px; letter-spacing: 0.5px;
            }}
            QPushButton#main_action:hover {{ background-color: #7A2323; }}
            QPushButton#main_action:disabled {{ background-color: {border_color}; color: {text_secondary}; }}
            
            QFrame#main_card {{ background-color: {card_color}; border-radius: 24px; border: 1px solid {border_color}; }}
            QFrame#sub_section {{ background-color: {sub_card_color}; border-radius: 16px; border: 1px solid {border_color}; }}
            
            QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{
                background-color: transparent; border: none;
            }}
            
            QCheckBox {{ 
                spacing: 10px; font-size: 13px; color: {text_primary}; 
                font-weight: 600; padding: 6px; border-radius: 8px;
                background-color: transparent; border: none; outline: none;
            }}
            QCheckBox:hover {{ background-color: {tool_btn_hover}; }}
            QCheckBox::indicator {{ 
                width: 20px; height: 20px; border-radius: 6px; 
                border: 1.5px solid {border_color}; background-color: {card_color}; 
            }}
            QCheckBox::indicator:checked {{ 
                background-color: {accent_color}; border-color: {accent_color};
                image: url("data:image/svg+xml;base64,{tick_b64}");
            }}
            
            /* 极简纯文本化的 DateEdit */
            QDateEdit {{
                background-color: {accent_trans}; color: {accent_color};
                border: 1px solid transparent; border-radius: 8px;
                min-width: 110px; padding: 6px 16px; 
                font-size: 13px; font-weight: 700;
            }}
            QDateEdit:focus {{
                border: 1px solid {accent_color}; background-color: transparent;
            }}
            QDateEdit::drop-down, QDateEdit::up-button, QDateEdit::down-button {{ 
                width: 0px; border: none; background: transparent; 
            }}
            
            QScrollBar:vertical {{ border: none; background: transparent; width: 6px; }}
            QScrollBar::handle:vertical {{ background: {border_color}; border-radius: 3px; min-height: 20px; }}
        """)
        self.title_lbl.setStyleSheet(f"font-size: 30px; font-weight: 800; color: {accent_color}; letter-spacing: -1px;")
        self.sub_title.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {text_secondary}; letter-spacing: 1.5px;")

    def on_select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "CHOOSE ZIP", "", "ZIP Archive (*.zip)")
        if path:
            self.update_status("INDEXING")
            self.log_view.clear(); self.source_panel.setVisible(False)
            self.btn_select.setEnabled(False)
            self.worker = ParseThread(path)
            # 使用 append，Qt会自动解析HTML代码并着色
            self.worker.log_sig.connect(self.log_view.append)
            self.worker.err_sig.connect(lambda e: QMessageBox.critical(self, "ERROR", e))
            self.worker.done_sig.connect(self.on_parse_done); self.worker.start()

    def on_parse_done(self, df, sources, zip_path, min_date, max_date):
        self.update_status("IDLE")
        self.df, self.zip_path = df, zip_path
        self.btn_select.setEnabled(True)
        for i in reversed(range(self.scroll_layout.count())): 
            item = self.scroll_layout.itemAt(i).widget()
            if item: item.deleteLater()
        self.checkboxes = []
        for s in sources:
            cb = QCheckBox(s)
            cb.setChecked(False); cb.setCursor(Qt.CursorShape.PointingHandCursor)
            self.scroll_layout.addWidget(cb)
            self.checkboxes.append(cb)
        self.scroll_layout.addStretch()
        
        self.date_start.setDate(QDate.fromString(min_date, "yyyy-MM-dd"))
        self.date_end.setDate(QDate.fromString(max_date, "yyyy-MM-dd"))
        
        self.source_panel.setVisible(True)

    def toggle_all(self, state):
        for cb in self.checkboxes: cb.setChecked(state)

    def on_export(self):
        selected = [cb.text() for cb in self.checkboxes if cb.isChecked()]
        if not selected: 
            QMessageBox.warning(self, "NO SOURCES", "Please select at least one data source.")
            return
            
        start_str = self.date_start.date().toString("yyyy-MM-dd")
        end_str = self.date_end.date().toString("yyyy-MM-dd")
        
        if start_str > end_str:
            QMessageBox.warning(self, "INVALID DATE", "Start date cannot be after end date.")
            return

        self.update_status("EXTRACTING")
        self.btn_export.setEnabled(False)
        self.exporter = ExportThread(self.df, selected, self.zip_path, start_str, end_str, self.cb_privacy.isChecked())
        self.exporter.log_sig.connect(self.log_view.append)
        
        def on_complete():
            self.btn_export.setEnabled(True)
            self.update_status("COMPLETED")
            
        self.exporter.done_sig.connect(on_complete)
        self.exporter.start()
        
    def closeEvent(self, event):
        self.monitor_thread.stop()
        self.monitor_thread.wait()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    win = MainWindow(); win.show()
    sys.exit(app.exec())