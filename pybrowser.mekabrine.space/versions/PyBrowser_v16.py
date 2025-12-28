import sys, os, json, base64, ctypes
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton,
    QLineEdit, QHBoxLayout, QLabel, QMenu, QListWidget, QDialog, QColorDialog,
    QCheckBox, QMessageBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, Qt, QPoint
from PyQt6.QtGui import QPixmap, QIcon


def request_admin():
    if ctypes.windll.shell32.IsUserAnAdmin():
        return
    ctypes.windll.shell32.ShellExecuteW(
        None, 'runas', sys.executable, ' ' + ' '.join(sys.argv), None, 1
    )
    sys.exit(0)


# minimize console on startup (best effort)
def minimize_console():
    try:
        import win32gui, win32con
        hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    except Exception:
        pass


request_admin()
minimize_console()


DEFAULT_SETTINGS = {
    "gui_color": "#000000",   # black
    "bg_color":  "#000000",   # black
    "text_color": "#ffffff",  # white
    "custom_colors": False
}


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


class SettingsPopup(QDialog):
    def __init__(self, parent, settings_file):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setGeometry(250, 250, 420, 240)
        self.settings_file = settings_file
        self.parent = parent

        layout = QVBoxLayout()

        # GUI Color Picker
        self.gui_color_btn = QPushButton(f"GUI Color (current: {parent.settings.get('gui_color')})")
        self.gui_color_btn.clicked.connect(lambda: self.pick_color("gui_color", self.gui_color_btn))
        layout.addWidget(self.gui_color_btn)

        # Background Color Picker
        self.bg_color_btn = QPushButton(f"Page Background (current: {parent.settings.get('bg_color')})")
        self.bg_color_btn.clicked.connect(lambda: self.pick_color("bg_color", self.bg_color_btn))
        layout.addWidget(self.bg_color_btn)

        # Text Color Picker
        self.text_color_btn = QPushButton(f"Page Text (current: {parent.settings.get('text_color')})")
        self.text_color_btn.clicked.connect(lambda: self.pick_color("text_color", self.text_color_btn))
        layout.addWidget(self.text_color_btn)

        # Toggle custom colors
        self.custom_colors_toggle = QCheckBox("Enable Custom Website Colors")
        self.custom_colors_toggle.setChecked(parent.settings.get("custom_colors", False))
        self.custom_colors_toggle.stateChanged.connect(
            lambda state: parent.update_setting("custom_colors", state == Qt.CheckState.Checked)
        )
        layout.addWidget(self.custom_colors_toggle)

        # Reset to default
        self.reset_btn = QPushButton("Reset to Default")
        self.reset_btn.clicked.connect(self.reset_defaults)
        layout.addWidget(self.reset_btn)

        self.setLayout(layout)

    def pick_color(self, key, btn):
        color = QColorDialog.getColor()
        if color.isValid():
            hex_color = color.name()
            self.parent.update_setting(key, hex_color)
            btn.setText(f"{btn.text().split('(current:')[0].strip()} (current: {hex_color})")

    def reset_defaults(self):
        self.parent.settings.update(DEFAULT_SETTINGS)
        self.parent.save_settings()
        self.parent.apply_gui_color()
        # Update button captions to reflect new current values
        self.gui_color_btn.setText(f"GUI Color (current: {self.parent.settings['gui_color']})")
        self.bg_color_btn.setText(f"Page Background (current: {self.parent.settings['bg_color']})")
        self.text_color_btn.setText(f"Page Text (current: {self.parent.settings['text_color']})")
        self.custom_colors_toggle.setChecked(self.parent.settings['custom_colors'])
        QMessageBox.information(self, "Reset", "Settings reset to default.")


