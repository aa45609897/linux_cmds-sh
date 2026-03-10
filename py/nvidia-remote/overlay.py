import sys
import paramiko
import threading
import json
import os
import time
import traceback
from PyQt6.QtWidgets import (
    QApplication, QLabel, QWidget, QSystemTrayIcon, QMenu, 
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QDoubleSpinBox, 
    QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QPen

# ------------------- 配置文件管理 -------------------
CONFIG_FILE = "~/feng1_config/gpu_overlay_config.json"
CONFIG_FILE = os.path.expanduser(CONFIG_FILE)
os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

DEFAULT_CONFIG = {
    "host": "192.168.10.250",
    "user": "feng1",
    "password": "feng1",
    "interval": 0.1
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 确保所有键都存在
                for key in DEFAULT_CONFIG:
                    if key not in config:
                        config[key] = DEFAULT_CONFIG[key]
                return config
        except Exception:
            print("Config file read error, using default.")
            return DEFAULT_CONFIG.copy()
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Save config failed: {e}")

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
    for i in range(len(points) - 1):
        painter.drawLine(points[i], points[i+1])
    painter.end()
    return QIcon(pixmap)

# ------------------- 设置窗口 -------------------
class SettingsDialog(QDialog):
    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("连接设置")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint) # 去掉问号
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.edit_host = QLineEdit(current_config['host'])
        self.edit_user = QLineEdit(current_config['user'])
        self.edit_pass = QLineEdit(current_config['password'])
        self.edit_pass.setEchoMode(QLineEdit.EchoMode.Password) # 密码掩码
        
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.5, 60.0)
        self.spin_interval.setSingleStep(0.5)
        self.spin_interval.setValue(current_config['interval'])
        
        form.addRow("Host IP:", self.edit_host)
        form.addRow("User:", self.edit_user)
        form.addRow("Password:", self.edit_pass)
        form.addRow("Interval (s):", self.spin_interval)
        
        layout.addLayout(form)
        
        # 按钮
        btn_box = QHBoxLayout()
        btn_save = QPushButton("保存并应用")
        btn_cancel = QPushButton("取消")
        btn_save.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addStretch()
        btn_box.addWidget(btn_save)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

    def get_config(self):
        return {
            "host": self.edit_host.text().strip(),
            "user": self.edit_user.text().strip(),
            "password": self.edit_pass.text(),
            "interval": self.spin_interval.value()
        }

# ------------------- SSH 后台线程 -------------------
class SSHWorker(QObject):
    update_signal = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.running = True
        self.client = None
        self.config = config
        self._config_changed = False

    def update_config(self, new_config):
        """外部调用此方法更新配置"""
        # 如果连接参数变了，标记需要重连
        if (self.config['host'] != new_config['host'] or 
            self.config['user'] != new_config['user'] or 
            self.config['password'] != new_config['password']):
            
            if self.client:
                try: self.client.close()
                except: pass
                self.client = None # 设为None会触发重连逻辑
                print("Connection parameters changed, will reconnect...")
        
        self.config = new_config
        self._config_changed = True

    def connect_ssh(self):
        if self.client is None:
            try:
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.client.connect(
                    self.config['host'], 
                    username=self.config['user'], 
                    password=self.config['password'], 
                    timeout=5
                )
                print("SSH Connected (persistent)")
            except Exception as e:
                self.update_signal.emit(f"Connection Failed: {e}")
                self.client = None
                return False
        return True

    def run(self):
        while self.running:
            # 如果连接断开或未建立，尝试连接
            if self.client is None:
                self.connect_ssh()
            
            if self.client:
                try:
                    cmd = "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader"
                    stdin, stdout, stderr = self.client.exec_command(cmd)
                    out = stdout.read().decode().strip()
                    
                    lines = out.split("\n")
                    text_lines = []
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

                            color = "lime"
                            if util_val > 80 or mem_percent > 80 or temp_val > 80:
                                color = "red"
                            elif util_val > 50 or mem_percent > 50 or temp_val > 60:
                                color = "orange"

                            text_lines.append(f'<span style="color:{color}; white-space: nowrap">GPU{idx}: {name} | {util} | {mem_used}/{mem_total} | {temp}°C</span>')
                        except Exception:
                            text_lines.append(f"GPU{idx}: Parse Error")

                    text = "<br>".join(text_lines)
                    self.update_signal.emit(text)

                except Exception as e:
                    # SSH 连接可能已断开
                    print(f"SSH Error: {e}")
                    if self.client: 
                        try: self.client.close() 
                        except: pass
                        self.client = None
                    self.update_signal.emit("Connection Lost... Retrying")
            else:
                # 连接失败等待重试
                self.update_signal.emit("Waiting for connection...")
                
            # 使用配置中的间隔
            sleep_time = self.config.get('interval', 1.0)
            time.sleep(sleep_time)

    def stop(self):
        self.running = False
        if self.client:
            self.client.close()
            print("SSH Closed")

# ------------------- PyQt Overlay -------------------
class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        # 加载配置
        self.config = load_config()
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool  # 不在任务栏显示
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # UI
        self.label = QLabel("Connecting...", self)
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setWordWrap(False)
        self.label.setStyleSheet("""
            QLabel {
                background: rgba(0,0,0,200);
                padding: 10px;
                font-family: Consolas;
                font-size: 13px;
            }
        """)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label.adjustSize()
        self.old_pos = QPoint()

        # SSH 后台线程
        self.worker = SSHWorker(self.config)
        self.worker.update_signal.connect(self.update_text)
        self.thread = threading.Thread(target=self.worker.run, daemon=True)
        self.thread.start()

        # 系统托盘
        self.tray_icon = QSystemTrayIcon(create_tray_icon(), self)
        tray_menu = QMenu(self)

        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.show_overlay)
        
        hide_action = QAction("隐藏窗口", self)
        hide_action.triggered.connect(self.hide_overlay)
        
        # 新增：设置选项
        settings_action = QAction("修改设置", self)
        settings_action.triggered.connect(self.open_settings)
        
        quit_action = QAction("退出程序", self)
        quit_action.triggered.connect(self.quit_app)

        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addSeparator()
        tray_menu.addAction(settings_action) # 插入设置
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setToolTip("Remote NVIDIA GPU Overlay")
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

        # 默认显示窗口
        self.show()

    def open_settings(self):
        """打开设置窗口"""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            new_config = dialog.get_config()
            self.config = new_config
            save_config(self.config) # 保存到文件
            
            # 通知后台线程更新配置
            self.worker.update_config(new_config)
            
            # 可选：弹出提示
            # self.tray_icon.showMessage("设置已保存", "新配置已应用", QSystemTrayIcon.MessageIcon.Information, 2000)

    def show_overlay(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_overlay(self):
        self.hide()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_overlay()

    def update_text(self, text):
        self.label.setText(text)
        self.label.adjustSize()
        self.resize(self.label.size())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.old_pos
            self.move(new_pos)
            
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        hide_action = menu.addAction("隐藏窗口")
        settings_action = menu.addAction("修改设置")
        quit_action = menu.addAction("退出程序")
        
        action = menu.exec(event.globalPos())
        if action == hide_action:
            self.hide_overlay()
        elif action == settings_action:
            self.open_settings()
        elif action == quit_action:
            self.quit_app()

    def quit_app(self):
        self.worker.stop()
        self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event):
        self.quit_app()

# ------------------- 主程序 -------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = Overlay()
    sys.exit(app.exec())