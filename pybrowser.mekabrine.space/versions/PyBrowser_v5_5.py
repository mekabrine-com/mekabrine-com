print('⟳ Loading PyBrowser v5')
print('❌ Broken cookies')

import sys
print('✔ Loaded sys')
import os
print('✔ Loaded os')
import json
print('✔ Loaded json')
import ctypes
print('✔ Loaded ctypes')
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton,
    QLineEdit, QHBoxLayout, QMenu, QFileDialog, QMessageBox, QColorDialog, QLabel
)
print('✔ Loaded QtWidgets')
from PyQt6.QtWebEngineWidgets import QWebEngineView
print('✔ Loaded QtWebEngineWidgets')
from PyQt6.QtWebEngineCore import QWebEngineProfile
print('✔ Loaded QtWebEngineCore')
from PyQt6.QtCore import QUrl
print('✔ Loaded QtCore')
from PyQt6.QtNetwork import QNetworkCookie
print('✔ Loaded QtNetwork')

def request_admin():
    if ctypes.windll.shell32.IsUserAnAdmin():
        print('✔ Already running as administrator')
        return
    print('❌ Attempting to run as administrator')
    ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, ' ' + ' '.join(sys.argv), None, 1)
    sys.exit(0)

request_admin()

PYBROWSER_DIR = 'C:\\Program Files\\PyBrowser'
SESSION_FILE = os.path.join(PYBROWSER_DIR, 'session.json')
SETTINGS_FILE = os.path.join(PYBROWSER_DIR, 'Settings', 'browser_settings.json')
PROFILE_DIR = os.path.join(PYBROWSER_DIR, 'UserData')
COOKIE_STORAGE_PATH = os.path.join(PYBROWSER_DIR, 'Cookies')
os.makedirs(COOKIE_STORAGE_PATH, exist_ok=True)
os.makedirs(PROFILE_DIR, exist_ok=True)
DEFAULT_TAB_URL = 'https://pybrowser.mekabrine.space'
print('✔ Loaded paths')

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'background_color': '#ffffff', 'pref_name': 'User'}

print('✔ defined load_settings')

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)

print('✔ defined save_settings')

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

        self.back_button.clicked.connect(lambda: self.webview.back())
        self.forward_button.clicked.connect(lambda: self.webview.forward())
        self.reload_button.clicked.connect(lambda: self.webview.reload())
        self.url_bar.returnPressed.connect(self.load_url)
        self.menu_button.clicked.connect(self.show_menu)

        self.toolbar.addWidget(self.back_button)
        self.toolbar.addWidget(self.forward_button)
        self.toolbar.addWidget(self.reload_button)
        self.toolbar.addWidget(self.url_bar)
        self.toolbar.addWidget(self.menu_button)

        self.webview = QWebEngineView(self)

        # Create a persistent profile
        profile = QWebEngineProfile.defaultProfile()
        profile.setPersistentStoragePath(PROFILE_DIR)  # Store session data here
        profile.setCachePath(PROFILE_DIR)  # Store cache here
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)  # Keep cookies across restarts
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)  # Use disk cache for performance

        # Enable local storage to ensure data persistence
        settings = profile.settings()
        settings.setAttribute(settings.WebAttribute.LocalStorageEnabled, True)  # Enable local storage
        settings.setAttribute(settings.WebAttribute.PluginsEnabled, True)  # Enable plugins
        settings.setAttribute(settings.WebAttribute.JavascriptCanOpenWindows, True)  # Allow popups
        settings.setAttribute(settings.WebAttribute.JavascriptCanAccessClipboard, True)  # Allow clipboard access

        print(f'✔ Persistent user data stored in: {PROFILE_DIR}')

        self.webview.titleChanged.connect(self.update_tab_title)
        self.webview.urlChanged.connect(self.update_url_bar)

        self.layout.addLayout(self.toolbar)
        self.layout.addWidget(self.webview)
        self.setLayout(self.layout)

        self.webview.setUrl(QUrl(DEFAULT_TAB_URL))
        print('✔ defined BrowserTab')

    def load_url(self):
        url = self.url_bar.text().strip()
        if not url.startswith('http'):
            url = 'https://' + url
        self.webview.setUrl(QUrl(url))
        print('✔ defined load_url')

    def update_tab_title(self, title):
        tab_widget = self.parentWidget().parentWidget()
        index = tab_widget.indexOf(self)
        if index != -1:
            tab_widget.setTabText(index, title)
        print('✔ defined update_tab_title')

    def update_url_bar(self, url):
        self.url_bar.setText(url.toString())
        print('✔ defined update_url_bar')

    def show_menu(self):
        menu = QMenu(self)
        parent_window = self.window()
        menu.addAction('Settings', parent_window.open_settings)
        menu.exec(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))
        print('✔ defined show_menu')

class CustomBrowser(QMainWindow):
    def open_settings(self):
        color = QColorDialog.getColor()
        if color.isValid():
            settings['background_color'] = color.name()
            save_settings(settings)
            self.setStyleSheet(f'background-color: {settings['background_color']};')

    def __init__(self):
        super().__init__()
        self.setWindowTitle('PyBrowser')
        self.setGeometry(100, 100, 1024, 768)
        self.setStyleSheet(f'background-color: {settings['background_color']};')

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

        self.add_new_tab()

    def add_new_tab(self, url=None):
        new_tab = BrowserTab(self.tabs)
        index = self.tabs.addTab(new_tab, 'New Tab')
        self.tabs.setCurrentIndex(index)
        if url:
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
        print('\n❓ The initial startup and tab loading might take a bit to load, this is because your cookies are loading, the more cookies you have, the slower this will load.\n(the initial tab may fail to load, if so, just reload it)')
        for file in os.listdir(COOKIE_STORAGE_PATH):
            with open(os.path.join(COOKIE_STORAGE_PATH, file), "r", encoding="utf-8") as f:
                for line in f:
                    cookie = QNetworkCookie.parseCookies(line.strip().encode())
                    if cookie:
                        self.cookie_store.setCookie(cookie[0])

print('✔ Loaded CustomBrowser')


if __name__ == '__main__':
    print('✔ Starting PyBrowser\n\n')
    print(' __  __           _        _             __  __      _')
    print('|  \/  |  __   __| | ___  | |__  _   _  |  \/  | ___| | ____ _   _ _ __')
    print('| |\/| |/ _  |/ _  |/ _ \ |  _ \| | | | | |\/| |/ _ \ |/ /  _ | (_)  _ \ ')
    print('| |  | | (_| | (_| |  __/ | |_) | |_| | | |  | |  __/   < (_| |  _| |_) |')
    print('|_|  |_|\__,_|\__,_|\___| |_.__/ \__, | |_|  |_|\___|_|\_\__,_| (_) .__/')
    print('                                  |___/                            |_|\n')
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = CustomBrowser()
    window.show()
    print('\n✔ PyBrowser Started\n')
    sys.exit(app.exec())
