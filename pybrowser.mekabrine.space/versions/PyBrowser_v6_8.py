import hashlib
from PyQt6.QtWebEngineCore import QWebEngineCookieStore, QWebEngineProfile
from PyQt6.QtWidgets import QMessageBox
import json
import sys
import os
import ctypes
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton,
    QLineEdit, QHBoxLayout, QLabel, QMenu, QListWidget, QDialog
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, Qt, QPoint
from PyQt6.QtGui import QIcon, QPixmap

def request_admin():
    if ctypes.windll.shell32.IsUserAnAdmin():
        return
    ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, ' ' + ' '.join(sys.argv), None, 1)
    sys.exit(0)

request_admin()

class HistoryPopup(QDialog):
    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.setWindowTitle("History")
        self.setGeometry(200, 200, 400, 300)
        layout = QVBoxLayout()
        
        self.list_widget = QListWidget()
        self.history = history
        self.list_widget.addItems(history)
        layout.addWidget(self.list_widget)
        
        self.setLayout(layout)

class CustomBrowser(QMainWindow):
    DEFAULT_URL = "https://pybrowser.mekabrine.space/browser/"

    def __init__(self):
        self.autofill_path = r"C:\Program Files\PyBrowser\Autofills"
        os.makedirs(self.autofill_path, exist_ok=True)
        


        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setGeometry(100, 100, 1024, 768)
        self.history = []
        self.cookies_path = r"C:\Program Files\PyBrowser\Cookies"
        os.makedirs(self.cookies_path, exist_ok=True)
        self.is_frozen = False
        self.main_layout = QVBoxLayout()
        self.old_pos = None
        
        # Custom top bar
        self.top_bar = QWidget()
        self.top_bar.setStyleSheet("background-color: #333; color: white; padding: 5px;")
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
        
        self.freeze_button = QPushButton("⏸")
        self.freeze_button.clicked.connect(self.toggle_freeze)
        self.top_bar_layout.addWidget(self.freeze_button)
        
        self.top_bar.setLayout(self.top_bar_layout)
        self.main_layout.addWidget(self.top_bar)
        
        # Navigation Bar
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
        
        # Browser Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_title)
        self.main_layout.addWidget(self.tabs)
        
        self.main_widget = QWidget()
        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)
        self.add_new_tab()

        # Add mouse event handling to enable dragging
        self.top_bar.setMouseTracking(True)
        self.top_bar.mousePressEvent = self.mouse_press_event
        self.top_bar.mouseMoveEvent = self.mouse_move_event
        self.top_bar.mouseReleaseEvent = self.mouse_release_event


    def handle_console_message(self, msg, browser):
        prefix = "PYBROWSER_LOGIN_CAPTURE:"
        if msg.startswith(prefix):
            try:
                login_data = json.loads(msg[len(prefix):])
                domain = browser.url().host()
                file_path = os.path.join(self.autofill_path, f"{domain}.json")

                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        saved = json.load(f)
                        if saved.get("username") == login_data["username"]:
                            return  # already saved

                reply = QMessageBox.question(
                    self, "Save Login?",
                    f"Save login for {domain}?\n\nUsername: {login_data['username']}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(login_data, f, indent=2)
                    print(f"Login saved for {domain}")
            except Exception as e:
                print("Login capture error:", e)


        
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
    
    def add_new_tab(self, url=None):
        browser = QWebEngineView()
        browser.page().javaScriptConsoleMessage = lambda lvl, msg, line, src: self.handle_console_message(msg, browser)
        default_url = QUrl(url) if url else QUrl(self.DEFAULT_URL)

        def on_page_load_finished():
            js_script = """
            (() => {
                let last = { username: "", password: "" };

                const captureLogin = (pwdField) => {
                    let password = pwdField.value;
                    let form = pwdField.closest("form") || document;
                    let username = "";

                    const inputs = form.querySelectorAll("input");
                    inputs.forEach(input => {
                        const type = input.type.toLowerCase();
                        if ((type === "text" || type === "email") && !username && input.value.length > 2) {
                            username = input.value;
                        }
                    });

                    if (username && password && (username !== last.username || password !== last.password)) {
                        last = { username, password };
                        console.log("PYBROWSER_LOGIN_CAPTURE:" + JSON.stringify(last));
                    }
                };

                const observe = () => {
                    document.querySelectorAll("input[type='password']").forEach(pwdField => {
                        pwdField.addEventListener("blur", () => captureLogin(pwdField));
                        pwdField.addEventListener("keydown", e => {
                            if (e.key === "Enter") {
                                captureLogin(pwdField);
                            }
                        });
                    });
                };

                // Run now and again later in case page loads late
                observe();
                setTimeout(observe, 2000);
                setTimeout(observe, 5000);
            })();
            """
            browser.page().runJavaScript(js_script)

        browser.loadFinished.connect(on_page_load_finished)

        browser.setUrl(default_url)
        browser.loadFinished.connect(on_page_load_finished)


        browser.titleChanged.connect(lambda title, br=browser: self.update_tab_title(br, title))
        browser.iconChanged.connect(lambda icon, br=browser: self.update_tab_icon(br, icon))
        browser.urlChanged.connect(self.update_url_bar)

        tab = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(browser)
        tab.setLayout(layout)

        index = self.tabs.addTab(tab, "Loading...")
        self.tabs.setCurrentIndex(index)


    def update_tab_title(self, browser, title):
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).layout().itemAt(0).widget() == browser:
                self.tabs.setTabText(i, title)
                break
    
    def update_tab_icon(self, browser, icon):
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).layout().itemAt(0).widget() == browser:
                self.tabs.setTabIcon(i, icon)
                break
    
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
        if not url.startswith('http'):
            url = 'https://' + url
        self.tabs.currentWidget().layout().itemAt(0).widget().setUrl(QUrl(url))
        self.history.append(url)
    
    def update_url_bar(self, url):
        self.url_bar.setText(url.toString())
    
    def update_title(self):
        current_widget = self.tabs.currentWidget()
        if current_widget:
            self.setWindowTitle(self.tabs.tabText(self.tabs.currentIndex()) + " - PyBrowser")
    
    def open_menu(self):
        menu = QMenu(self)
        history_action = menu.addAction("History")
        settings_action = menu.addAction("Settings (Coming Soon)")
        history_action.triggered.connect(self.show_history)
        menu.exec(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))
    
    def show_history(self):
        self.history_popup = HistoryPopup(self.history, self)
        self.history_popup.show()
    
    def toggle_freeze(self):
        self.is_frozen = not self.is_frozen
        self.freeze_button.setText("Paused" if self.is_frozen else "⏸")
        for widget in [self.tabs, self.nav_bar]:
            widget.setEnabled(not self.is_frozen)
        self.freeze_button.setEnabled(True)
        self.main_widget.setStyleSheet("background: rgba(0, 0, 0, 0.5);" if self.is_frozen else "")
    
    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = CustomBrowser()
    window.show()
    sys.exit(app.exec())
