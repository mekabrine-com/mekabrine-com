import sys, os, json, ctypes, time
import pyotp

from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton,
    QLineEdit, QTextEdit, QHBoxLayout, QLabel, QMenu, QListWidget, QDialog,
    QColorDialog, QCheckBox, QMessageBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, Qt, QTimer
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QPen, QColor, QFont


# -------------------------
# Defaults / Settings
# -------------------------
DEFAULT_SETTINGS = {
    "gui_color": "#000000",
    "bg_color": "#000000",
    "text_color": "#ffffff",
    "other_bg_color": "#111111",   # card/container backgrounds
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
# Small UI helpers
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
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{self.seconds_left}s")


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
        QTimer.singleShot(2500, self.close)


# -------------------------
# Popups
# -------------------------
class HistoryPopup(QDialog):
    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.setWindowTitle("History")
        self.setGeometry(200, 200, 400, 300)
        layout = QVBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.addItems(history)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)

        self.list_widget.itemDoubleClicked.connect(
            lambda item: parent.get_current_browser().setUrl(QUrl(item.text()))
        )


class SettingsPopup(QDialog):
    def __init__(self, parent, settings_file):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setGeometry(250, 250, 420, 320)
        self.parent = parent

        layout = QVBoxLayout()

        self.gui_color_btn = QPushButton(f"GUI Color (current: {parent.settings['gui_color']})")
        self.gui_color_btn.clicked.connect(lambda: self.pick_color("gui_color", self.gui_color_btn))
        layout.addWidget(self.gui_color_btn)

        self.bg_color_btn = QPushButton(f"Page Background (current: {parent.settings['bg_color']})")
        self.bg_color_btn.clicked.connect(lambda: self.pick_color("bg_color", self.bg_color_btn))
        layout.addWidget(self.bg_color_btn)

        self.text_color_btn = QPushButton(f"Page Text (current: {parent.settings['text_color']})")
        self.text_color_btn.clicked.connect(lambda: self.pick_color("text_color", self.text_color_btn))
        layout.addWidget(self.text_color_btn)

        self.other_bg_color_btn = QPushButton(f"Other Background (current: {parent.settings['other_bg_color']})")
        self.other_bg_color_btn.clicked.connect(lambda: self.pick_color("other_bg_color", self.other_bg_color_btn))
        layout.addWidget(self.other_bg_color_btn)

        self.custom_colors_toggle = QCheckBox("Enable Custom Website Colors")
        self.custom_colors_toggle.setChecked(parent.settings["custom_colors"])
        self.custom_colors_toggle.stateChanged.connect(
            lambda state: parent.update_setting("custom_colors", state == Qt.CheckState.Checked)
        )
        layout.addWidget(self.custom_colors_toggle)

        self.reset_btn = QPushButton("Reset to Default")
        self.reset_btn.clicked.connect(self.reset_defaults)
        layout.addWidget(self.reset_btn)

        self.setLayout(layout)

    def pick_color(self, key, btn):
        color = QColorDialog.getColor()
        if color.isValid():
            hex_color = color.name()
            self.parent.update_setting(key, hex_color)
            label = btn.text().split("(current:")[0].strip()
            btn.setText(f"{label} (current: {hex_color})")

    def reset_defaults(self):
        self.parent.settings.update(DEFAULT_SETTINGS)
        self.parent.save_settings()
        self.parent.apply_gui_color()
        QMessageBox.information(self, "Reset", "Settings reset to default.")


class ToolsPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tools")
        self.setGeometry(300, 300, 450, 420)
        self.parent = parent

        layout = QVBoxLayout()

        # TOTP
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

    # TOTP
    def start_totp(self):
        secret = self.key_input.text().strip()
        if not secret:
            self.code_label.setText("Enter a secret key first")
            return
        try:
            self.secret = secret
            self.totp = pyotp.TOTP(secret)
            self.refresh_code()
            self.timer.start(1000)  # updates the circle/seconds; code refresh is scheduled
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

    # Inject JS
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

        # Permissions + Downloads
        self.permissions_file = r"C:\PyBrowser\permissions\permissions.json"
        os.makedirs(os.path.dirname(self.permissions_file), exist_ok=True)
        if not os.path.exists(self.permissions_file):
            with open(self.permissions_file, "w") as f:
                json.dump({}, f)

        self.downloads_dir = r"C:\PyBrowser\Downloads"
        os.makedirs(self.downloads_dir, exist_ok=True)
        self.profile.downloadRequested.connect(self.handle_download)

        self.history = []
        self.setGeometry(100, 100, 1024, 768)

        self.main_layout = QVBoxLayout()

        # --- Top bar
        self.top_bar = QWidget()
        self.top_bar_layout = QHBoxLayout()
        self.top_bar_layout.setContentsMargins(5, 2, 5, 2)

        self.icon_label = QLabel()
        try:
            pixmap = QPixmap("C:\\Program Files\\PyBrowser\\Icon.ico").scaled(15, 15)
            self.icon_label.setPixmap(pixmap)
        except Exception:
            pass
        self.top_bar_layout.addWidget(self.icon_label)

        self.title_label = QLabel("PyBrowser v2")
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

    # --- Downloads ---
    def handle_download(self, download_item):
        """
        QWebEngineDownloadRequest:
          - setDownloadDirectory(dir)
          - setDownloadFileName(name)
          - accept()
          - signals: downloadProgress(received, total), finished()
        """
        try:
            # Ensure directory + filename are set
            download_item.setDownloadDirectory(self.downloads_dir)
            # Keep the server-suggested filename
            # (You could override with something custom if you like)
            # download_item.setDownloadFileName(download_item.downloadFileName())
            download_item.accept()
        except Exception:
            # Fallback path set (older bindings sometimes expose setPath)
            path = os.path.join(self.downloads_dir, download_item.downloadFileName())
            try:
                download_item.setPath(path)
                download_item.accept()
            except Exception:
                pass

        # Toast UI
        toast = QLabel(f"Downloading {download_item.downloadFileName()} (0%)", self)
        toast.setStyleSheet("""
            background-color: rgba(0,0,0,200);
            color: white;
            padding: 6px 12px;
            border-radius: 6px;
        """)
        toast.setWindowFlags(Qt.WindowType.ToolTip)
        toast.adjustSize()
        pos = self.mapToGlobal(self.rect().center())
        toast.move(pos.x() - toast.width() // 2, pos.y() - 100)
        toast.show()

        def update_progress(received, total):
            if total > 0:
                pct = int((received / total) * 100)
                toast.setText(f"Downloading {download_item.downloadFileName()} ({pct}%)")
                toast.adjustSize()

        def finish():
            toast.setText(f"Download complete: {download_item.downloadFileName()}")
            toast.adjustSize()
            QTimer.singleShot(2500, toast.close)

        try:
            download_item.downloadProgress.connect(update_progress)
        except Exception:
            pass
        try:
            download_item.finished.connect(finish)
        except Exception:
            pass

    def open_downloads(self):
        try:
            os.startfile(self.downloads_dir)
        except Exception:
            QMessageBox.warning(self, "Downloads", "Could not open Downloads folder.")

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

    # Settings load/save
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
        self.top_bar.setStyleSheet(f"background-color: {gui_color}; color: white;")
        self.nav_bar.setStyleSheet(f"background-color: {gui_color}; color: white;")

    # Tabs
    def add_new_tab(self, url=None):
        browser = QWebEngineView()
        page = QWebEnginePage(self.profile, browser)
        browser.setPage(page)

        # Permission handler
        page.featurePermissionRequested.connect(self.on_permission_requested)

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
        # If user navigated to Spotify Web → launch app and go home
        try:
            if "open.spotify.com" in browser.url().toString().lower():
                try:
                    os.startfile("spotify:")
                except Exception:
                    QMessageBox.warning(self, "Spotify", "Spotify desktop app not found.")
                # Navigate away to prevent the unsupported player staying open
                browser.setUrl(QUrl(self.DEFAULT_URL))
                return
        except Exception:
            pass

        self.inject_custom_colors(browser)
        url = browser.url().toString()
        if url and (not self.history or self.history[-1] != url):
            self.history.append(url)

    def inject_custom_colors(self, browser: QWebEngineView):
        if not self.settings.get("custom_colors", False):
            return
        bg = self.settings["bg_color"]
        other_bg = self.settings.get("other_bg_color", "#111111")
        text = self.settings["text_color"]

        js = f"""
            (function() {{
              try {{
                document.documentElement.style.background = "{bg}";
                document.body.style.background = "{bg}";
                document.documentElement.style.color = "{text}";
                document.body.style.color = "{text}";

                // Replace non-transparent backgrounds on all elements
                const all = document.querySelectorAll('*');
                for (const el of all) {{
                  const cs = getComputedStyle(el);
                  if (cs && cs.backgroundColor && cs.backgroundColor !== "rgba(0, 0, 0, 0)") {{
                    el.style.backgroundColor = "{other_bg}";
                  }}
                  if (cs && cs.color) {{
                    el.style.color = "{text}";
                  }}
                }}
              }} catch(e) {{ /* ignore */ }}
            }})();
        """
        browser.page().runJavaScript(js)

    # --- Permissions ---
    def on_permission_requested(self, url, feature):
        site = url.host()
        feature_map = {
            QWebEnginePage.Feature.MediaAudioCapture: "microphone",
            QWebEnginePage.Feature.MediaVideoCapture: "camera",
            QWebEnginePage.Feature.Geolocation: "geolocation"
        }
        feature_name = feature_map.get(feature)
        if not feature_name:
            return

        # Load rules
        try:
            with open(self.permissions_file, "r") as f:
                perms = json.load(f)
        except Exception:
            perms = {}

        site_perms = perms.get(site, {})

        if feature_name in site_perms and site_perms[feature_name] in ["allow", "deny"]:
            decision = site_perms[feature_name]
            policy = (QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
                      if decision == "allow"
                      else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)
            self.get_current_browser().page().setFeaturePermission(url, feature, policy)
            return

        # Ask the user
        dlg = QDialog(self)
        dlg.setWindowTitle("Permission Request")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(f"{site} wants to access your {feature_name}."))

        allow_once_btn = QPushButton("Allow once")
        always_allow_btn = QPushButton("Always allow for this site")
        deny_btn = QPushButton("Don't allow")

        v.addWidget(allow_once_btn)
        v.addWidget(always_allow_btn)
        v.addWidget(deny_btn)

        choice = {"value": "deny"}  # default

        def choose(val):
            choice["value"] = val
            dlg.accept()

        allow_once_btn.clicked.connect(lambda: choose("allow_once"))
        always_allow_btn.clicked.connect(lambda: choose("always_allow"))
        deny_btn.clicked.connect(lambda: choose("deny"))

        dlg.exec()
        sel = choice["value"]

        if sel == "allow_once":
            # Allow for current tab session, persist as 'deny' so it will ask next time.
            self.get_current_browser().page().setFeaturePermission(
                url, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
            )
            site_perms[feature_name] = "deny"
            perms[site] = site_perms
            with open(self.permissions_file, "w") as f:
                json.dump(perms, f, indent=2)

        elif sel == "always_allow":
            self.get_current_browser().page().setFeaturePermission(
                url, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
            )
            site_perms[feature_name] = "allow"
            perms[site] = site_perms
            with open(self.permissions_file, "w") as f:
                json.dump(perms, f, indent=2)

        else:  # deny
            self.get_current_browser().page().setFeaturePermission(
                url, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
            )
            site_perms[feature_name] = "deny"
            perms[site] = site_perms
            with open(self.permissions_file, "w") as f:
                json.dump(perms, f, indent=2)

    # Tab UI updates
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

    # Navigation + URL handling
    def load_url(self):
        text = self.url_bar.text().strip()
        if not text:
            return

        # Keyword shortcuts (case-insensitive exact match)
        shortcuts = {
            "roblox": "https://www.roblox.com",
            "google": "https://www.google.com",
            "gmail": "https://mail.google.com",
            "apple": "https://www.apple.com",
            "youtube": "https://www.youtube.com",
            "chatgpt": "https://www.chatgpt.com",
        }
        lower = text.lower()

        # Spotify redirect
        if "open.spotify.com" in lower or lower == "spotify":
            try:
                os.startfile("spotify:")  # opens Spotify desktop client
            except Exception:
                QMessageBox.warning(self, "Spotify", "Spotify desktop app not found.")
            return

        if lower in shortcuts:
            url = shortcuts[lower]
        elif " " in text or "." not in text:
            # Smart Google search
            query = text.replace(" ", "+")
            url = f"https://www.google.com/search?q={query}"
        else:
            url = text if text.startswith("http") else "https://" + text

        b = self.get_current_browser()
        if b:
            b.setUrl(QUrl(url))

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

    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)

    def update_url_bar(self, qurl):
        self.url_bar.setText(qurl.toString())

    def update_title(self):
        current_widget = self.tabs.currentWidget()
        if current_widget:
            self.setWindowTitle(self.tabs.tabText(self.tabs.currentIndex()) + " - PyBrowser")

    # Menu & popups
    def open_menu(self):
        menu = QMenu(self)
        history_action = menu.addAction("History")
        settings_action = menu.addAction("Settings")
        tools_action = menu.addAction("Tools")
        downloads_action = menu.addAction("Downloads")

        history_action.triggered.connect(self.show_history)
        settings_action.triggered.connect(self.show_settings)
        tools_action.triggered.connect(self.show_tools)
        downloads_action.triggered.connect(self.open_downloads)

        menu.exec(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))

    def show_history(self):
        self.history_popup = HistoryPopup(self.history, self)
        self.history_popup.show()

    def show_settings(self):
        self.settings_popup = SettingsPopup(self, self.settings_file)
        self.settings_popup.show()

    def show_tools(self):
        self.tools_popup = ToolsPopup(self)
        self.tools_popup.show()


# -------------------------
# Run
# -------------------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = CustomBrowser()
    window.show()
    sys.exit(app.exec())
