import sys, os, json, base64, ctypes, time
import pyotp

from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton,
    QLineEdit, QTextEdit, QHBoxLayout, QLabel, QMenu, QListWidget, QDialog,
    QColorDialog, QCheckBox, QMessageBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, Qt, QPoint, QTimer
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QPen, QColor, QFont


# -------------------------
# Constants
# -------------------------
DEFAULT_SETTINGS = {
    "gui_color": "#000000",
    "bg_color": "#000000",
    "text_color": "#ffffff",
    "custom_colors": False
}


def request_admin():
    if ctypes.windll.shell32.IsUserAnAdmin():
        return
    ctypes.windll.shell32.ShellExecuteW(
        None, 'runas', sys.executable, ' ' + ' '.join(sys.argv), None, 1
    )
    sys.exit(0)


def minimize_console():
    try:
        import win32gui, win32con
        hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    except Exception:
        pass


request_admin()
minimize_console()


# -------------------------
# Helper Widgets
# -------------------------
class CircleProgress(QWidget):
    """Circular countdown progress bar with seconds inside."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.progress = 1.0
        self.seconds_left = 30
        self.setFixedSize(80, 80)

    def set_progress(self, ratio: float, seconds: int):
        self.progress = max(0.0, min(1.0, ratio))
        self.seconds_left = max(0, seconds)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(5, 5, -5, -5)
        start_angle = 90 * 16
        span_angle = -int(360 * 16 * self.progress)

        # background circle
        pen = QPen(QColor("#3a3a3a"), 6)
        painter.setPen(pen)
        painter.drawEllipse(rect)

        # progress arc
        pen.setColor(QColor("#00ccff"))
        painter.setPen(pen)
        painter.drawArc(rect, start_angle, span_angle)

        # seconds text
        painter.setPen(QColor("#ffffff"))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        text = f"{self.seconds_left}s"
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)


class ToastNotification(QLabel):
    """Simple fading toast notification."""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            background-color: rgba(0,0,0,200);
            color: white;
            padding: 6px 12px;
            border-radius: 6px;
        """)
        self.setWindowFlags(Qt.WindowType.ToolTip)
        self.adjustSize()
        QTimer.singleShot(2000, self.close)  # auto-close after 2s


