import sys, os, zipfile, pandas as pd, xml.etree.ElementTree as ET, time, io, math
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QTextEdit, QLabel,
                             QFileDialog, QScrollArea, QCheckBox, QMessageBox, QFrame, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor

# Ensure proper layer rendering for macOS
if sys.platform == 'darwin':
    os.environ["QT_MAC_WANTS_LAYER"] = "1"

# ==========================================
# 1. High-Performance Core Engine
# ==========================================
class ParseThread(QThread):
    log_sig = pyqtSignal(str)
    done_sig = pyqtSignal(object, list, str)
    err_sig = pyqtSignal(str)

    def __init__(self, zip_path):
        super().__init__()
        self.zip_path = zip_path

    def run(self):
        try:
            self.log_sig.emit("🔍 INITIALIZING: Scanning ZIP architecture...")
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                xml_filename = None
                all_files = zip_ref.namelist()
                
                # Fix encoding for non-ASCII filenames inside ZIP
                for name in all_files:
                    try: decoded_name = name.encode('cp437').decode('utf-8')
                    except:
                        try: decoded_name = name.encode('cp437').decode('gbk')
                        except: decoded_name = name

                    base_name = os.path.basename(decoded_name).lower()
                    if base_name in ["export.xml", "导出.xml"]:
                        xml_filename = name 
                        self.log_sig.emit(f"🚀 SOURCE DETECTED: {decoded_name}")
                        break
                
                if not xml_filename:
                    self.err_sig.emit("CRITICAL: 'export.xml' not found in ZIP.")
                    return

                attribute_list = []
                with zip_ref.open(xml_filename) as f:
                    raw_data = f.read().replace(b'\x0b', b'')
                    xml_stream = io.BytesIO(raw_data)
                    context = ET.iterparse(xml_stream, events=('end',))
                    try:
                        event, root = next(context)
                        count = 0
                        for event, elem in context:
                            if elem.tag == 'Record':
                                sn = elem.attrib.get('sourceName')
                                if sn:
                                    attribute_list.append({
                                        'type': elem.attrib.get('type', ''),
                                        'value': elem.attrib.get('value', ''),
                                        'unit': elem.attrib.get('unit', ''),
                                        'startdate': elem.attrib.get('startDate', ''),
                                        'sourcename': sn
                                    })
                                    count += 1
                                    if count % 500000 == 0:
                                        self.log_sig.emit(f"⚡ INDEXING: {count} records synced...")
                                elem.clear()
                                root.clear()
                    except ET.ParseError: pass

            df = pd.DataFrame(attribute_list)
            sources = sorted(df['sourcename'].unique().tolist())
            self.done_sig.emit(df, sources, self.zip_path)
        except Exception as e: self.err_sig.emit(f"SYSTEM ERROR: {str(e)}")

