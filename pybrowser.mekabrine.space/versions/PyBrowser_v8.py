print('⟳ Loading PyBrowser v6')

import sys
print('✔ Loaded sys')
import os
print('✔ Loaded os')
import json
print('✔ Loaded json')
import ctypes
print('✔ Loaded ctypes')
print('❓ If it crashes here, open command prompt and type\n\npython3 -m pip install Pyqt6\n')
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton,
    QLineEdit, QHBoxLayout, QMenu, QColorDialog
)
print('✔ Loaded QtWidgets')
from PyQt6.QtWebEngineWidgets import QWebEngineView
print('✔ Loaded QtWebEngineWidgets')
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineCookieStore
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
COOKIE_STORAGE_PATH = os.path.join(PYBROWSER_DIR, 'Cookies')
os.makedirs(COOKIE_STORAGE_PATH, exist_ok=True)
DEFAULT_TAB_URL = 'https://pybrowser.mekabrine.space'
print('✔ Loaded paths')

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

        self.toolbar.addWidget(self.back_button)
        self.toolbar.addWidget(self.forward_button)
        self.toolbar.addWidget(self.reload_button)
        self.toolbar.addWidget(self.url_bar)
        self.toolbar.addWidget(self.menu_button)

        self.webview = QWebEngineView(self)
        self.layout.addLayout(self.toolbar)
        self.layout.addWidget(self.webview)
        self.setLayout(self.layout)

        self.webview.setUrl(QUrl(DEFAULT_TAB_URL))

    def load_url(self):
        url = self.url_bar.text().strip()
        if not url.startswith('http'):
            url = 'https://' + url
        self.webview.setUrl(QUrl(url))
print('✔ Loaded BrowserTab')

class CustomBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('PyBrowser')
        self.setGeometry(100, 100, 1024, 768)

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

    def add_new_tab(self, url=DEFAULT_TAB_URL):
        if not isinstance(url, str) or not url:
            url = DEFAULT_TAB_URL  # Ensure a valid string URL
    
        new_tab = BrowserTab(self.tabs)
        index = self.tabs.addTab(new_tab, 'New Tab')
        self.tabs.setCurrentIndex(index)
        new_tab.webview.setUrl(QUrl(url))  # Now always a valid string

    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            self.close()

    def save_cookie(self, cookie):
        domain = cookie.domain()
        cookie_file = os.path.join(COOKIE_STORAGE_PATH, f"{domain}.txt")
        
        # Delete the existing file before saving a new cookie
        if os.path.exists(cookie_file):
            os.remove(cookie_file)
        
        with open(cookie_file, "w", encoding="utf-8") as f:  # Use 'w' to overwrite
            f.write(cookie.toRawForm().data().decode() + "\n")

    def load_cookies(self):
        print('⟳ Loading Cookies')
        print('\n❓ The initial startup and tab loading might take a bit to load, this is because your cookies are loading, the more cookies you have, the slower this will load.\n(the initial tab may fail to load, if so, just reload it)')
        for file in os.listdir(COOKIE_STORAGE_PATH):
            with open(os.path.join(COOKIE_STORAGE_PATH, file), "r", encoding="utf-8") as f:
                for line in f:
                    cookie = QNetworkCookie.parseCookies(line.strip().encode())
                    if cookie:
                        self.cookie_store.setCookie(cookie[0])
print('✔ Loaded CustomBrowser')

if __name__ == '__main__':
    print('⟳ Starting PyBrowser v6\n\n')
    print(' __  __           _        _             __  __      _')
    print('|  \/  |  __   __| | ___  | |__  _   _  |  \/  | ___| | ____ _   _ _ __')
    print('| |\/| |/ _  |/ _  |/ _ \ |  _ \| | | | | |\/| |/ _ \ |/ /  _ | (_)  _ \ ')
    print('| |  | | (_| | (_| |  __/ | |_) | |_| | | |  | |  __/   < (_| |  _| |_) |')
    print('|_|  |_|\__,_|\__,_|\___| |_.__/ \__, | |_|  |_|\___|_|\_\__,_| (_) .__/')
    print('                                  |___/                           |_|\n')
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = CustomBrowser()
    window.show()
    sys.exit(app.exec())