# -------------------------
# Popups
# -------------------------
class ToolsPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tools")
        self.setGeometry(300, 300, 450, 400)
        self.parent = parent

        layout = QVBoxLayout()

        # TOTP input
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Enter authenticator secret key")
        layout.addWidget(self.key_input)

        self.generate_btn = QPushButton("Generate Code")
        self.generate_btn.clicked.connect(self.start_totp)
        layout.addWidget(self.generate_btn)

        self.code_label = QLabel("Code will appear here")
        self.code_label.setStyleSheet("font-size: 22px; font-weight: bold;")
        self.code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.code_label)

        self.progress = CircleProgress()
        layout.addWidget(self.progress, alignment=Qt.AlignmentFlag.AlignCenter)

        # JavaScript injection
        layout.addWidget(QLabel("Inject JavaScript into current page:"))
        self.js_input = QTextEdit()
        self.js_input.setPlaceholderText("Enter JavaScript code here...")
        layout.addWidget(self.js_input)

        self.inject_btn = QPushButton("Inject JavaScript")
        self.inject_btn.clicked.connect(self.inject_js)
        layout.addWidget(self.inject_btn)

        self.setLayout(layout)

        self.secret = None
        self.totp = None
        self.remaining = 30
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)

        self.code_label.mousePressEvent = self.copy_code

    # TOTP functions
    def start_totp(self):
        secret = self.key_input.text().strip()
        if not secret:
            self.code_label.setText("Enter a secret key first")
            return
        try:
            self.secret = secret
            self.totp = pyotp.TOTP(secret)
            self.refresh_code()
            self.timer.start(1000)
        except Exception:
            self.code_label.setText("Invalid key")

    def refresh_code(self):
        if not self.totp:
            return
        code = self.totp.now()
        self.code_label.setText(f"{code}")
        now = int(time.time())
        self.remaining = 30 - (now % 30)
        self.progress.set_progress(1.0, self.remaining)
        QTimer.singleShot(self.remaining * 1000, self.refresh_code)

    def update_progress(self):
        if not self.totp:
            return
        self.remaining -= 1
        if self.remaining < 0:
            self.remaining = 0
        ratio = self.remaining / 30.0
        self.progress.set_progress(ratio, self.remaining)

    def copy_code(self, event):
        code = self.code_label.text().strip()
        if code and code.isdigit():
            QApplication.clipboard().setText(code)
            toast = ToastNotification("Code copied!", self)
            pos = self.mapToGlobal(self.rect().center())
            toast.move(pos.x() - toast.width() // 2, pos.y() - 80)
            toast.show()

    # JS injection
    def inject_js(self):
        code = self.js_input.toPlainText().strip()
        if code and self.parent:
            current_browser = self.parent.get_current_browser()
            if current_browser:
                current_browser.page().runJavaScript(code)


# -------------------------
# Browser
# -------------------------
class CustomBrowser(QMainWindow):
    DEFAULT_URL = "https://www.google.com"

    def __init__(self):
        super().__init__()
        self.settings_file = r"C:\PyBrowser\settings.json"
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)

        self.settings = self.load_settings()
        self.profile = QWebEngineProfile("PyBrowserProfile", self)

        self.history = []
        self.old_pos = None

        self.setGeometry(100, 100, 1024, 768)  # resizable now

        self.main_layout = QVBoxLayout()

        # --- Top bar
        self.top_bar = QWidget()
        self.top_bar_layout = QHBoxLayout()
        self.top_bar_layout.setContentsMargins(5, 2, 5, 2)

        self.icon_label = QLabel()
        pixmap = QPixmap("C:\\Program Files\\PyBrowser\\Icon.ico").scaled(15, 15)
        self.icon_label.setPixmap(pixmap)
        self.top_bar_layout.addWidget(self.icon_label)

        self.title_label = QLabel("PyBrowser v2")
        self.title_label.setStyleSheet("font-size: 14px;")
        self.top_bar_layout.addWidget(self.title_label)
        self.top_bar_layout.addStretch()

        self.minimize_button = QPushButton("➖")
        self.minimize_button.clicked.connect(self.showMinimized)
        self.top_bar_layout.addWidget(self.minimize_button)

        self.fullscreen_button = QPushButton("⬜")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.top_bar_layout.addWidget(self.fullscreen_button)

        self.close_button = QPushButton("❌")
        self.close_button.clicked.connect(self.close)
        self.top_bar_layout.addWidget(self.close_button)

        self.top_bar.setLayout(self.top_bar_layout)
        self.main_layout.addWidget(self.top_bar)

        # --- Nav bar
        self.nav_bar = QWidget()
        self.nav_bar_layout = QHBoxLayout()
        self.nav_bar_layout.setContentsMargins(5, 2, 5, 2)

        self.back_button = QPushButton("◀")
        self.back_button.clicked.connect(self.go_back)
        self.forward_button = QPushButton("▶")
        self.forward_button.clicked.connect(self.go_forward)
        self.reload_button = QPushButton("⟳")
        self.reload_button.clicked.connect(self.reload_page)
        self.home_button = QPushButton("🏠")
        self.home_button.clicked.connect(self.go_home)
        for btn in [self.back_button, self.forward_button, self.reload_button, self.home_button]:
            btn.setFixedSize(30, 30)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.load_url)

        self.menu_button = QPushButton("☰")
        self.menu_button.setFixedSize(30, 30)
        self.menu_button.clicked.connect(self.open_menu)

        self.new_tab_button = QPushButton("➕")
        self.new_tab_button.setFixedSize(30, 30)
        self.new_tab_button.clicked.connect(self.add_new_tab)

        self.nav_bar_layout.addWidget(self.back_button)
        self.nav_bar_layout.addWidget(self.forward_button)
        self.nav_bar_layout.addWidget(self.reload_button)
        self.nav_bar_layout.addWidget(self.home_button)
        self.nav_bar_layout.addWidget(self.url_bar)
        self.nav_bar_layout.addWidget(self.new_tab_button)
        self.nav_bar_layout.addWidget(self.menu_button)
        self.nav_bar.setLayout(self.nav_bar_layout)
        self.main_layout.addWidget(self.nav_bar)

        # --- Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_title)
        self.main_layout.addWidget(self.tabs)

        self.main_widget = QWidget()
        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)

        self.apply_gui_color()
        self.add_new_tab()

    # Helpers
    def get_current_browser(self):
        current_widget = self.tabs.currentWidget()
        if current_widget:
            return current_widget.layout().itemAt(0).widget()
        return None

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # Settings
    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    loaded = json.load(f)
                for k, v in DEFAULT_SETTINGS.items():
                    loaded.setdefault(k, v)
                return loaded
            except Exception:
                pass
        return DEFAULT_SETTINGS.copy()

    def save_settings(self):
        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f, indent=2)

    def update_setting(self, key, value):
        self.settings[key] = value
        self.save_settings()
        if key == "gui_color":
            self.apply_gui_color()

    def apply_gui_color(self):
        gui_color = self.settings.get("gui_color", DEFAULT_SETTINGS["gui_color"])
        self.top_bar.setStyleSheet(f"background-color: {gui_color}; color: white; padding: 5px;")
        self.nav_bar.setStyleSheet(f"background-color: {gui_color}; color: white; padding: 5px;")

    # Tabs
    def add_new_tab(self, url=None):
        browser = QWebEngineView()
        page = QWebEnginePage(self.profile, browser)
        browser.setPage(page)
        default_url = QUrl(url) if url else QUrl(self.DEFAULT_URL)
        browser.urlChanged.connect(self.update_url_bar)
        browser.titleChanged.connect(lambda title, b=browser: self.update_tab_title(b, title))
        browser.iconChanged.connect(lambda icon, b=browser: self.update_tab_icon(b, icon))
        browser.loadFinished.connect(lambda ok, b=browser: self.on_page_load(b))

        tab = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(browser)
        tab.setLayout(layout)
        index = self.tabs.addTab(tab, "Loading...")
        self.tabs.setCurrentIndex(index)
        browser.setUrl(default_url)

    def on_page_load(self, browser: QWebEngineView):
        self.inject_custom_colors(browser)

    def inject_custom_colors(self, browser: QWebEngineView):
        if not self.settings.get("custom_colors", False):
            return
        bg = self.settings["bg_color"]
        text = self.settings["text_color"]
        js = f"""
            document.documentElement.style.background = "{bg}";
            document.body.style.background = "{bg}";
            document.documentElement.style.color = "{text}";
            document.body.style.color = "{text}";
        """
        browser.page().runJavaScript(js)

    # Tabs updates
    def update_tab_title(self, browser, title):
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).layout().itemAt(0).widget() == browser:
                self.tabs.setTabText(i, title if title else "New Tab")
                break

    def update_tab_icon(self, browser, icon: QIcon):
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).layout().itemAt(0).widget() == browser:
                self.tabs.setTabIcon(i, icon)
                break

    # Browser actions
    def go_back(self): self.get_current_browser().back()
    def go_forward(self): self.get_current_browser().forward()
    def reload_page(self): self.get_current_browser().reload()
    def go_home(self): self.get_current_browser().setUrl(QUrl(self.DEFAULT_URL))
    def close_tab(self, index): 
        if self.tabs.count() > 1: self.tabs.removeTab(index)
    def load_url(self):
        url = self.url_bar.text().strip()
        if not url.startswith("http"):
            url = "https://" + url
        self.get_current_browser().setUrl(QUrl(url))
        self.history.append(url)
    def update_url_bar(self, url): self.url_bar.setText(url.toString())
    def update_title(self):
        current_widget = self.tabs.currentWidget()
        if current_widget: self.setWindowTitle(self.tabs.tabText(self.tabs.currentIndex()) + " - PyBrowser")

    def open_menu(self):
        menu = QMenu(self)
        history_action = menu.addAction("History")
        settings_action = menu.addAction("Settings")
        tools_action = menu.addAction("Tools")
        history_action.triggered.connect(lambda: None)  # placeholder
        settings_action.triggered.connect(lambda: None)  # placeholder
        tools_action.triggered.connect(self.show_tools)
        menu.exec(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))

    def show_tools(self): self.tools_popup = ToolsPopup(self); self.tools_popup.show()


# -------------------------
# Run app
# -------------------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = CustomBrowser()
    window.show()
    sys.exit(app.exec())
