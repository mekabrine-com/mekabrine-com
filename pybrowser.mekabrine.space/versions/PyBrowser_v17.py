import sys
import os
import json
import base64
import ctypes

from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton,
    QLineEdit, QHBoxLayout, QLabel, QMenu, QListWidget, QDialog, QColorDialog,
    QCheckBox, QMessageBox, QInputDialog
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, Qt, QPoint
from PyQt6.QtGui import QPixmap, QIcon

# -------------------------
# Constants & Helpers
# -------------------------
DEFAULT_SETTINGS = {
    "gui_color": "#000000",   # black
    "bg_color":  "#000000",   # black
    "text_color": "#ffffff",  # white
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
    # best-effort minimization of the console window (requires pywin32)
    try:
        import win32gui, win32con
        hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    except Exception:
        pass

# Try to request admin (keeps your original behavior) and minimize console
request_admin()
minimize_console()

# -------------------------
# UI Popups
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

class SettingsPopup(QDialog):
    def __init__(self, parent, settings_file):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setGeometry(250, 250, 420, 260)
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
            # update the button text
            label = btn.text().split("(current:")[0].strip()
            btn.setText(f"{label} (current: {hex_color})")

    def reset_defaults(self):
        self.parent.settings.update(DEFAULT_SETTINGS)
        self.parent.save_settings()
        self.parent.apply_gui_color()
        # Update button captions
        self.gui_color_btn.setText(f"GUI Color (current: {self.parent.settings['gui_color']})")
        self.bg_color_btn.setText(f"Page Background (current: {self.parent.settings['bg_color']})")
        self.text_color_btn.setText(f"Page Text (current: {self.parent.settings['text_color']})")
        self.custom_colors_toggle.setChecked(self.parent.settings['custom_colors'])
        QMessageBox.information(self, "Reset", "Settings reset to default.")

# -------------------------
# Main Browser
# -------------------------
class CustomBrowser(QMainWindow):
    DEFAULT_URL = "https://www.google.com"

    def __init__(self):
        super().__init__()

        # Paths
        self.settings_file = r"C:\PyBrowser\settings.json"
        self.passwords_path = r"C:\PyBrowser\Passwords"
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
        os.makedirs(self.passwords_path, exist_ok=True)

        # Settings & profile
        self.settings = self.load_settings()
        self.profile = QWebEngineProfile("PyBrowserProfile", self)

        # UI state
        self.history = []
        self.old_pos = None

        # Window setup
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setGeometry(100, 100, 1024, 768)

        self.main_layout = QVBoxLayout()

        # Top bar
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

        # Nav bar
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

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_title)
        self.main_layout.addWidget(self.tabs)

        # Central widget
        self.main_widget = QWidget()
        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)

        self.apply_gui_color()
        self.add_new_tab()

        # Drag window events
        self.top_bar.setMouseTracking(True)
        self.top_bar.mousePressEvent = self.mouse_press_event
        self.top_bar.mouseMoveEvent = self.mouse_move_event
        self.top_bar.mouseReleaseEvent = self.mouse_release_event

    # -------------------------
    # Settings
    # -------------------------
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

    # -------------------------
    # Password manager (multi-entry)
    # -------------------------
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
        # We expect console messages like: "PYBROWSER_LOGIN_CAPTURE:{"username":"...", "password":"..."}"
        prefix = "PYBROWSER_LOGIN_CAPTURE:"
        if isinstance(message, str) and message.startswith(prefix):
            try:
                payload = json.loads(message[len(prefix):])
                username = payload.get("username", "")
                password = payload.get("password", "")
                domain = browser.url().host()
                if username and password and domain:
                    self.prompt_save_credentials(domain, username, password)
            except Exception as e:
                # Ignore parse errors
                print("Login capture parse error:", e)

    def prompt_save_credentials(self, domain: str, username: str, password: str):
        file_path = self.passwords_file_for_domain(domain)

        # Load existing list (possibly empty)
        existing = []
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = []

        # If same username already exists -> ask how to proceed
        same_username = [e for e in existing if self.b64d(e.get("username_b64", "")) == username]

        if same_username:
            # If same username exists, ask Replace/Don't Save
            msg = QMessageBox(self)
            msg.setWindowTitle("Login Exists")
            msg.setText(f"A login with username \"{username}\" already exists for {domain}.\nWhat do you want to do?")
            replace_btn = msg.addButton("Replace Existing", QMessageBox.ButtonRole.AcceptRole)
            dont_btn = msg.addButton("Don't Save", QMessageBox.ButtonRole.RejectRole)
            cancel_btn = msg.addButton("Cancel", QMessageBox.ButtonRole.DestructiveRole)
            msg.exec()

            if msg.clickedButton() == dont_btn:
                return
            if msg.clickedButton() == replace_btn:
                # remove existing entries with same username
                existing = [e for e in existing if self.b64d(e.get("username_b64", "")) != username]
            else:
                # Cancel pressed
                return

        elif existing:
            # There are other entries with different usernames -> ask Replace All / Save as New / Don't Save
            msg = QMessageBox(self)
            msg.setWindowTitle("Multiple logins")
            msg.setText(f"Other logins already exist for {domain}. What do you want to do?")
            replace_all_btn = msg.addButton("Replace All", QMessageBox.ButtonRole.AcceptRole)
            save_new_btn = msg.addButton("Save as New", QMessageBox.ButtonRole.ActionRole)
            dont_btn = msg.addButton("Don't Save", QMessageBox.ButtonRole.RejectRole)
            msg.exec()

            if msg.clickedButton() == dont_btn:
                return
            elif msg.clickedButton() == replace_all_btn:
                existing = []  # wipe all
            # else Save as New -> keep existing entries and append below

        # Append new entry
        new_entry = {
            "username_b64": self.b64e(username),
            "password_b64": self.b64e(password)
        }
        existing.append(new_entry)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
        except Exception as e:
            print("Failed to save password file:", e)

    def maybe_offer_autofill(self, browser: QWebEngineView):
        domain = browser.url().host()
        file_path = self.passwords_file_for_domain(domain)
        if not os.path.exists(file_path):
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                entries = json.load(f)
            if not entries:
                return
        except Exception:
            return

        # If multiple, ask which username to use
        if len(entries) == 1:
            username = self.b64d(entries[0].get("username_b64", ""))
            password = self.b64d(entries[0].get("password_b64", ""))
        else:
            choices = [self.b64d(e.get("username_b64", "")) for e in entries]
            # Show a selection dialog
            username, ok = QInputDialog.getItem(self, "Choose login", f"Multiple logins found for {domain}. Select one:", choices, 0, False)
            if not ok or not username:
                return
            # find password for selected username
            match = next((e for e in entries if self.b64d(e.get("username_b64", "")) == username), None)
            if not match:
                return
            password = self.b64d(match.get("password_b64", ""))

        # Confirm autofill
        reply = QMessageBox.question(self, "Autofill?", f"Autofill saved login for {domain}?\n\nUsername: {username}", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            # Inject into common fields
            u_js = json.dumps(username)
            p_js = json.dumps(password)
            js = f"""
                (function(u, p) {{
                    let uSel = "input[type='email'],input[type='text'],input[name*=\\"user\\" i],input[name*=\\"email\\" i]";
                    let pSel = "input[type='password']";
                    let uInput = document.querySelector(uSel);
                    let pInput = document.querySelector(pSel);
                    if (uInput) uInput.value = u;
                    if (pInput) pInput.value = p;
                }})({u_js}, {p_js});
            """
            browser.page().runJavaScript(js)

    # -------------------------
    # Tab handling
    # -------------------------
    def add_new_tab(self, url=None):
        browser = QWebEngineView()
        page = QWebEnginePage(self.profile, browser)
        # Hook JS console messages so password capture from JS can reach python
        # Signature: javaScriptConsoleMessage(level, message, lineNumber, sourceID)
        # PyQt6 allows assigning a callable to page.javaScriptConsoleMessage
        page.javaScriptConsoleMessage = lambda level, message, line, source, b=browser: self.handle_console_message(level, message, line, source, b)
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
        # Apply custom colors
        self.inject_custom_colors(browser)
        # Inject password-capture JS
        self.inject_password_capture(browser)
        # Offer autofill (prompts if saved)
        self.maybe_offer_autofill(browser)

    def inject_custom_colors(self, browser: QWebEngineView):
        if not self.settings.get("custom_colors", False):
            return
        bg = self.settings.get("bg_color", DEFAULT_SETTINGS["bg_color"])
        text = self.settings.get("text_color", DEFAULT_SETTINGS["text_color"])
        js = f"""
            try {{
                document.documentElement.style.background = "{bg}";
                document.body.style.background = "{bg}";
                document.documentElement.style.color = "{text}";
                document.body.style.color = "{text}";
            }} catch(e) {{ /* ignore */ }}
        """
        browser.page().runJavaScript(js)

    def inject_password_capture(self, browser: QWebEngineView):
        # JavaScript that watches password fields and logs creds to console with a prefix
        js = r"""
            (function(){
                const prefix = "PYBROWSER_LOGIN_CAPTURE:";
                let last = {u:"", p:""};
                function capture(pwdField){
                    const form = pwdField.closest("form") || document;
                    let u = "";
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
                        try {
                            console.log(prefix + JSON.stringify({username:u, password:p}));
                        } catch(e) {}
                    }
                }
                function hook(){
                    const pwds = document.querySelectorAll("input[type='password']");
                    pwds.forEach(p => {
                        p.removeEventListener("blur", p._py_hook_blur);
                        p._py_hook_blur = () => capture(p);
                        p.addEventListener("blur", p._py_hook_blur);

                        p.removeEventListener("keydown", p._py_hook_keydown);
                        p._py_hook_keydown = (e) => { if(e.key==="Enter"){ capture(p); } };
                        p.addEventListener("keydown", p._py_hook_keydown);

                        p.removeEventListener("change", p._py_hook_change);
                        p._py_hook_change = () => capture(p);
                        p.addEventListener("change", p._py_hook_change);
                    });
                }
                hook();
                setTimeout(hook, 1200);
                setTimeout(hook, 4000);
            })();
        """
        browser.page().runJavaScript(js)

    # -------------------------
    # Title / Icon updates
    # -------------------------
    def update_tab_title(self, browser, title):
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if widget and widget.layout() and widget.layout().itemAt(0).widget() == browser:
                self.tabs.setTabText(i, title if title else "New Tab")
                break

    def update_tab_icon(self, browser, icon: QIcon):
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if widget and widget.layout() and widget.layout().itemAt(0).widget() == browser:
                self.tabs.setTabIcon(i, icon)
                break

    # -------------------------
    # Window movement / controls
    # -------------------------
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

    # -------------------------
    # Browser actions
    # -------------------------
    def go_back(self):
        self.tabs.currentWidget().layout().itemAt(0).widget().back()
    def go_forward(self):
        self.tabs.currentWidget().layout().itemAt(0).widget().forward()
    def reload_page(self):
        self.tabs.currentWidget().layout().itemAt(0).widget().reload()
    def go_home(self):
        self.tabs.currentWidget().layout().itemAt(0).widget().setUrl(QUrl(self.DEFAULT_URL))
    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
    def load_url(self):
        url = self.url_bar.text().strip()
        if not url.startswith("http"):
            url = "https://" + url
        self.tabs.currentWidget().layout().itemAt(0).widget().setUrl(QUrl(url))
        self.history.append(url)
    def update_url_bar(self, qurl):
        self.url_bar.setText(qurl.toString())
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

# -------------------------
# Startup
# -------------------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = CustomBrowser()
    window.show()
    sys.exit(app.exec())
