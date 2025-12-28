import sys
import os
import ctypes
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton,
    QLineEdit, QHBoxLayout, QLabel
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

class CustomBrowser(QMainWindow):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.top_bar.underMouse():
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos and event.buttons() == Qt.MouseButton.LeftButton:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None
    DEFAULT_URL = "https://pybrowser.mekabrine.space"

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setGeometry(100, 100, 1024, 768)
        self.main_layout = QVBoxLayout()

        # Custom top bar
        self.top_bar = QWidget()
        self.top_bar.setStyleSheet("background-color: #333; color: white; padding: 5px;")
        self.top_bar_layout = QHBoxLayout()
        self.top_bar_layout.setContentsMargins(5, 2, 5, 2)

        # Icon
        self.icon_label = QLabel()
        pixmap = QPixmap("C:\\Program Files\\PyBrowser\\Icon.ico").scaled(15, 15)
        self.icon_label.setPixmap(pixmap)
        self.top_bar_layout.addWidget(self.icon_label)
        
        # Browser Name
        self.title_label = QLabel("PyBrowser")
        self.title_label.setStyleSheet("font-size: 14px;")
        self.top_bar_layout.addWidget(self.title_label)
        self.top_bar_layout.addStretch()

        # Minimize Button
        self.minimize_button = QPushButton("➖")
        self.minimize_button.clicked.connect(self.showMinimized)
        self.top_bar_layout.addWidget(self.minimize_button)

        # Fullscreen Button
        self.fullscreen_button = QPushButton("⬜")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.top_bar_layout.addWidget(self.fullscreen_button)
        
        # Freeze Button
        self.freeze_button = QPushButton("⏸")
        self.freeze_button.clicked.connect(self.toggle_freeze)
        self.top_bar_layout.addWidget(self.freeze_button)

        self.top_bar.setLayout(self.top_bar_layout)
        self.main_layout.addWidget(self.top_bar)

        # Navigation Bar
        self.nav_bar = QWidget()
        self.nav_bar_layout = QHBoxLayout()
        self.back_button = QPushButton("◀")
        self.forward_button = QPushButton("▶")
        self.reload_button = QPushButton("⟳")
        self.url_bar = QLineEdit()
        self.new_tab_button = QPushButton("+ New Tab")
        self.back_button.clicked.connect(lambda: self.tabs.currentWidget().layout().itemAt(0).widget().back())
        self.forward_button.clicked.connect(lambda: self.tabs.currentWidget().layout().itemAt(0).widget().forward())
        self.reload_button.clicked.connect(lambda: self.tabs.currentWidget().layout().itemAt(0).widget().reload())
        self.url_bar.returnPressed.connect(self.load_url)
        self.new_tab_button.clicked.connect(self.add_new_tab)
        self.nav_bar_layout.addWidget(self.back_button)
        self.nav_bar_layout.addWidget(self.forward_button)
        self.nav_bar_layout.addWidget(self.reload_button)
        self.nav_bar_layout.addWidget(self.url_bar)
        self.nav_bar_layout.addWidget(self.new_tab_button)
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

    def add_new_tab(self, url=None):
        url = url or self.DEFAULT_URL
        new_tab = QWidget()
        layout = QVBoxLayout()
        webview = QWebEngineView()
        webview.setUrl(QUrl(url))
        webview.urlChanged.connect(self.update_url_bar)
        webview.titleChanged.connect(lambda title: self.tabs.setTabText(self.tabs.indexOf(new_tab), title))
        layout.addWidget(webview)
        new_tab.setLayout(layout)
        index = self.tabs.addTab(new_tab, "New Tab")
        self.tabs.setCurrentIndex(index)
        self.webview = webview

    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            self.add_new_tab(self.DEFAULT_URL)

    def load_url(self):
        url = self.url_bar.text().strip()
        if not url.startswith('http'):
            url = 'https://' + url
        self.tabs.currentWidget().layout().itemAt(0).widget().setUrl(QUrl(url))

    def update_url_bar(self, url):
        self.url_bar.setText(url.toString())

    def update_title(self):
        current_widget = self.tabs.currentWidget()
        if current_widget:
            self.setWindowTitle(self.tabs.tabText(self.tabs.currentIndex()) + " - PyBrowser")

    def toggle_freeze(self):
        self.is_frozen = not getattr(self, 'is_frozen', False)
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
