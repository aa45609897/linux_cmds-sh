import sys
import paramiko
import threading
import json
import os
import time
import traceback
import ctypes
from ctypes import wintypes
from PyQt6.QtWidgets import (
    QApplication, QLabel, QWidget, QSystemTrayIcon, QMenu, 
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QDoubleSpinBox, 
    QPushButton, QMessageBox, QSpinBox, QComboBox, QColorDialog, QSlider
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QPen

# ------------------- Windows API 定义 -------------------
user32 = ctypes.windll.user32

# 规范化 64位 下的 API 函数签名，防止指针截断导致 API 调用失败
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = wintypes.LONG
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
user32.SetWindowLongW.restype = wintypes.LONG
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.SetWindowPos.restype = wintypes.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001

# 必须定义为 ctypes 的 HWND 类型
HWND_TOPMOST = wintypes.HWND(-1)
HWND_NOTOPMOST = wintypes.HWND(-2)
SWP_SHOWWINDOW = 0x0040
SWP_NOACTIVATE = 0x0010
WS_EX_NOACTIVATE = 0x08000000

# ------------------- 配置文件管理 -------------------
def get_config_path():
    config_dir = os.path.expanduser("~/feng1_config")
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "gpu_overlay_config.json")

CONFIG_FILE = get_config_path()

DEFAULT_CONFIG = {
    "host": "192.168.10.250",
    "user": "feng1",
    "password": "feng1",
    "interval": 0.5,
    "interaction_key": "Ctrl",
    "color_rules": {
        "danger": 80,
        "warning": 50,
        "temp_danger": 80,
        "temp_warning": 60
    },
    "ui_settings": {
        "font_color": "#00FF00",
        "bg_color": "#000000",
        "bg_opacity": 200
    }
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                def merge(d, default):
                    for key in default:
                        if key not in d: d[key] = default[key]
                        elif isinstance(default[key], dict): merge(d[key], default[key])
                merge(config, DEFAULT_CONFIG)
                return config
        except Exception: return DEFAULT_CONFIG.copy()
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e: print(f"Save config failed: {e}")

# ------------------- 辅助函数：生成图标 -------------------
def create_tray_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(50, 50, 50))
    painter.drawRoundedRect(0, 0, 64, 64, 10, 10)
    pen = QPen(QColor(0, 255, 0), 4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    points = [QPoint(10, 45), QPoint(25, 25), QPoint(40, 40), QPoint(54, 15)]
    for i in range(len(points) - 1): painter.drawLine(points[i], points[i+1])
    painter.end()
    return QIcon(pixmap)

# ------------------- 设置窗口 -------------------
class SettingsDialog(QDialog):
    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置 (保存后重启生效)")
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)
        
        # 1. 连接设置
        grp_conn = QFormLayout()
        self.edit_host = QLineEdit(current_config['host'])
        self.edit_user = QLineEdit(current_config['user'])
        self.edit_pass = QLineEdit(current_config['password'])
        self.edit_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.1, 60.0)
        self.spin_interval.setSingleStep(0.1)
        self.spin_interval.setValue(current_config['interval'])
        grp_conn.addRow("Host IP:", self.edit_host)
        grp_conn.addRow("User:", self.edit_user)
        grp_conn.addRow("Password:", self.edit_pass)
        grp_conn.addRow("刷新间隔:", self.spin_interval)
        layout.addLayout(grp_conn)
        
        # 2. 交互设置
        layout.addSpacing(10)
        grp_interact = QFormLayout()
        self.combo_key = QComboBox()
        self.combo_key.addItems(["Ctrl", "Alt", "Shift"])
        idx = self.combo_key.findText(current_config.get('interaction_key', 'Ctrl'))
        if idx >= 0: self.combo_key.setCurrentIndex(idx)
        grp_interact.addRow("拖动/菜单按键:", self.combo_key)
        layout.addLayout(grp_interact)

        # 3. 颜色阈值
        layout.addSpacing(10)
        grp_color = QFormLayout()
        rules = current_config.get('color_rules', DEFAULT_CONFIG['color_rules'])
        self.spin_warn = QSpinBox(); self.spin_warn.setRange(0, 100); self.spin_warn.setValue(rules.get('warning', 50)); self.spin_warn.setSuffix("%")
        self.spin_danger = QSpinBox(); self.spin_danger.setRange(0, 100); self.spin_danger.setValue(rules.get('danger', 80)); self.spin_danger.setSuffix("%")
        self.spin_temp_warn = QSpinBox(); self.spin_temp_warn.setRange(0, 120); self.spin_temp_warn.setValue(rules.get('temp_warning', 60)); self.spin_temp_warn.setSuffix("°C")
        self.spin_temp_danger = QSpinBox(); self.spin_temp_danger.setRange(0, 120); self.spin_temp_danger.setValue(rules.get('temp_danger', 80)); self.spin_temp_danger.setSuffix("°C")
        grp_color.addRow("利用率 警告(橙):", self.spin_warn)
        grp_color.addRow("利用率 危险(红):", self.spin_danger)
        grp_color.addRow("温度 警告(橙):", self.spin_temp_warn)
        grp_color.addRow("温度 危险(红):", self.spin_temp_danger)
        layout.addLayout(grp_color)

        # 4. 外观设置
        layout.addSpacing(10)
        grp_ui = QFormLayout()
        ui_settings = current_config.get('ui_settings', DEFAULT_CONFIG['ui_settings'])
        
        self.font_color = ui_settings.get('font_color', '#00FF00')
        self.btn_font_color = QPushButton("选择颜色")
        self.btn_font_color.setStyleSheet(f"background-color: {self.font_color}; color: white;")
        self.btn_font_color.clicked.connect(self.pick_font_color)
        grp_ui.addRow("字体颜色:", self.btn_font_color)
        
        self.bg_color = ui_settings.get('bg_color', '#000000')
        self.btn_bg_color = QPushButton("选择颜色")
        self.btn_bg_color.setStyleSheet(f"background-color: {self.bg_color}; color: white;")
        self.btn_bg_color.clicked.connect(self.pick_bg_color)
        grp_ui.addRow("背景颜色:", self.btn_bg_color)
        
        self.slide_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slide_opacity.setRange(0, 255)
        self.slide_opacity.setValue(int(ui_settings.get('bg_opacity', 200)))
        self.lbl_opacity_val = QLabel(str(self.slide_opacity.value()))
        self.slide_opacity.valueChanged.connect(lambda v: self.lbl_opacity_val.setText(str(v)))
        
        hbox_op = QHBoxLayout()
        hbox_op.addWidget(self.slide_opacity)
        hbox_op.addWidget(self.lbl_opacity_val)
        grp_ui.addRow("背景透明度:", hbox_op)
        layout.addLayout(grp_ui)

        btn_box = QHBoxLayout()
        btn_save = QPushButton("保存设置")
        btn_cancel = QPushButton("取消")
        btn_save.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addStretch()
        btn_box.addWidget(btn_save)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

    def pick_font_color(self):
        color = QColorDialog.getColor(QColor(self.font_color), self, "选择字体颜色")
        if color.isValid():
            self.font_color = color.name()
            self.btn_font_color.setStyleSheet(f"background-color: {self.font_color}; color: white;")

    def pick_bg_color(self):
        color = QColorDialog.getColor(QColor(self.bg_color), self, "选择背景颜色")
        if color.isValid():
            self.bg_color = color.name()
            self.btn_bg_color.setStyleSheet(f"background-color: {self.bg_color}; color: white;")

    def get_config(self):
        return {
            "host": self.edit_host.text().strip(),
            "user": self.edit_user.text().strip(),
            "password": self.edit_pass.text(),
            "interval": self.spin_interval.value(),
            "interaction_key": self.combo_key.currentText(),
            "color_rules": {
                "warning": self.spin_warn.value(),
                "danger": self.spin_danger.value(),
                "temp_warning": self.spin_temp_warn.value(),
                "temp_danger": self.spin_temp_danger.value()
            },
            "ui_settings": {
                "font_color": self.font_color,
                "bg_color": self.bg_color,
                "bg_opacity": self.slide_opacity.value()
            }
        }