class CustomBrowser(QMainWindow):
    DEFAULT_URL = "https://www.google.com"

    def __init__(self):
        super().__init__()

        # Paths
        self.settings_file = r"C:\PyBrowser\settings.json"
        self.passwords_path = r"C:\PyBrowser\Passwords"
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
        os.makedirs(self.passwords_path, exist_ok=True)

        # Settings
        self.settings = self.load_settings()

        # Web profile
        self.profile = QWebEngineProfile("PyBrowserProfile", self)

        self.history = []
        self.old_pos = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setGeometry(100, 100, 1024, 768)

        self.main_layout = QVBoxLayout()

        # --- Top bar ---
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

        self.close_button = QPushButton("❌")
        self.close_button.clicked.connect(self.close)
        self.top_bar_layout.addWidget(self.close_button)

        self.top_bar.setLayout(self.top_bar_layout)
        self.main_layout.addWidget(self.top_bar)

        # --- Nav bar ---
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

        # --- Tabs ---
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

        # drag window
        self.top_bar.setMouseTracking(True)
        self.top_bar.mousePressEvent = self.mouse_press_event
        self.top_bar.mouseMoveEvent = self.mouse_move_event
        self.top_bar.mouseReleaseEvent = self.mouse_release_event

    # ---------- Settings ----------
    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    loaded = json.load(f)
                # ensure all defaults exist
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

    # ---------- Password manager ----------
    def passwords_file_for_domain(self, domain: str) -> str:
        safe = domain.replace(":", "_")
        return os.path.join(self.passwords_path, f"{safe}.json")

    def b64e(self, s: str) -> str:
        return base64.b64encode(s.encode("utf-8")).decode("ascii")

    def b64d(self, s: str) -> str:
        try:
            return base64.b64decode(s.encode("ascii")).decode("utf-8")
        except Exception:
            return ""

    def handle_console_message(self, level, message, line, source, browser):
        prefix = "PYBROWSER_LOGIN_CAPTURE:"
        if message.startswith(prefix):
            try:
                payload = json.loads(message[len(prefix):])
                username = payload.get("username", "")
                password = payload.get("password", "")
                domain = browser.url().host()
                if username and password and domain:
                    self.prompt_save_credentials(domain, username, password)
            except Exception as e:
                print("Login capture parse error:", e)

    def prompt_save_credentials(self, domain: str, username: str, password: str):
        file_path = self.passwords_file_for_domain(domain)
        # If same username already saved, skip prompt
        existing = {}
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                if self.b64d(existing.get("username_b64", "")) == username:
                    return
            except Exception:
                existing = {}

        reply = QMessageBox.question(
            self, "Save login?",
            f"Save login for {domain}?\n\nUsername: {username}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            data = {
                "username_b64": self.b64e(username),
                "password_b64": self.b64e(password),
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def maybe_offer_autofill(self, browser: QWebEngineView):
        domain = browser.url().host()
        file_path = self.passwords_file_for_domain(domain)
        if not os.path.exists(file_path):
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            username = self.b64d(data.get("username_b64", ""))
            password = self.b64d(data.get("password_b64", ""))
            if not username or not password:
                return
        except Exception:
            return

        reply = QMessageBox.question(
            self, "Autofill?",
            f"Autofill saved login for {domain}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # fill common username/password fields
            u_js = json.dumps(username)
            p_js = json.dumps(password)
            js = f"""
                (function(u, p) {{
                    // Try common selectors
                    let uSel = "input[type='email'],input[type='text'],input[name*=\"user\" i],input[name*=\"email\" i]";
                    let pSel = "input[type='password']";
                    let uInput = document.querySelector(uSel);
                    let pInput = document.querySelector(pSel);
                    if (uInput) uInput.value = u;
                    if (pInput) pInput.value = p;
                }})({u_js}, {p_js});
            """
            browser.page().runJavaScript(js)

    # ---------- Tabs / Page ----------
    def add_new_tab(self, url=None):
        browser = QWebEngineView()
        page = QWebEnginePage(self.profile, browser)
        # capture console messages from JS for password capture
        page.javaScriptConsoleMessage = lambda lvl, msg, line, src, b=browser: self.handle_console_message(lvl, msg, line, src, b)
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
        # Apply custom page colors (html, body only)
        self.inject_custom_colors(browser)
        # Inject password capture watchers
        self.inject_password_capture(browser)
        # Offer autofill if we have saved login for this domain
        self.maybe_offer_autofill(browser)

    def inject_custom_colors(self, browser: QWebEngineView):
        if not self.settings.get("custom_colors", False):
            return
        bg = self.settings.get("bg_color", DEFAULT_SETTINGS["bg_color"])
        text = self.settings.get("text_color", DEFAULT_SETTINGS["text_color"])
        js = f"""
            document.documentElement.style.background = "{bg}";
            document.body.style.background = "{bg}";
            document.documentElement.style.color = "{text}";
            document.body.style.color = "{text}";
        """
        browser.page().runJavaScript(js)

    def inject_password_capture(self, browser: QWebEngineView):
        # Watch password fields and send captured creds to console
        js = """
            (function(){
                const prefix = "PYBROWSER_LOGIN_CAPTURE:";
                let last = {u:"", p:""};
                function capture(pwdField){
                    const form = pwdField.closest("form") || document;
                    let u = "";
                    // try nearby fields
                    const inputs = form.querySelectorAll("input");
                    for (const input of inputs) {
                        const t = (input.type || "").toLowerCase();
                        const n = (input.name || "").toLowerCase();
                        if ((t === "text" || t === "email" || n.includes("user") || n.includes("email")) && input.value.trim()) {
                            u = input.value.trim(); break;
                        }
                    }
                    const p = pwdField.value || "";
                    if (u && p && (u !== last.u || p !== last.p)) {
                        last = {u, p};
                        console.log(prefix + JSON.stringify({username:u, password:p}));
                    }
                }
                function hook(){
                    const pwds = document.querySelectorAll("input[type='password']");
                    pwds.forEach(p => {
                        p.addEventListener("blur", () => capture(p));
                        p.addEventListener("keydown", (e)=>{ if(e.key==="Enter"){ capture(p);} });
                        p.addEventListener("change", () => capture(p));
                    });
                }
                hook();
                // In case of late-loaded forms
                setTimeout(hook, 1500);
                setTimeout(hook, 4000);
            })();
        """
        browser.page().runJavaScript(js)

    # ---------- Title / Icon ----------
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

    # ---------- Window controls ----------
    def mouse_press_event(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.top_bar.underMouse():
            self.old_pos = event.globalPosition().toPoint()

    def mouse_move_event(self, event):
        if self.old_pos and event.buttons() == Qt.MouseButton.LeftButton:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouse_release_event(self, event):
        self.old_pos = None

    # ---------- Browser actions ----------
    def go_back(self): self.tabs.currentWidget().layout().itemAt(0).widget().back()
    def go_forward(self): self.tabs.currentWidget().layout().itemAt(0).widget().forward()
    def reload_page(self): self.tabs.currentWidget().layout().itemAt(0).widget().reload()
    def go_home(self): self.tabs.currentWidget().layout().itemAt(0).widget().setUrl(QUrl(self.DEFAULT_URL))
    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
    def load_url(self):
        url = self.url_bar.text().strip()
        if not url.startswith("http"):
            url = "https://" + url
        self.tabs.currentWidget().layout().itemAt(0).widget().setUrl(QUrl(url))
        self.history.append(url)
    def update_url_bar(self, url): self.url_bar.setText(url.toString())
    def update_title(self):
        current_widget = self.tabs.currentWidget()
        if current_widget:
            self.setWindowTitle(self.tabs.tabText(self.tabs.currentIndex()) + " - PyBrowser")
    def open_menu(self):
        menu = QMenu(self)
        history_action = menu.addAction("History")
        settings_action = menu.addAction("Settings")
        history_action.triggered.connect(self.show_history)
        settings_action.triggered.connect(self.show_settings)
        menu.exec(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))
    def show_history(self):
        self.history_popup = HistoryPopup(self.history, self)
        self.history_popup.show()
    def show_settings(self):
        self.settings_popup = SettingsPopup(self, self.settings_file)
        self.settings_popup.show()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = CustomBrowser()
    window.show()
    sys.exit(app.exec())
