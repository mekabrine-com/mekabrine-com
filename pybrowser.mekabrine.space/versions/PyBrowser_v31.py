import sys, os, json, ctypes
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEnginePage,
    QWebEngineSettings,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton,
    QLineEdit, QHBoxLayout, QLabel, QMenu, QMessageBox, QProgressBar, QTabBar
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, Qt, QTimer
from PyQt6.QtGui import QPixmap, QIcon


# -------------------------
# Defaults / Settings
# -------------------------
DEFAULT_SETTINGS = {
    "gui_color": "#000000",
    "bg_color": "#000000",
    "text_color": "#ffffff",
    "other_bg_color": "#111111",
    "custom_colors": False
}


def request_admin():
    """Request admin privileges if not already elevated."""
    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            return
        ctypes.windll.shell32.ShellExecuteW(
            None, 'runas', sys.executable, ' ' + ' '.join(sys.argv), None, 1
        )
        sys.exit(0)
    except Exception:
        pass


def minimize_console():
    """Minimize console window (Windows only)."""
    try:
        import win32gui, win32con
        hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    except Exception:
        pass


request_admin()
minimize_console()


# -------------------------
# Download Widgets
# -------------------------
class DownloadItemWidget(QWidget):
    def __init__(self, filename: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            QWidget {
                background: rgba(0,0,0,180);
                border-radius: 8px;
            }
            QLabel {
                color: #fff;
                padding: 4px 8px;
            }
            QProgressBar {
                margin: 0 8px 8px 8px;
                height: 12px;
                border: 1px solid rgba(255,255,255,60);
                border-radius: 6px;
                background: rgba(255,255,255,25);
            }
            QProgressBar::chunk {
                background-color: #00ccff;
                border-radius: 6px;
            }
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)

        self.title = QLabel(f"Downloading {filename}", self)
        self.progress_label = QLabel("0 MB / ? MB", self)
        self.bar = QProgressBar(self)
        self.bar.setTextVisible(False)

        self.layout.addWidget(self.title)
        self.layout.addWidget(self.progress_label)
        self.layout.addWidget(self.bar)

        self.setFixedWidth(320)
        self.done = False

    def update_progress(self, received, total):
        if total > 0:
            self.bar.setMaximum(total)
            self.bar.setValue(received)
            mb_recv = received / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self.progress_label.setText(f"{mb_recv:.2f} MB / {mb_total:.2f} MB")
        else:
            self.bar.setMaximum(0)
            self.progress_label.setText(f"{received/1024/1024:.2f} MB / ? MB")

    def finish(self):
        self.done = True
        self.title.setText(self.title.text().replace("Downloading", "Downloaded"))
        self.progress_label.setText("Complete")
        self._shrink_timer = QTimer(self)
        self._shrink_timer.timeout.connect(self.shrink_step)
        self._shrink_timer.start(30)

    def shrink_step(self):
        h = self.height()
        if h <= 5:
            self._shrink_timer.stop()
            self.hide()
            self.setParent(None)
        else:
            self.resize(self.width(), h - 5)


class DownloadsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        self.widgets = []

    def add_download_widget(self, w: DownloadItemWidget):
        self.widgets.append(w)
        self.layout.addWidget(w)
        self.adjustSize()
        self.show()

    def cleanup(self):
        self.widgets = [w for w in self.widgets if not w.isHidden()]
        if not self.widgets:
            self.hide()
        else:
            self.adjustSize()


# -------------------------
# TabBar with Safe Context Menu
# -------------------------
class DragSafeTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self._dragging = False
        self._press_pos = None
        self._drag_threshold = 6

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press_pos = e.pos()
            self._dragging = False
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._press_pos and (e.buttons() & Qt.MouseButton.LeftButton):
            if (e.pos() - self._press_pos).manhattanLength() > self._drag_threshold:
                self._dragging = True
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._press_pos = None
        self._dragging = False
        super().mouseReleaseEvent(e)

    def find_browser_window(self):
        parent = self.parent()
        while parent is not None:
            if parent.__class__.__name__ == "CustomBrowser":
                return parent
            parent = parent.parent()
        return None

    def show_context_menu(self, pos):
        idx = self.tabAt(pos)
        if idx < 0:
            return
        menu = QMenu(self)
        action_refresh = menu.addAction("Refresh Tab")
        action_close = menu.addAction("Close Tab")
        action = menu.exec(self.mapToGlobal(pos))

        browser_window = self.find_browser_window()
        if not browser_window:
            return

        if action == action_refresh:
            browser_window.refresh_tab(idx)
        elif action == action_close:
            browser_window.close_tab(idx)