# ------------------- SSH 后台线程 -------------------
class SSHWorker(QObject):
    update_signal = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.running = True
        self.client = None
        self.config = config

    def update_config(self, new_config):
        if (self.config['host'] != new_config['host'] or 
            self.config['user'] != new_config['user'] or 
            self.config['password'] != new_config['password']):
            if self.client:
                try: self.client.close()
                except: pass
                self.client = None
        self.config = new_config

    def connect_ssh(self):
        if self.client is None:
            try:
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.client.connect(self.config['host'], username=self.config['user'], password=self.config['password'], timeout=5)
            except Exception as e:
                self.update_signal.emit(f"Connection Failed: {e}")
                self.client = None
                return False
        return True

    def run(self):
        while self.running:
            if self.client is None: self.connect_ssh()
            if self.client:
                try:
                    cmd = "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader"
                    # 必须加 timeout，否则网络假死会永久卡住 UI 更新
                    stdin, stdout, stderr = self.client.exec_command(cmd, timeout=5)
                    out = stdout.read().decode().strip()
                    lines = out.split("\n")
                    text_lines = []
                    rules = self.config.get('color_rules', {})
                    
                    ui = self.config.get('ui_settings', {})
                    default_font_color = ui.get('font_color', '#00FF00')
                    
                    for idx, line in enumerate(lines):
                        try:
                            parts = [x.strip() for x in line.split(",")]
                            if len(parts) < 5: continue
                            name, util, mem_used, mem_total, temp = parts
                            util_val = int(util.replace("%",""))
                            mem_used_val = int(mem_used.split()[0])
                            mem_total_val = int(mem_total.split()[0])
                            mem_percent = mem_used_val / mem_total_val * 100 if mem_total_val else 0
                            temp_val = int(temp)

                            color = default_font_color
                            if util_val > rules.get('danger', 80) or mem_percent > rules.get('danger', 80) or temp_val > rules.get('temp_danger', 80): color = "red"
                            elif util_val > rules.get('warning', 50) or mem_percent > rules.get('warning', 50) or temp_val > rules.get('temp_warning', 60): color = "orange"

                            text_lines.append(f'<span style="color:{color}; white-space: nowrap">GPU{idx}: {name} | {util} | {mem_used}/{mem_total} | {temp}°C</span>')
                        except Exception: text_lines.append(f"GPU{idx}: Parse Error")
                    self.update_signal.emit("<br>".join(text_lines))
                except Exception:
                    if self.client: 
                        try: self.client.close() 
                        except: pass
                        self.client = None
                    self.update_signal.emit("Connection Lost...")
            else:
                self.update_signal.emit("Waiting for connection...")
            time.sleep(self.config.get('interval', 1.0))

    def stop(self):
        self.running = False
        if self.client: self.client.close()