class ExportThread(QThread):
    log_sig = pyqtSignal(str)
    done_sig = pyqtSignal()

    def __init__(self, df, selected_sources, zip_path):
        super().__init__()
        self.df, self.selected_sources, self.zip_path = df, selected_sources, zip_path
        self.CHUNK_SIZE = 800000 # ~90MB split threshold

    def run(self):
        try:
            self.log_sig.emit(f"\n📂 STARTING MULTI-DIMENSIONAL EXPORT...")
            filtered_df = self.df[self.df['sourcename'].isin(self.selected_sources)]
            out_dir = os.path.dirname(self.zip_path)
            
            groups = {
                '1_Heart_Metrics': ['heartrate', 'resting', 'variability'],
                '2_Body_Composition': ['mass', 'bmi', 'fat', 'leanbody'],
                '3_Activity_Energy': ['step', 'energy', 'distance', 'flights'],
                '4_Sleep_Analysis': ['sleep'],
                '5_Mobility_Gait': ['walkingspeed', 'steplength', 'asymmetry', 'support'],
                '6_Reproductive_Health': ['menstrual', 'ovulation', 'cervical'],
                '7_Vitals_Respiratory': ['oxygen', 'respiratory', 'temperature', 'bloodpressure']
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
                        self.log_sig.emit(f"⚠️ SPLITTING: {base_name} is large ({row_count} rows). Creating {num_parts} parts.")
                        for i in range(num_parts):
                            chunk = subset.iloc[i*self.CHUNK_SIZE : (i+1)*self.CHUNK_SIZE]
                            chunk_file = os.path.join(out_dir, f"{base_name}_Part{i+1}.csv")
                            chunk.to_csv(chunk_file, index=False, encoding='utf-8-sig')
                            self.log_sig.emit(f"   ✅ PART SAVED: {os.path.basename(chunk_file)}")
                    else:
                        file_path = os.path.join(out_dir, f"{base_name}.csv")
                        subset.to_csv(file_path, index=False, encoding='utf-8-sig')
                        self.log_sig.emit(f"📌 SAVED: {base_name}.csv")
                else:
                    self.log_sig.emit(f"➖ SKIPPED: {base_name} (No data found)")

            self.log_sig.emit(f"\n🎉 ALL OPERATIONS COMPLETE.\nSaved at: {out_dir}")
            self.done_sig.emit()
        except Exception as e: self.log_sig.emit(f"❌ EXPORT FAILED: {str(e)}")

# ==========================================
# 2. Studio-Grade UI (Cranberry Unified)
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.is_dark = False
        self.setWindowTitle("Apple Health Pro")
        self.setFixedSize(850, 850)
        self.init_ui()
        self.update_theme()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.layout = QVBoxLayout(main_widget)
        self.layout.setContentsMargins(45, 45, 45, 45)
        self.layout.setSpacing(25)

        # Global Header
        header_row = QHBoxLayout()
        title_vbox = QVBoxLayout()
        self.title_lbl = QLabel("Apple Health Pro")
        self.sub_title = QLabel("STUDIO-GRADE DATA ENGINE")
        self.copyright_lbl = QLabel("© 2026 LEEcDiang. All rights reserved.")
        title_vbox.addWidget(self.title_lbl)
        title_vbox.addWidget(self.sub_title)
        header_row.addLayout(title_vbox)
        header_row.addStretch()

        # Theme Toggle
        self.btn_theme = QPushButton("🌓 THEME")
        self.btn_theme.setFixedSize(110, 40)
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.clicked.connect(self.switch_theme)
        header_row.addWidget(self.btn_theme)
        self.layout.addLayout(header_row)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Awaiting system input...")
        self.layout.addWidget(self.log_view, stretch=3)

        self.btn_select = QPushButton("SELECT DATA ARCHIVE (.ZIP)")
        self.btn_select.setObjectName("main_action")
        self.btn_select.setFixedHeight(60)
        self.btn_select.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_select.clicked.connect(self.on_select_file)
        self.layout.addWidget(self.btn_select)

        # Source Panel Card
        self.source_panel = QFrame()
        self.source_panel.setObjectName("card")
        self.source_panel.setVisible(False)
        self.source_layout = QVBoxLayout(self.source_panel)
        self.source_layout.setContentsMargins(30, 30, 30, 30)
        
        # Soft Shadow setup
        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(20)
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(8)
        self.shadow.setColor(QColor(0, 0, 0, 25))
        self.source_panel.setGraphicsEffect(self.shadow)
        
        ctrl_layout = QHBoxLayout()
        self.lbl_id = QLabel("IDENTIFIED SOURCES:")
        ctrl_layout.addWidget(self.lbl_id)
        ctrl_layout.addStretch()
        
        self.btn_all = QPushButton("Select All")
        self.btn_all.setObjectName("tool_btn")
        self.btn_all.clicked.connect(lambda: self.toggle_all(True))
        
        self.btn_none = QPushButton("Deselect All")
        self.btn_none.setObjectName("tool_btn")
        self.btn_none.clicked.connect(lambda: self.toggle_all(False))
        
        ctrl_layout.addWidget(self.btn_all)
        ctrl_layout.addWidget(self.btn_none)
        self.source_layout.addLayout(ctrl_layout)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(8)
        self.scroll.setWidget(self.scroll_content)
        self.source_layout.addWidget(self.scroll)
        
        self.btn_export = QPushButton("EXECUTE EXPORT")
        self.btn_export.setObjectName("main_action")
        self.btn_export.setFixedHeight(60)
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.clicked.connect(self.on_export)
        self.source_layout.addWidget(self.btn_export)
        
        self.layout.addWidget(self.source_panel, stretch=6)
        self.checkboxes = []

    def switch_theme(self):
        self.is_dark = not self.is_dark
        if self.is_dark:
            self.shadow.setColor(QColor(0, 0, 0, 50))
        else:
            self.shadow.setColor(QColor(0, 0, 0, 25))
        self.update_theme()

    def update_theme(self):
        # Master palette logic with Unified Cranberry Buttons
        accent_color = "#9B2C2C" # Cranberry
        if not self.is_dark:
            bg_color = "#F5F5F7"
            card_color = "#FFFFFF"
            text_primary = "#1D1D1F"
            text_secondary = "#86868B"
            border_color = "#D2D2D7"
            log_bg = "#FFFFFF"
            
            # Unified Button Colors - Light Mode
            btn_bg = accent_color
            btn_text = "#FFFFFF"
            btn_hover = "#7A2323" # Darker cranberry for hover
            btn_disabled = "#D1D5DB"
            btn_disabled_text = "#9CA3AF"
            tool_btn_hover = "#F5F5F7"
        else:
            bg_color = "#000000"
            card_color = "#1C1C1E"
            text_primary = "#F5F5F7"
            text_secondary = "#86868B"
            border_color = "#38383A"
            log_bg = "#1C1C1E"
            
            # Unified Button Colors - Dark Mode
            btn_bg = accent_color
            btn_text = "#FFFFFF"
            btn_hover = "#A83030" # Lighter cranberry for hover
            btn_disabled = "#3F3F46"
            btn_disabled_text = "#71717A"
            tool_btn_hover = "#2C2C2E"
        
        # Valid Stroke SVG Checkmark
        tick_b64 = "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIwIDYgOSAxNyA0IDEyIj48L3BvbHlsaW5lPjwvc3ZnPg=="
        
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {bg_color}; }}
            
            LABEL {{ color: {text_primary}; font-family: -apple-system, "SF Pro Text", "PingFang SC", sans-serif; font-weight: 500; }}
            
            QTextEdit {{ 
                background-color: {log_bg}; border-radius: 16px; padding: 18px; 
                border: 1px solid {border_color}; color: {text_primary}; 
                font-family: ui-monospace, "SF Mono", "Menlo", monospace; font-size: 12px; line-height: 1.6;
            }}
            
            /* Theme Toggle Button */
            QPushButton {{ 
                background-color: transparent; color: {text_primary}; 
                border: 1px solid {border_color}; border-radius: 10px; font-weight: 600; font-size: 12px;
            }}
            QPushButton:hover {{ border-color: {text_secondary}; background-color: {tool_btn_hover}; }}

            /* Tool Buttons (Select All / None) */
            QPushButton#tool_btn {{ border: none; font-size: 13px; font-weight: 600; color: {accent_color}; padding: 6px 12px; }}
            QPushButton#tool_btn:hover {{ background-color: {tool_btn_hover}; border-radius: 6px; }}

            /* Main Action Buttons - Unified Cranberry Red */
            QPushButton#main_action {{ 
                background-color: {btn_bg}; color: {btn_text}; 
                border: none; border-radius: 14px; font-weight: 700; font-size: 15px; letter-spacing: 0.5px;
            }}
            QPushButton#main_action:hover {{ background-color: {btn_hover}; }}
            QPushButton#main_action:disabled {{ background-color: {btn_disabled}; color: {btn_disabled_text}; }}
            
            QFrame#card {{ background-color: {card_color}; border-radius: 20px; border: 1px solid {border_color}; }}
            
            /* Checkbox Styling */
            QCheckBox {{ spacing: 12px; font-size: 14px; color: {text_primary}; font-weight: 500; padding: 4px; }}
            QCheckBox:hover {{ background-color: {tool_btn_hover}; border-radius: 8px; }}
            QCheckBox::indicator {{ 
                width: 20px; height: 20px; border-radius: 6px; 
                border: 1.5px solid {border_color}; background-color: transparent; 
            }}
            QCheckBox::indicator:hover {{ border-color: {accent_color}; }}
            QCheckBox::indicator:checked {{ 
                background-color: {accent_color}; border-color: {accent_color};
                image: url("data:image/svg+xml;base64,{tick_b64}");
            }}
            
            /* Minimalist Scrollbar */
            QScrollBar:vertical {{ border: none; background: transparent; width: 6px; margin: 0px 0px 0px 0px; }}
            QScrollBar::handle:vertical {{ background: {border_color}; border-radius: 3px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: {text_secondary}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)
        
        self.title_lbl.setStyleSheet(f"font-size: 34px; font-weight: 800; color: {accent_color}; letter-spacing: -1.5px;")
        self.sub_title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {text_secondary}; letter-spacing: 2px;")
        self.scroll_content.setStyleSheet(f"background-color: {card_color};")
        self.copyright_lbl.setStyleSheet(f"font-size: 10px; font-weight: 500; color: {text_secondary}; margin-top: 2px;")
    def on_select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "CHOOSE ZIP", "", "ZIP Archive (*.zip)")
        if path:
            self.log_view.clear(); self.source_panel.setVisible(False)
            self.btn_select.setEnabled(False)
            self.worker = ParseThread(path)
            self.worker.log_sig.connect(self.log_view.append)
            self.worker.err_sig.connect(lambda e: QMessageBox.critical(self, "SYSTEM ERROR", e))
            self.worker.done_sig.connect(self.on_parse_done); self.worker.start()

    def on_parse_done(self, df, sources, zip_path):
        self.df, self.zip_path = df, zip_path
        self.btn_select.setEnabled(True)
        for i in reversed(range(self.scroll_layout.count())): 
            item = self.scroll_layout.itemAt(i).widget()
            if item: item.deleteLater()
        self.checkboxes = []
        for s in sources:
            cb = QCheckBox(s)
            cb.setChecked(False) # Ensure deselected by default
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            self.scroll_layout.addWidget(cb)
            self.checkboxes.append(cb)
        self.scroll_layout.addStretch(); self.source_panel.setVisible(True)

    def toggle_all(self, state):
        for cb in self.checkboxes: cb.setChecked(state)

    def on_export(self):
        selected = [cb.text() for cb in self.checkboxes if cb.isChecked()]
        if not selected: 
            QMessageBox.warning(self, "NO SOURCES", "Please select at least one data source.")
            return
        self.btn_export.setEnabled(False)
        self.exporter = ExportThread(self.df, selected, self.zip_path)
        self.exporter.log_sig.connect(self.log_view.append)
        self.exporter.done_sig.connect(lambda: self.btn_export.setEnabled(True))
        self.exporter.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    win = MainWindow(); win.show()
    sys.exit(app.exec())