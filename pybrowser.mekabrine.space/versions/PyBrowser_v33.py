import sys, os, json, ctypes
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEnginePage,
    QWebEngineSettings,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton,
    QLineEdit, QHBoxLayout, QLabel, QMenu, QMessageBox, QProgressBar, QTabBar,
    QComboBox, QDialog, QDialogButtonBox, QColorDialog, QCheckBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import (
    QUrl, Qt, QTimer, QMimeData, QByteArray
)
from PyQt6.QtGui import (
    QIcon, QDrag, QColor
)


# -------------------------
# Defaults / Settings
# -------------------------
DEFAULT_SETTINGS = {
    "gui_color": "#000000",
    "bg_color": "#000000",
    "text_color": "#ffffff",
    "other_bg_color": "#111111",
    "custom_colors": False,
    "search_engine": "google",
    "custom_page_bg_enabled": False,
    "page_bg_color": "#ffffff",
}


SEARCH_ENGINE_HOME = {
    "google": "https://www.google.com",
    "duckduckgo": "https://duckduckgo.com",
    "bing": "https://www.bing.com",
}

SEARCH_ENGINE_QUERY = {
    "google": "https://www.google.com/search?q=",
    "duckduckgo": "https://duckduckgo.com/?q=",
    "bing": "https://www.bing.com/search?q=",
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
# TabBar with context menu + DnD between windows
# -------------------------
class DragSafeTabBar(QTabBar):
    _drag_source = None  # (source_window, index)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(False)  # we handle moves explicitly
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self._dragging = False
        self._press_pos = None
        self._drag_threshold = 6
        self._drag_index = -1

        self.setAcceptDrops(True)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press_pos = e.pos()
            self._dragging = False
            self._drag_index = self.tabAt(e.pos())
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._press_pos and (e.buttons() & Qt.MouseButton.LeftButton):
            if (e.pos() - self._press_pos).manhattanLength() > self._drag_threshold:
                if not self._dragging and self._drag_index >= 0:
                    self._dragging = True
                    self.start_drag(self._drag_index)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._press_pos = None
        self._dragging = False
        self._drag_index = -1
        super().mouseReleaseEvent(e)

    def start_drag(self, index: int):
        window = self.find_browser_window()
        if window is None:
            return

        DragSafeTabBar._drag_source = (window, index)

        drag = QDrag(self)
        mime = QMimeData()
        # IMPORTANT: mimetype must be str, not bytes
        mime.setData("application/x-pybrowser-tab", QByteArray(b"tab"))
        drag.setMimeData(mime)
        result = drag.exec(Qt.DropAction.MoveAction)

        # If no tab bar accepted the drop, detach into new window
        if result != Qt.DropAction.MoveAction:
            if index < window.tabs.count():
                window.detach_tab(index)

        DragSafeTabBar._drag_source = None
        self._dragging = False

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-pybrowser-tab"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-pybrowser-tab"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasFormat("application/x-pybrowser-tab"):
            event.ignore()
            return

        info = DragSafeTabBar._drag_source
        DragSafeTabBar._drag_source = None
        if not info:
            event.ignore()
            return

        source_window, src_index = info
        dest_window = self.find_browser_window()
        if not dest_window:
            event.ignore()
            return

        dest_index = self.tabAt(event.pos())
        if dest_index < 0:
            dest_index = dest_window.tabs.count()

        if source_window is dest_window:
            # Same window: reorder tab
            source_window.move_tab_within(src_index, dest_index)
        else:
            # Different windows: move tab to other window
            source_window.move_tab_to_other_window(src_index, dest_window, dest_index)

        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def find_browser_window(self):
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, CustomBrowser):
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
# Settings dialog
# -------------------------
class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._settings = settings

        self.search_engine = settings.get("search_engine", "google")
        self.bg_color = settings.get("bg_color", "#000000")
        self.custom_page_bg_enabled = settings.get("custom_page_bg_enabled", False)
        self.page_bg_color = settings.get("page_bg_color", "#ffffff")

        layout = QVBoxLayout(self)

        # Search engine
        layout.addWidget(QLabel("Default search engine:"))
        self.engine_combo = QComboBox(self)
        self.engine_combo.addItems(["google", "duckduckgo", "bing"])
        if self.search_engine in ("google", "duckduckgo", "bing"):
            self.engine_combo.setCurrentText(self.search_engine)
        layout.addWidget(self.engine_combo)

        # Browser background color
        self.bg_label = QLabel(f"Browser background color: {self.bg_color}")
        self.bg_button = QPushButton("Choose browser background color")
        self.bg_button.clicked.connect(self.pick_bg_color)
        layout.addWidget(self.bg_label)
        layout.addWidget(self.bg_button)

        # Custom webpage background color
        self.page_bg_checkbox = QCheckBox("Enable custom webpage background color")
        self.page_bg_checkbox.setChecked(self.custom_page_bg_enabled)
        self.page_bg_label = QLabel(f"Webpage background color: {self.page_bg_color}")
        self.page_bg_button = QPushButton("Choose webpage background color")
        self.page_bg_button.clicked.connect(self.pick_page_bg_color)
        layout.addWidget(self.page_bg_checkbox)
        layout.addWidget(self.page_bg_label)
        layout.addWidget(self.page_bg_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def pick_bg_color(self):
        col = QColorDialog.getColor(QColor(self.bg_color), self, "Select browser background color")
        if col.isValid():
            self.bg_color = col.name()
            self.bg_label.setText(f"Browser background color: {self.bg_color}")

    def pick_page_bg_color(self):
        col = QColorDialog.getColor(QColor(self.page_bg_color), self, "Select webpage background color")
        if col.isValid():
            self.page_bg_color = col.name()
            self.page_bg_label.setText(f"Webpage background color: {self.page_bg_color}")

    def get_values(self) -> dict:
        return {
            "search_engine": self.engine_combo.currentText(),
            "bg_color": self.bg_color,
            "custom_page_bg_enabled": self.page_bg_checkbox.isChecked(),
            "page_bg_color": self.page_bg_color,
        }


# -------------------------
# Browser
# -------------------------
class CustomBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyBrowser")
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

        # --- Navigation Bar (no custom top bar)
        self.setup_nav_bar()

        # --- Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(False)  # DnD is handled by DragSafeTabBar
        self.tabs.setTabBar(DragSafeTabBar())
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_title)
        self.main_layout.addWidget(self.tabs)

        self.main_widget = QWidget()
        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)

        self.downloads_panel = DownloadsPanel(self)
        self.downloads_panel.hide()

        self.apply_gui_colors()
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
    def get_home_url(self) -> str:
        engine = self.settings.get("search_engine", "google").lower()
        return SEARCH_ENGINE_HOME.get(engine, SEARCH_ENGINE_HOME["google"])

    def position_downloads_panel(self):
        if self.downloads_panel and self.downloads_panel.isVisible():
            self.downloads_panel.adjustSize()
            x = self.width() - self.downloads_panel.width() - 12
            y = self.nav_bar.height() + 8
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
            engine = self.settings.get("search_engine", "google").lower()
            base = SEARCH_ENGINE_QUERY.get(engine, SEARCH_ENGINE_QUERY["google"])
            url = base + text.replace(" ", "+")
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

        b.urlChanged.connect(self.update_url_bar)
        b.titleChanged.connect(lambda t, br=b: self.update_tab_title(br, t))
        b.iconChanged.connect(lambda i, br=b: self.update_tab_icon(br, i))
        b.page().loadFinished.connect(lambda ok, br=b: self.on_page_load_finished(br, ok))

        tab = QWidget()
        l = QVBoxLayout()
        l.setContentsMargins(0, 0, 0, 0)
        l.addWidget(b)
        tab.setLayout(l)
        idx = self.tabs.addTab(tab, "Loading...")
        self.tabs.setCurrentIndex(idx)

        default_url = QUrl(url) if url else QUrl(self.get_home_url())
        b.setUrl(default_url)

    def add_existing_tab(self, tab_widget: QWidget, title: str, icon: QIcon):
        # reconnect signals to this window
        browser = tab_widget.layout().itemAt(0).widget()
        try:
            browser.urlChanged.disconnect()
        except TypeError:
            pass
        try:
            browser.titleChanged.disconnect()
        except TypeError:
            pass
        try:
            browser.iconChanged.disconnect()
        except TypeError:
            pass
        try:
            browser.page().loadFinished.disconnect()
        except TypeError:
            pass

        browser.urlChanged.connect(self.update_url_bar)
        browser.titleChanged.connect(lambda t, br=browser: self.update_tab_title(br, t))
        browser.iconChanged.connect(lambda i, br=browser: self.update_tab_icon(br, i))
        browser.page().loadFinished.connect(lambda ok, br=browser: self.on_page_load_finished(br, ok))

        idx = self.tabs.addTab(tab_widget, icon, title)
        self.tabs.setCurrentIndex(idx)

    def detach_tab(self, index: int):
        if index < 0 or index >= self.tabs.count():
            return
        tab_widget = self.tabs.widget(index)
        title = self.tabs.tabText(index)
        icon = self.tabs.tabIcon(index)
        self.tabs.removeTab(index)

        new_window = CustomBrowser()
        new_window.add_existing_tab(tab_widget, title, icon)
        if new_window.tabs.count() > 1:
            new_window.close_tab(0)
        new_window.show()

    def move_tab_to_other_window(self, index: int, dest_window: "CustomBrowser", dest_index: int):
        if index < 0 or index >= self.tabs.count():
            return
        tab_widget = self.tabs.widget(index)
        title = self.tabs.tabText(index)
        icon = self.tabs.tabIcon(index)
        self.tabs.removeTab(index)

        dest_window.insert_existing_tab(tab_widget, title, icon, dest_index)

        if self.tabs.count() == 0:
            self.add_new_tab()

    def insert_existing_tab(self, tab_widget: QWidget, title: str, icon: QIcon, dest_index: int):
        browser = tab_widget.layout().itemAt(0).widget()
        try:
            browser.urlChanged.disconnect()
        except TypeError:
            pass
        try:
            browser.titleChanged.disconnect()
        except TypeError:
            pass
        try:
            browser.iconChanged.disconnect()
        except TypeError:
            pass
        try:
            browser.page().loadFinished.disconnect()
        except TypeError:
            pass

        browser.urlChanged.connect(self.update_url_bar)
        browser.titleChanged.connect(lambda t, br=browser: self.update_tab_title(br, t))
        browser.iconChanged.connect(lambda i, br=browser: self.update_tab_icon(br, i))
        browser.page().loadFinished.connect(lambda ok, br=browser: self.on_page_load_finished(br, ok))

        dest_index = max(0, min(dest_index, self.tabs.count()))
        self.tabs.insertTab(dest_index, tab_widget, icon, title)
        self.tabs.setCurrentIndex(dest_index)

    def move_tab_within(self, from_index: int, to_index: int):
        count = self.tabs.count()
        if from_index < 0 or from_index >= count:
            return
        to_index = max(0, min(to_index, count - 1))
        if from_index == to_index:
            return
        tab_widget = self.tabs.widget(from_index)
        title = self.tabs.tabText(from_index)
        icon = self.tabs.tabIcon(from_index)
        self.tabs.removeTab(from_index)
        if from_index < to_index:
            to_index -= 1
        self.tabs.insertTab(to_index, tab_widget, icon, title)
        self.tabs.setCurrentIndex(to_index)

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
        if b:
            b.back()

    def go_forward(self):
        b = self.get_current_browser()
        if b:
            b.forward()

    def reload_page(self):
        b = self.get_current_browser()
        if b:
            b.reload()

    def go_home(self):
        b = self.get_current_browser()
        if b:
            b.setUrl(QUrl(self.get_home_url()))

    # --- Helpers ---
    def get_current_browser(self):
        cw = self.tabs.currentWidget()
        return cw.layout().itemAt(0).widget() if cw else None

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def load_settings(self):
        data = DEFAULT_SETTINGS.copy()
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        data.update(loaded)
            except Exception:
                pass
        return data

    def save_settings(self):
        try:
            with open(self.settings_file, "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass

    def apply_gui_colors(self):
        bg = self.settings.get("bg_color", "#000000")
        self.setStyleSheet(f"QMainWindow {{ background-color: {bg}; }}")
        self.main_widget.setStyleSheet(f"background-color: {bg};")
        self.nav_bar.setStyleSheet(f"background-color: {bg};")

    def update_url_bar(self, qurl):
        self.url_bar.setText(qurl.toString())

    def update_title(self):
        current_widget = self.tabs.currentWidget()
        if current_widget:
            self.setWindowTitle(self.tabs.tabText(self.tabs.currentIndex()))
        else:
            self.setWindowTitle("PyBrowser")

    def update_tab_title(self, browser, title):
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).layout().itemAt(0).widget() == browser:
                self.tabs.setTabText(i, title if title else "New Tab")
                if self.tabs.currentIndex() == i:
                    self.setWindowTitle(title if title else "New Tab")
                break

    def update_tab_icon(self, browser, icon: QIcon):
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).layout().itemAt(0).widget() == browser:
                self.tabs.setTabIcon(i, icon)
                break

    def on_page_load_finished(self, browser: QWebEngineView, ok: bool):
        if not ok:
            return
        self.apply_custom_page_background(browser)

    def apply_custom_page_background(self, browser: QWebEngineView | None = None):
        if not self.settings.get("custom_page_bg_enabled", False):
            return
        color = self.settings.get("page_bg_color", "#ffffff")
        script = f"""
            (function() {{
                try {{
                    document.documentElement.style.backgroundColor = '{color}';
                    if (document.body) {{
                        document.body.style.backgroundColor = '{color}';
                    }}
                }} catch (e) {{}}
            }})();
        """
        if browser is None:
            browser = self.get_current_browser()
        if browser:
            browser.page().runJavaScript(script)

    def open_settings_dialog(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.get_values()
            self.settings.update(vals)
            self.save_settings()
            self.apply_gui_colors()
            # Reapply custom page background to current tab if enabled
            self.apply_custom_page_background()

    def open_menu(self):
        menu = QMenu(self)
        downloads_action = menu.addAction("Downloads")
        settings_action = menu.addAction("Settings")
        downloads_action.triggered.connect(lambda: os.startfile(self.downloads_dir))
        settings_action.triggered.connect(self.open_settings_dialog)
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