# ------------------- PyQt Overlay -------------------
class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.apply_ui_settings()
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label.adjustSize()
        self.old_pos = QPoint()

        self.worker = SSHWorker(self.config)
        self.worker.update_signal.connect(self.update_text)
        self.thread = threading.Thread(target=self.worker.run, daemon=True)
        self.thread.start()

        self.key_codes = {"Ctrl": 0x11, "Shift": 0x10, "Alt": 0x12}
        self.is_interactive = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_interaction_state)
        self.timer.start(20)

        # 加快保活频率至 500ms，压过任务栏的自刷频率
        self.topmost_timer = QTimer(self)
        self.topmost_timer.timeout.connect(self.force_topmost)
        self.topmost_timer.start(500)

        self.tray_icon = QSystemTrayIcon(create_tray_icon(), self)
        tray_menu = QMenu(self)
        tray_menu.addAction("显示窗口").triggered.connect(self.show_overlay)
        tray_menu.addAction("隐藏窗口").triggered.connect(self.hide_overlay)
        tray_menu.addAction("修改设置").triggered.connect(self.open_settings)
        tray_menu.addAction("退出程序").triggered.connect(self.quit_app)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setToolTip("Remote NVIDIA GPU Overlay")
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

        self.show()
        QTimer.singleShot(100, lambda: self.set_penetration(True))

    def apply_ui_settings(self):
        ui = self.config.get('ui_settings', DEFAULT_CONFIG['ui_settings'])
        bg_c = QColor(ui.get('bg_color', '#000000'))
        opacity = ui.get('bg_opacity', 200)
        bg_rgba = f"rgba({bg_c.red()}, {bg_c.green()}, {bg_c.blue()}, {opacity})"
        
        self.label = QLabel("Connecting...", self)
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setWordWrap(False)
        self.label.setStyleSheet(f"""
            QLabel {{
                background: {bg_rgba};
                padding: 10px;
                font-family: Consolas;
                font-size: 13px;
                border-radius: 5px;
            }}
        """)

    def update_interaction_state(self):
        key_name = self.config.get('interaction_key', 'Ctrl')
        vk_code = self.key_codes.get(key_name, 0x11)
        key_pressed = (user32.GetAsyncKeyState(vk_code) & 0x8000) != 0

        if key_pressed:
            if not self.is_interactive:
                self.set_penetration(False)
                self.is_interactive = True
                self.raise_()
        else:
            if self.is_interactive:
                self.set_penetration(True)
                self.is_interactive = False

    def set_penetration(self, enabled):
        # 关键修复：使用 int() 转换 winId()，解决 sip.voidptr 无法传递给 ctypes 的问题
        hwnd = int(self.winId())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        
        if enabled:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)
            self.unsetCursor()
        else:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, (style | WS_EX_LAYERED) & ~WS_EX_TRANSPARENT)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_FRAMECHANGED | SWP_NOACTIVATE | SWP_SHOWWINDOW)

    def force_topmost(self):
        if not self.isVisible(): return
        # 关键修复：使用 int() 转换 winId()
        hwnd = int(self.winId())
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(50, self.force_topmost)

    def open_settings(self):
        self.set_penetration(False)
        self.is_interactive = True 
        
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            self.config = dialog.get_config()
            save_config(self.config)
            self.worker.update_config(self.config)
            self.tray_icon.showMessage("已保存", "配置已保存，部分设置需重启生效。", QSystemTrayIcon.MessageIcon.Information, 3000)
        
        self.is_interactive = False
        self.update_interaction_state()

    def show_overlay(self): self.show()
    def hide_overlay(self): self.hide()
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible(): self.hide()
            else: self.show()

    def update_text(self, text):
        self.label.setText(text)
        self.label.adjustSize()
        self.resize(self.label.size())
        # 每次更新文本时顺便强制置顶一次
        self.force_topmost()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.old_pos
            self.move(new_pos)

    def mouseReleaseEvent(self, event):
        if self.is_interactive:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("隐藏窗口").triggered.connect(self.hide_overlay)
        menu.addAction("修改设置").triggered.connect(self.open_settings)
        menu.addAction("退出程序").triggered.connect(self.quit_app)
        menu.exec(event.globalPos())

    def quit_app(self):
        self.timer.stop()
        self.topmost_timer.stop()
        self.worker.stop()
        self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event):
        self.quit_app()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = Overlay()
    sys.exit(app.exec())