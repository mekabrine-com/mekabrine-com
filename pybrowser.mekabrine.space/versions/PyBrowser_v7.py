print('⟳ Loading PyBrowser v6')

import sys
import os
import json
import ctypes
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton,
    QLineEdit, QHBoxLayout, QMenu, QColorDialog, QListWidget, QCheckBox, QMessageBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineCookieStore, QWebEnginePage
from PyQt6.QtCore import QUrl
from PyQt6.QtNetwork import QNetworkCookie

def request_admin():
    if ctypes.windll.shell32.IsUserAnAdmin():
        return
    ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, ' ' + ' '.join(sys.argv), None, 1)
    sys.exit(0)

request_admin()

PYBROWSER_DIR = 'C:\\Program Files\\PyBrowser'
COOKIE_STORAGE_PATH = os.path.join(PYBROWSER_DIR, 'Cookies')
SETTINGS_PATH = os.path.join(PYBROWSER_DIR, 'Settings.json')
os.makedirs(COOKIE_STORAGE_PATH, exist_ok=True)
DEFAULT_TAB_URL = 'https://pybrowser.mekabrine.space'

def load_settings():
    default_settings = {'browser_color': '#ffffff'}
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, 'r') as f:
                settings = json.load(f)
                return {**default_settings, **settings}  # Ensure default values exist
        except json.JSONDecodeError:
            pass  # Handle corrupted file
    return default_settings

def save_settings(settings):
    with open(SETTINGS_PATH, 'w') as f:
        json.dump(settings, f)

settings = load_settings()

class BrowserTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.toolbar = QHBoxLayout()
        
        self.back_button = QPushButton('◀')
        self.forward_button = QPushButton('▶')
        self.reload_button = QPushButton('⟳')
        self.url_bar = QLineEdit(self)
        self.menu_button = QPushButton('⋮')
        
        self.back_button.setFixedSize(25, 25)
        self.forward_button.setFixedSize(25, 25)
        
        self.back_button.clicked.connect(lambda: self.webview.back())
        self.forward_button.clicked.connect(lambda: self.webview.forward())
        self.reload_button.clicked.connect(lambda: self.webview.reload())
        self.url_bar.returnPressed.connect(self.load_url)
        
        self.toolbar.addWidget(self.back_button)
        self.toolbar.addWidget(self.forward_button)
        self.toolbar.addWidget(self.reload_button)
        self.toolbar.addWidget(self.url_bar)
        self.toolbar.addWidget(self.menu_button)
        
        self.webview = QWebEngineView(self)
        self.webview.page().titleChanged.connect(self.update_tab_title)
        self.webview.page().iconChanged.connect(self.update_tab_icon)
        self.webview.urlChanged.connect(self.update_url_bar)
        
        self.layout.addLayout(self.toolbar)
        self.layout.addWidget(self.webview)
        self.setLayout(self.layout)
        
        self.webview.setUrl(QUrl(DEFAULT_TAB_URL))
    
    def load_url(self):
        url = self.url_bar.text().strip()
        if not url.startswith('http'):
            url = 'https://' + url
        self.webview.setUrl(QUrl(url))
    
    def update_tab_title(self, title):
        index = self.parent().indexOf(self)
        self.parent().setTabText(index, title)
    
    def update_tab_icon(self, icon):
        index = self.parent().indexOf(self)
        self.parent().setTabIcon(index, icon)
    
    def update_url_bar(self, url):
        self.url_bar.setText(url.toString())

class CustomBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('PyBrowser')
        self.setGeometry(100, 100, 1024, 768)
        self.setStyleSheet(f'background-color: {settings["browser_color"]};')
        
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        
        self.new_tab_button = QPushButton('+ New Tab')
        self.new_tab_button.clicked.connect(self.add_new_tab)
        
        self.toolbar_layout = QHBoxLayout()
        self.toolbar_layout.addWidget(self.new_tab_button)
        
        self.central_layout = QVBoxLayout()
        self.central_layout.addLayout(self.toolbar_layout)
        self.central_layout.addWidget(self.tabs)
        
        self.central_widget = QWidget()
        self.central_widget.setLayout(self.central_layout)
        self.setCentralWidget(self.central_widget)
        
        self.profile = QWebEngineProfile.defaultProfile()
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.cookie_store = self.profile.cookieStore()
        self.cookie_store.cookieAdded.connect(self.save_cookie)
        self.load_cookies()
        
        self.add_new_tab()
        self.setup_menu()
    
    def add_new_tab(self, url=DEFAULT_TAB_URL):
        new_tab = BrowserTab(self.tabs)
        index = self.tabs.addTab(new_tab, 'New Tab')
        self.tabs.setCurrentIndex(index)
        new_tab.webview.setUrl(QUrl(url))
    
    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            self.close()
    
    def save_cookie(self, cookie):
        domain = cookie.domain()
        cookie_file = os.path.join(COOKIE_STORAGE_PATH, f"{domain}.txt")
        with open(cookie_file, "a", encoding="utf-8") as f:
            f.write(cookie.toRawForm().data().decode() + "\n")
    
    def load_cookies(self):
        for file in os.listdir(COOKIE_STORAGE_PATH):
            with open(os.path.join(COOKIE_STORAGE_PATH, file), "r", encoding="utf-8") as f:
                for line in f:
                    cookie = QNetworkCookie.parseCookies(line.strip().encode())
                    if cookie:
                        self.cookie_store.setCookie(cookie[0])

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = CustomBrowser()
    window.show()
    sys.exit(app.exec())