# -------------------------
# Browser
# -------------------------
class CustomBrowser(QMainWindow):
    DEFAULT_URL = "https://www.google.com"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyBrowser v31")
        self.settings_file = r"C:\PyBrowser\settings.json"
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
        self.settings = self.load_settings()

        self.profile = QWebEngineProfile("PyBrowserProfile", self)
        self.enable_javascript_features()

        self.downloads_dir = r"C:\PyBrowser\Downloads"
        os.makedirs(self.downloads_dir, exist_ok=True)
        self.profile.downloadRequested.connect(self.handle_download)

        self.setGeometry(100, 100, 1024, 768)
        self.main_layout = QVBoxLayout()

        # --- Top Bar
        self.setup_top_bar()

        # --- Navigation Bar
        self.setup_nav_bar()

        # --- Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setTabBar(DragSafeTabBar())
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_title)
        self.main_layout.addWidget(self.tabs)

        self.main_widget = QWidget()
        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)

        self.downloads_panel = DownloadsPanel(self)
        self.downloads_panel.hide()
        self.add_new_tab()

    # --- Enable full JavaScript and plugins ---
    def enable_javascript_features(self):
        settings = self.profile.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)

    # --- Top Bar ---
    def setup_top_bar(self):
        self.top_bar = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)

        icon_label = QLabel()
        try:
            pixmap = QPixmap("C:\\Program Files\\PyBrowser\\Icon.ico").scaled(15, 15)
            icon_label.setPixmap(pixmap)
        except Exception:
            pass
        layout.addWidget(icon_label)

        title_label = QLabel("PyBrowser v31")
        layout.addWidget(title_label)
        layout.addStretch()

        minimize_btn = QPushButton("➖")
        minimize_btn.clicked.connect(self.showMinimized)
        layout.addWidget(minimize_btn)

        fullscreen_btn = QPushButton("⬜")
        fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        layout.addWidget(fullscreen_btn)

        close_btn = QPushButton("❌")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        self.top_bar.setLayout(layout)
        self.main_layout.addWidget(self.top_bar)

    # --- Navigation Bar ---
    def setup_nav_bar(self):
        self.nav_bar = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)

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

        self.new_tab_button = QPushButton("➕")
        self.new_tab_button.setFixedSize(30, 30)
        self.new_tab_button.clicked.connect(self.add_new_tab)

        self.menu_button = QPushButton("☰")
        self.menu_button.setFixedSize(30, 30)
        self.menu_button.clicked.connect(self.open_menu)

        layout.addWidget(self.back_button)
        layout.addWidget(self.forward_button)
        layout.addWidget(self.reload_button)
        layout.addWidget(self.home_button)
        layout.addWidget(self.url_bar)
        layout.addWidget(self.new_tab_button)
        layout.addWidget(self.menu_button)
        self.nav_bar.setLayout(layout)
        self.main_layout.addWidget(self.nav_bar)

    # --- Core Functions ---
    def position_downloads_panel(self):
        if self.downloads_panel and self.downloads_panel.isVisible():
            self.downloads_panel.adjustSize()
            x = self.width() - self.downloads_panel.width() - 12
            y = self.top_bar.height() + 8
            self.downloads_panel.move(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_downloads_panel()

    def load_url(self):
        text = self.url_bar.text().strip()
        if not text:
            return
        shortcuts = {
            "roblox": "https://www.roblox.com",
            "google": "https://www.google.com",
            "gmail": "https://mail.google.com",
            "apple": "https://www.apple.com",
            "youtube": "https://www.youtube.com",
            "chatgpt": "https://chat.openai.com",
        }
        lower = text.lower()
        if lower in shortcuts:
            url = shortcuts[lower]
        elif " " in text or "." not in text:
            url = f"https://www.google.com/search?q={text.replace(' ', '+')}"
        else:
            url = text if text.startswith("http") else "https://" + text
        b = self.get_current_browser()
        if b:
            b.setUrl(QUrl(url))

    # --- Downloads ---
    def handle_download(self, download_item):
        path = os.path.join(self.downloads_dir, download_item.downloadFileName())
        try:
            download_item.setPath(path)
            download_item.accept()
        except Exception:
            return
        w = DownloadItemWidget(download_item.downloadFileName(), parent=self.downloads_panel)
        self.downloads_panel.add_download_widget(w)
        self.position_downloads_panel()

        def update_progress():
            w.update_progress(download_item.receivedBytes(), download_item.totalBytes())
            self.downloads_panel.cleanup()
            self.position_downloads_panel()

        download_item.receivedBytesChanged.connect(update_progress)
        download_item.totalBytesChanged.connect(update_progress)
        download_item.finished.connect(lambda: (w.finish(), QTimer.singleShot(3500, self.downloads_panel.cleanup)))

    # --- Tabs ---
    def add_new_tab(self, url=None):
        b = QWebEngineView()
        p = QWebEnginePage(self.profile, b)
        b.setPage(p)
        b.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        b.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        default_url = QUrl(url) if url else QUrl(self.DEFAULT_URL)
        b.urlChanged.connect(self.update_url_bar)
        b.titleChanged.connect(lambda t, br=b: self.update_tab_title(br, t))
        b.iconChanged.connect(lambda i, br=b: self.update_tab_icon(br, i))
        tab = QWidget()
        l = QVBoxLayout()
        l.addWidget(b)
        tab.setLayout(l)
        idx = self.tabs.addTab(tab, "Loading...")
        self.tabs.setCurrentIndex(idx)
        b.setUrl(default_url)

    def refresh_tab(self, index):
        browser = self.tabs.widget(index).layout().itemAt(0).widget()
        if browser:
            browser.reload()

    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)

    # --- Navigation ---
    def go_back(self):
        b = self.get_current_browser()
        if b: b.back()

    def go_forward(self):
        b = self.get_current_browser()
        if b: b.forward()

    def reload_page(self):
        b = self.get_current_browser()
        if b: b.reload()

    def go_home(self):
        b = self.get_current_browser()
        if b: b.setUrl(QUrl(self.DEFAULT_URL))

    # --- Helpers ---
    def get_current_browser(self):
        cw = self.tabs.currentWidget()
        return cw.layout().itemAt(0).widget() if cw else None

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    return json.load(f)
            except:
                pass
        return DEFAULT_SETTINGS.copy()

    def update_url_bar(self, qurl):
        self.url_bar.setText(qurl.toString())

    def update_title(self):
        current_widget = self.tabs.currentWidget()
        if current_widget:
            self.setWindowTitle(self.tabs.tabText(self.tabs.currentIndex()) + " - PyBrowser")

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

    def open_menu(self):
        menu = QMenu(self)
        downloads_action = menu.addAction("Downloads")
        downloads_action.triggered.connect(lambda: os.startfile(self.downloads_dir))
        menu.exec(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))


# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = CustomBrowser()
    window.show()
    sys.exit(app.exec())
