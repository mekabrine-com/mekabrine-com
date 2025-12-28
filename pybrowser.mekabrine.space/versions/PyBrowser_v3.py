print('Working cookies')

import sys
print('Loaded part...')
import os
print('Loaded part...')
import json
print('Loaded part...')
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton, 
    QLineEdit, QHBoxLayout, QProgressBar, QMenu, QColorDialog
)
print('Loaded part...')
from PyQt6.QtWebEngineWidgets import QWebEngineView
print('Loaded part...')
from PyQt6.QtCore import QUrl, QPoint, Qt
print('Loaded part...')
from PyQt6.QtGui import QAction, QColor, QCursor
print('Loaded part...')
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineCookieStore
print('Loaded part...')
from PyQt6.QtNetwork import QNetworkCookie
print('Loaded part...')

# Configuration constants
SETTINGS_FILE = "browser_settings.json"
COOKIE_STORAGE_PATH = "C:\\Program Files\\PyBrowser\\Cookies"
DEFAULT_TAB_URL = "https://pybrowser.mekabrine.space/"

# Ensure the cookie storage directory exists
if not os.path.exists(COOKIE_STORAGE_PATH):
    os.makedirs(COOKIE_STORAGE_PATH)

class BrowserTab(QWidget):
    def show_context_menu(self, position: QPoint):
        menu = QMenu(self)

        back_action = QAction("B<ck", self)
        back_action.triggered.connect(self.webview.back)
        menu.addAction(back_action)

        forward_action = QAction("F>rward", self)
        forward_action.triggered.connect(self.webview.forward)
        menu.addAction(forward_action)

        reload_action = QAction("Rel⟳ad", self)
        reload_action.triggered.connect(self.webview.reload)
        menu.addAction(reload_action)

        menu.addSeparator()

        self.webview.page().runJavaScript("window.getSelection().toString()", self.handle_selected_text)
        menu.exec(self.mapToGlobal(position))

    def handle_selected_text(self, text):
        if text and text.startswith("http"):
            hovered_url = QUrl(text)
            open_tab_action = QAction(f"Open {hovered_url.toString()} in new tab", self)
            open_tab_action.triggered.connect(lambda: self.parentWidget().parentWidget().add_new_tab(hovered_url))
            self.show_context_menu_action(open_tab_action)

    def show_context_menu_action(self, action):
        menu = QMenu(self)
        menu.addAction(action)
        menu.exec(QCursor.pos())
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)

        # Progress bar for page loading status
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                height: 1px;
                background: transparent;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 lightblue, stop: 1 blue);
            }
        """)

        # URL input field
        self.url_bar = QLineEdit(self)
        self.url_bar.returnPressed.connect(self.load_url)

        # Web view for displaying webpages
        self.webview = QWebEngineView(self)
        self.webview.setUrl(QUrl(DEFAULT_TAB_URL))
        self.webview.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.webview.customContextMenuRequested.connect(self.show_context_menu)

        # Navigation buttons
        self.nav_layout = QHBoxLayout()
        self.back_btn = QPushButton("B<ck")
        self.forward_btn = QPushButton("F>rward")
        self.reload_btn = QPushButton("Rel⟳ad")

        self.back_btn.clicked.connect(self.webview.back)
        self.forward_btn.clicked.connect(self.webview.forward)
        self.reload_btn.clicked.connect(self.webview.reload)

        # Arrange navigation elements
        self.nav_layout.addWidget(self.back_btn)
        self.nav_layout.addWidget(self.forward_btn)
        self.nav_layout.addWidget(self.reload_btn)
        self.nav_layout.addWidget(self.url_bar)

        # Set layout structure
        self.layout.addLayout(self.nav_layout)
        self.layout.addWidget(self.progress_bar)
        self.layout.addWidget(self.webview)
        self.setLayout(self.layout)

        # Connect web events to update UI
        self.webview.urlChanged.connect(self.update_url)
        self.webview.titleChanged.connect(self.update_tab_title)
        self.webview.loadProgress.connect(self.update_progress)
        self.webview.loadFinished.connect(self.hide_progress_bar)

    def load_url(self):
        url = self.url_bar.text().strip()
        if not url.startswith("http"):
            url = "https://" + url
        self.webview.setUrl(QUrl(url))

    def update_url(self, url):
        self.url_bar.setText(url.toString())

    def update_tab_title(self, title):
        tab_widget = self.parentWidget().parentWidget()
        if isinstance(tab_widget, QTabWidget):
            index = tab_widget.indexOf(self)
            if index != -1:
                tab_widget.setTabText(index, title)

    def update_progress(self, progress):
        self.progress_bar.setValue(progress)
        self.progress_bar.show()

    def hide_progress_bar(self):
        self.progress_bar.hide()
print('Loaded BrowserTab...')

class CustomBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyBrowser")
        self.setGeometry(100, 100, 1024, 768)

        profile = QWebEngineProfile.defaultProfile()
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.cookie_store = profile.cookieStore()
        self.cookie_store.cookieAdded.connect(self.save_cookie)
        
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        self.toolbar_widget = QWidget()
        self.toolbar_layout = QHBoxLayout(self.toolbar_widget)

        self.new_tab_button = QPushButton("+ New Tab")
        self.new_tab_button.clicked.connect(lambda: self.add_new_tab(DEFAULT_TAB_URL))
        self.toolbar_layout.addWidget(self.new_tab_button)

        self.settings_button = QPushButton("⚙ Settings")
        self.settings_button.clicked.connect(self.open_settings)
        self.toolbar_layout.addWidget(self.settings_button)

        self.central_layout = QVBoxLayout()
        self.central_layout.addWidget(self.toolbar_widget)
        self.central_layout.addWidget(self.tabs)

        self.central_widget = QWidget()
        self.central_widget.setLayout(self.central_layout)
        self.setCentralWidget(self.central_widget)

        self.load_cookies()  # Load cookies before opening any tabs
        self.add_new_tab(DEFAULT_TAB_URL)  # Ensure the first tab loads a default page

    def add_new_tab(self, url=DEFAULT_TAB_URL):
        new_tab = BrowserTab(self.tabs)
        index = self.tabs.addTab(new_tab, "Loading...")
        self.tabs.setCurrentIndex(index)
        new_tab.webview.setUrl(QUrl(url))


    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            self.close()

    def open_settings(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.setStyleSheet(f"background-color: {color.name()};")

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
print('Loaded CustomBrowser...')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    print('Loaded part...')

    app.setStyle("Fusion")
    print('Creating window ui...')
    print('(This can take up to a few minutes)')


    window = CustomBrowser()
    print('Creating window display...')

    window.show()
    print('Loaded Window...')
    os.system('cls')
    print('Made by Meka :p (https://mekabrine.space)\nPyBrowser Ready to go! have fun browsing :D\n(The initial page might take a while to load, after that, everything loads fast!)')
    sys.exit(app.exec())
