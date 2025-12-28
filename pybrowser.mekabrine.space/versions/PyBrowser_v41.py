import sys, os, json, ctypes
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEnginePage,
    QWebEngineSettings,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton,
    QLineEdit, QHBoxLayout, QLabel, QMenu, QMessageBox, QProgressBar, QTabBar,
    QComboBox, QDialog, QDialogButtonBox, QColorDialog, QCheckBox, QFileDialog,
    QGraphicsBlurEffect
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import (
    QUrl, Qt, QTimer, QMimeData, QByteArray, QRect, QEvent
)
from PyQt6.QtGui import (
    QIcon, QDrag, QColor, QCursor, QPainter, QPixmap
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
    "kill_ai": False,
    "downloads_dir": r"C:\PyBrowser\Downloads",
    # permissions
    "permissions_default": {
        "location": "block",
        "camera": "block",
        "microphone": "block",
        "screenshare": "block",
    },
    "site_permissions": {},   # { host: { "location": "allow/block", "camera": "...", "microphone": "...", "screenshare": "..." } }
    "view_style": "none",     # none, bw, invert, cracked
    # legacy bookmarks (kept for migration, main data is bookmarks.json)
    "bookmarks": [],
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
# Bookmark button
# -------------------------
class BookmarkButton(QPushButton):
    def __init__(self, title: str, url: str, parent=None, icon: QIcon | None = None):
        super().__init__("", parent)
        self.title = title
        self.url = url
        self.first_word = title.split()[0] if title.strip() else ""
        self.has_icon = icon is not None and not icon.isNull()

        if self.has_icon:
            self.setIcon(icon)
            self.setText("")
        else:
            self.setText(self.first_word)

        self.setToolTip(title)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setMinimumWidth(24)
        self.setMaximumWidth(160)
        self.setFixedHeight(22)

    def enterEvent(self, event):
        self.setText(self.title)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.has_icon:
            self.setText("")
        else:
            self.setText(self.first_word)
        super().leaveEvent(event)


# -------------------------
# Bookmark bar with drag-reorder
# -------------------------
class BookmarkBar(QWidget):
    def __init__(self, browser, parent=None):
        super().__init__(parent)
        self.browser = browser
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 5, 0)
        self.layout.setSpacing(4)
        self.layout.addStretch(1)
        self.buttons: list[BookmarkButton] = []

        self._drag_button: BookmarkButton | None = None
        self._drag_start_pos = None
        self._dragging = False
        self._drag_threshold = 6

    def clear_buttons(self):
        for btn in self.buttons:
            btn.removeEventFilter(self)
            btn.setParent(None)
        self.buttons = []
        while self.layout.count():
            item = self.layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        self.layout.addStretch(1)

    def set_bookmarks(self, bookmarks: list[dict]):
        self.clear_buttons()
        for bm in bookmarks:
            title = bm.get("title", bm.get("url", ""))
            url = bm.get("url", "")
            icon = None
            icon_path = bm.get("icon_path")
            if icon_path and os.path.exists(icon_path):
                icon = QIcon(icon_path)
            btn = BookmarkButton(title, url, self, icon=icon)
            btn.installEventFilter(self)
            btn.clicked.connect(lambda checked=False, u=url: self.browser.activate_bookmark(u))
            self.layout.insertWidget(self.layout.count() - 1, btn)
            self.buttons.append(btn)

    def eventFilter(self, obj, event):
        if isinstance(obj, BookmarkButton):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_button = obj
                self._drag_start_pos = obj.mapToParent(event.pos())
                self._dragging = False
                return False
            elif event.type() == QEvent.Type.MouseMove and self._drag_button is obj and (event.buttons() & Qt.MouseButton.LeftButton):
                pos = obj.mapToParent(event.pos())
                if (pos - self._drag_start_pos).manhattanLength() > self._drag_threshold:
                    self._dragging = True
                    self.handle_drag_move(pos.x())
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease and self._drag_button is obj:
                if self._dragging:
                    self._drag_button = None
                    self._dragging = False
                    self.browser.on_bookmarks_reordered(self.buttons)
                    return True
                else:
                    self._drag_button = None
                    self._dragging = False
                    return False
        return super().eventFilter(obj, event)

    def handle_drag_move(self, x_in_bar: int):
        if not self._drag_button:
            return
        if len(self.buttons) < 2:
            return

        current_index = self.buttons.index(self._drag_button)
        new_index = current_index

        for i, btn in enumerate(self.buttons):
            if btn is self._drag_button:
                continue
            center_x = btn.geometry().center().x()
            if x_in_bar < center_x:
                new_index = i
                break
            new_index = i

        if new_index == current_index:
            return

        self.buttons.pop(current_index)
        self.buttons.insert(new_index, self._drag_button)

        self.layout.removeWidget(self._drag_button)
        self.layout.insertWidget(new_index, self._drag_button)
        self.layout.update()


# -------------------------
# TabBar with context menu + DnD + hover ❌
# -------------------------
class DragSafeTabBar(QTabBar):
    _drag_source = None  # (source_window, index)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self._press_pos = None
        self._pressed_index = -1
        self._drag_threshold = 6
        self._hover_tab = -1
        self._close_rects = {}
        self._external_drag_started = False

        self.setAcceptDrops(True)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            idx = self.tabAt(e.pos())
            if idx >= 0:
                rect = self._close_rects.get(idx)
                if rect is not None and rect.contains(e.pos()):
                    browser_window = self.find_browser_window()
                    if browser_window:
                        browser_window.close_tab(idx)
                    return
            self._press_pos = e.pos()
            self._pressed_index = self.tabAt(e.pos())
            self._external_drag_started = False
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._press_pos and (e.buttons() & Qt.MouseButton.LeftButton) and self._pressed_index >= 0:
            dist = (e.pos() - self._press_pos).manhattanLength()
            if dist > self._drag_threshold:
                if not self.rect().contains(e.pos()) and not self._external_drag_started:
                    self._external_drag_started = True
                    self.start_drag(self._pressed_index)
                    return
        self._hover_tab = self.tabAt(e.pos())
        self.update()
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._press_pos = None
        self._pressed_index = -1
        self._external_drag_started = False
        super().mouseReleaseEvent(e)

    def leaveEvent(self, event):
        self._hover_tab = -1
        self.update()
        super().leaveEvent(event)

    def start_drag(self, index: int):
        window = self.find_browser_window()
        if window is None:
            return

        DragSafeTabBar._drag_source = (window, index)

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-pybrowser-tab", QByteArray(b"tab"))
        drag.setMimeData(mime)
        result = drag.exec(Qt.DropAction.MoveAction)

        if result != Qt.DropAction.MoveAction:
            if index < window.tabs.count():
                window.detach_tab(index)

        DragSafeTabBar._drag_source = None
        self._external_drag_started = False

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

        pos = event.position().toPoint()
        dest_index = self.tabAt(pos)
        if dest_index < 0:
            dest_index = dest_window.tabs.count()

        if source_window is dest_window:
            source_window.move_tab_within(src_index, dest_index)
        else:
            source_window.move_tab_to_other_window(src_index, dest_window, dest_index)

        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def find_browser_window(self):
        parent = self.parent()
        while parent is not None:
            if parent.__class__.__name__ == "CustomBrowser":
                return parent
            parent = parent.parent()
        return None

    def show_context_menu(self, pos):
        idx = self.tabAt(pos)
        if idx < 0:
            return
        browser_window = self.find_browser_window()
        if not browser_window:
            return

        suspended = browser_window.is_tab_suspended(idx)

        menu = QMenu(self)
        action_refresh = menu.addAction("Refresh Tab")
        action_close = menu.addAction("Close Tab")
        action_suspend = menu.addAction("Resume Tab" if suspended else "Suspend Tab")
        action = menu.exec(self.mapToGlobal(pos))

        if action == action_refresh:
            browser_window.refresh_tab(idx)
        elif action == action_close:
            browser_window.close_tab(idx)
        elif action == action_suspend:
            if suspended:
                browser_window.resume_tab(idx)
            else:
                browser_window.suspend_tab(idx)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._hover_tab >= 0:
            rect = self.tabRect(self._hover_tab)
            close_size = 14
            close_rect = QRect(
                rect.left() + 4,
                rect.top() + (rect.height() - close_size) // 2,
                close_size,
                close_size
            )
            self._close_rects[self._hover_tab] = close_rect
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.drawText(close_rect, Qt.AlignmentFlag.AlignCenter, "❌")
        else:
            self._close_rects.clear()


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
        self.downloads_dir = settings.get("downloads_dir", r"C:\PyBrowser\Downloads")

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Default search engine:"))
        self.engine_combo = QComboBox(self)
        self.engine_combo.addItems(["google", "duckduckgo", "bing"])
        if self.search_engine in ("google", "duckduckgo", "bing"):
            self.engine_combo.setCurrentText(self.search_engine)
        layout.addWidget(self.engine_combo)

        self.bg_label = QLabel(f"Browser background color: {self.bg_color}")
        self.bg_button = QPushButton("Choose browser background color")
        self.bg_button.clicked.connect(self.pick_bg_color)
        layout.addWidget(self.bg_label)
        layout.addWidget(self.bg_button)

        self.page_bg_checkbox = QCheckBox("Enable custom webpage background color")
        self.page_bg_checkbox.setChecked(self.custom_page_bg_enabled)
        self.page_bg_label = QLabel(f"Webpage background color: {self.page_bg_color}")
        self.page_bg_button = QPushButton("Choose webpage background color")
        self.page_bg_button.clicked.connect(self.pick_page_bg_color)
        layout.addWidget(self.page_bg_checkbox)
        layout.addWidget(self.page_bg_label)
        layout.addWidget(self.page_bg_button)

        layout.addWidget(QLabel("Downloads directory:"))
        self.downloads_label = QLabel(self.downloads_dir)
        self.downloads_button = QPushButton("Choose folder")
        self.downloads_button.clicked.connect(self.pick_downloads_dir)
        layout.addWidget(self.downloads_label)
        layout.addWidget(self.downloads_button)

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

    def pick_downloads_dir(self):
        dir_ = QFileDialog.getExistingDirectory(self, "Select downloads folder", self.downloads_dir)
        if dir_:
            self.downloads_dir = dir_
            self.downloads_label.setText(self.downloads_dir)

    def get_values(self) -> dict:
        return {
            "search_engine": self.engine_combo.currentText(),
            "bg_color": self.bg_color,
            "custom_page_bg_enabled": self.page_bg_checkbox.isChecked(),
            "page_bg_color": self.page_bg_color,
            "downloads_dir": self.downloads_dir,
        }


# -------------------------
# Modifications dialog (Kill AI + View Style)
# -------------------------
class ModificationsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modifications")
        layout = QVBoxLayout(self)

        self.cb_kill_ai = QCheckBox("Kill AI")
        self.cb_kill_ai.setChecked(settings.get("kill_ai", False))
        layout.addWidget(self.cb_kill_ai)

        layout.addWidget(QLabel("View Style:"))
        self.view_combo = QComboBox()
        self.view_combo.addItems(["None", "Black and white", "Invert", "Cracked glass"])
        style_code = settings.get("view_style", "none")
        index_map = {"none": 0, "bw": 1, "invert": 2, "cracked": 3}
        self.view_combo.setCurrentIndex(index_map.get(style_code, 0))
        layout.addWidget(self.view_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> dict:
        idx = self.view_combo.currentIndex()
        code = {0: "none", 1: "bw", 2: "invert", 3: "cracked"}.get(idx, "none")
        return {
            "kill_ai": self.cb_kill_ai.isChecked(),
            "view_style": code,
        }


# -------------------------
# Permissions dialog
# -------------------------
class PermissionsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Permissions")
        self._settings = settings
        layout = QVBoxLayout(self)

        perms_default = settings.get("permissions_default")
        if not isinstance(perms_default, dict):
            perms_default = {"location": "block", "camera": "block", "microphone": "block", "screenshare": "block"}
        site_perms = settings.get("site_permissions")
        if not isinstance(site_perms, dict):
            site_perms = {}

        self.default_combos = {}
        self.site_combos = {}

        features = [
            ("location", "Location"),
            ("camera", "Camera"),
            ("microphone", "Microphone"),
            ("screenshare", "Screen share"),
        ]

        layout.addWidget(QLabel("Default permissions (for new sites):"))
        for key, label in features:
            row = QHBoxLayout()
            row.addWidget(QLabel(label + ":"))
            combo = QComboBox()
            combo.addItems(["allow", "block"])
            current = perms_default.get(key, "block")
            if current not in ("allow", "block"):
                current = "block"
            combo.setCurrentText(current)
            self.default_combos[key] = combo
            row.addWidget(combo)
            layout.addLayout(row)

        layout.addWidget(QLabel("Site-specific permissions:"))
        if not site_perms:
            layout.addWidget(QLabel("(No sites have requested permissions yet.)"))
        else:
            for host, perms in site_perms.items():
                layout.addWidget(QLabel(host))
                for key, label in features:
                    if key in perms:
                        row = QHBoxLayout()
                        row.addWidget(QLabel("  " + label + ":"))
                        combo = QComboBox()
                        combo.addItems(["inherit default", "allow", "block"])
                        val = perms.get(key, "inherit default")
                        if val not in ("allow", "block"):
                            val = "inherit default"
                        combo.setCurrentText(val)
                        self.site_combos[(host, key)] = combo
                        row.addWidget(combo)
                        layout.addLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> dict:
        defaults = {}
        for key, combo in self.default_combos.items():
            defaults[key] = combo.currentText()

        sites: dict[str, dict] = {}
        for (host, key), combo in self.site_combos.items():
            val = combo.currentText()
            if val == "inherit default":
                continue
            site = sites.setdefault(host, {})
            site[key] = val

        return {
            "permissions_default": defaults,
            "site_permissions": sites,
        }


# -------------------------
# Custom QWebEnginePage for file-type handling
# -------------------------
class BrowserPage(QWebEnginePage):
    def __init__(self, profile: QWebEngineProfile, browser_window: "CustomBrowser", parent=None):
        super().__init__(profile, parent)
        self.browser_window = browser_window

    def acceptNavigationRequest(self, url: QUrl, type: QWebEnginePage.NavigationType, is_main_frame: bool) -> bool:
        if is_main_frame:
            path = url.path().lower()
            _, ext = os.path.splitext(path)
            ext = ext.lstrip(".")
            allowed = {"", "png", "html", "txt", "htm", "php", "jpg", "jpeg"}
            if ext and ext not in allowed:
                msg = f"This file type ({ext}) is not directly supported.\nDownload this file?\n\n{url.toString()}"
                box = QMessageBox(self.browser_window)
                box.setWindowTitle("Download file")
                box.setText(msg)
                box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                result = box.exec()
                if result == QMessageBox.StandardButton.Yes:
                    self.profile().download(url, "")
                return False
        return super().acceptNavigationRequest(url, type, is_main_frame)


# -------------------------
# Browser
# -------------------------
class CustomBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyBrowser")
        self.settings_file = r"C:\PyBrowser\settings.json"
        self.bookmarks_file = r"C:\PyBrowser\bookmarks.json"
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
        self.settings = self.load_settings()
        self.history = []
        self.bookmarks = self.load_bookmarks()

        self.profile = QWebEngineProfile("PyBrowserProfile", self)
        self.enable_javascript_features()

        self.downloads_dir = self.settings.get("downloads_dir", r"C:\PyBrowser\Downloads")
        os.makedirs(self.downloads_dir, exist_ok=True)
        self.profile.downloadRequested.connect(self.handle_download)

        self.setGeometry(100, 100, 1024, 768)
        self.main_layout = QVBoxLayout()

        self.setup_nav_bar()
        self.setup_bookmarks_bar()

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(False)
        self.tabs.setMovable(True)
        self.tabs.setTabBar(DragSafeTabBar())
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_title)
        self.tabs.currentChanged.connect(lambda idx: self.update_bookmark_button_state())
        self.main_layout.addWidget(self.tabs)

        self.main_widget = QWidget()
        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)

        self.downloads_panel = DownloadsPanel(self)
        self.downloads_panel.hide()

        self.apply_gui_colors()
        self.refresh_bookmarks_bar()
        self.add_new_tab()

    def enable_javascript_features(self):
        settings = self.profile.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)

    # --- Navigation Bar ---
    def setup_nav_bar(self):
        self.nav_bar = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)

        self.back_button = QPushButton("◀")
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.back_button.customContextMenuRequested.connect(self.show_history_menu)

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

        self.bookmark_button = QPushButton("☆")
        self.bookmark_button.setFixedSize(30, 30)
        self.bookmark_button.clicked.connect(self.on_bookmark_button_clicked)

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
        layout.addWidget(self.bookmark_button)
        layout.addWidget(self.new_tab_button)
        layout.addWidget(self.menu_button)
        self.nav_bar.setLayout(layout)
        self.main_layout.addWidget(self.nav_bar)

    # --- Bookmarks Bar ---
    def setup_bookmarks_bar(self):
        self.bookmarks_bar = BookmarkBar(self)
        self.main_layout.addWidget(self.bookmarks_bar)

    def refresh_bookmarks_bar(self):
        self.bookmarks_bar.set_bookmarks(self.bookmarks)

    def activate_bookmark(self, url: str):
        if not url:
            return
        if url.lower().startswith("javascript:"):
            script = url[len("javascript:"):]
            b = self.get_current_browser()
            if b:
                b.page().runJavaScript(script)
        else:
            self.add_new_tab(url)

    def on_bookmarks_reordered(self, buttons: list[BookmarkButton]):
        new_list = []
        for btn in buttons:
            for bm in self.bookmarks:
                if bm.get("url") == btn.url and bm.get("title", bm.get("url", "")) == btn.title:
                    if bm not in new_list:
                        new_list.append(bm)
                    break
        if len(new_list) == len(self.bookmarks):
            self.bookmarks = new_list
            self.save_bookmarks()

    # --- Core Functions ---
    def get_home_url(self) -> str:
        engine = self.settings.get("search_engine", "google").lower()
        return SEARCH_ENGINE_HOME.get(engine, SEARCH_ENGINE_HOME["google"])

    def position_downloads_panel(self):
        if self.downloads_panel and self.downloads_panel.isVisible():
            self.downloads_panel.adjustSize()
            x = self.width() - self.downloads_panel.width() - 12
            y = self.nav_bar.height() + self.bookmarks_bar.height() + 8
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
        self.downloads_dir = self.settings.get("downloads_dir", r"C:\PyBrowser\Downloads")
        os.makedirs(self.downloads_dir, exist_ok=True)

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
    def _attach_page_permissions(self, page: QWebEnginePage):
        try:
            page.featurePermissionRequested.disconnect()
        except TypeError:
            pass
        page.featurePermissionRequested.connect(self.on_feature_permission_requested)

    def add_new_tab(self, url=None):
        b = QWebEngineView()
        p = BrowserPage(self.profile, self, b)
        b.setPage(p)
        self._attach_page_permissions(p)
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
        tab._browser = b
        tab._suspended = False
        tab._suspend_overlay = None

        idx = self.tabs.addTab(tab, "Loading...")
        self.tabs.setCurrentIndex(idx)

        default_url = QUrl(url) if url else QUrl(self.get_home_url())
        b.setUrl(default_url)
        self.update_bookmark_button_state()

    def add_existing_tab(self, tab_widget: QWidget, title: str, icon: QIcon):
        if not hasattr(tab_widget, "_browser"):
            tab_widget._browser = tab_widget.layout().itemAt(0).widget()
            tab_widget._suspended = False
            tab_widget._suspend_overlay = None

        browser = tab_widget._browser
        for sig in (browser.urlChanged, browser.titleChanged, browser.iconChanged):
            try:
                sig.disconnect()
            except TypeError:
                pass
        try:
            browser.page().loadFinished.disconnect()
        except TypeError:
            pass

        self._attach_page_permissions(browser.page())

        browser.urlChanged.connect(self.update_url_bar)
        browser.titleChanged.connect(lambda t, br=browser: self.update_tab_title(br, t))
        browser.iconChanged.connect(lambda i, br=browser: self.update_tab_icon(br, i))
        browser.page().loadFinished.connect(lambda ok, br=browser: self.on_page_load_finished(br, ok))

        idx = self.tabs.addTab(tab_widget, icon, title)
        self.tabs.setCurrentIndex(idx)
        self.update_bookmark_button_state()

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
        pos = QCursor.pos()
        new_window.move(pos.x() - new_window.width() // 2, pos.y())

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
        if not hasattr(tab_widget, "_browser"):
            tab_widget._browser = tab_widget.layout().itemAt(0).widget()
            tab_widget._suspended = False
            tab_widget._suspend_overlay = None

        browser = tab_widget._browser
        for sig in (browser.urlChanged, browser.titleChanged, browser.iconChanged):
            try:
                sig.disconnect()
            except TypeError:
                pass
        try:
            browser.page().loadFinished.disconnect()
        except TypeError:
            pass

        self._attach_page_permissions(browser.page())

        browser.urlChanged.connect(self.update_url_bar)
        browser.titleChanged.connect(lambda t, br=browser: self.update_tab_title(br, t))
        browser.iconChanged.connect(lambda i, br=browser: self.update_tab_icon(br, i))
        browser.page().loadFinished.connect(lambda ok, br=browser: self.on_page_load_finished(br, ok))

        dest_index = max(0, min(dest_index, self.tabs.count()))
        self.tabs.insertTab(dest_index, tab_widget, icon, title)
        self.tabs.setCurrentIndex(dest_index)
        self.update_bookmark_button_state()

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
            self.update_bookmark_button_state()

    # --- Suspend / Resume ---
    def is_tab_suspended(self, index: int) -> bool:
        if index < 0 or index >= self.tabs.count():
            return False
        tab = self.tabs.widget(index)
        return getattr(tab, "_suspended", False)

    def suspend_tab(self, index: int):
        if index < 0 or index >= self.tabs.count():
            return
        tab = self.tabs.widget(index)
        if getattr(tab, "_suspended", False):
            return
        browser = getattr(tab, "_browser", None)
        if browser is None:
            browser = tab.layout().itemAt(0).widget()
            tab._browser = browser

        pixmap = browser.grab()

        overlay = QWidget(tab)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        img_label = QLabel()
        img_label.setPixmap(pixmap)
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(10.0)
        img_label.setGraphicsEffect(blur)

        text_label = QLabel("Tab is suspended. Tap the button below to resume the webpage.")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        resume_btn = QPushButton("Resume")
        resume_btn.setFixedHeight(30)
        resume_btn.clicked.connect(lambda: self.resume_tab(index))

        layout.addWidget(img_label)
        layout.addWidget(text_label)
        layout.addWidget(resume_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        overlay.setLayout(layout)

        tab.layout().addWidget(overlay)
        browser.hide()

        tab._suspended = True
        tab._suspend_overlay = overlay

        try:
            browser.page().setLifecycleState(QWebEnginePage.LifecycleState.Frozen)
        except AttributeError:
            pass

    def resume_tab(self, index: int):
        if index < 0 or index >= self.tabs.count():
            return
        tab = self.tabs.widget(index)
        if not getattr(tab, "_suspended", False):
            return
        browser = getattr(tab, "_browser", None)
        if browser is None:
            browser = tab.layout().itemAt(0).widget()
            tab._browser = browser

        overlay = getattr(tab, "_suspend_overlay", None)
        if overlay:
            tab.layout().removeWidget(overlay)
            overlay.setParent(None)
            overlay.deleteLater()
        browser.show()
        try:
            browser.page().setLifecycleState(QWebEnginePage.LifecycleState.Active)
        except AttributeError:
            pass
        tab._suspended = False
        tab._suspend_overlay = None

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

    # --- History ---
    def record_history_entry(self, browser: QWebEngineView):
        url = browser.url().toString()
        if not url:
            return
        title = browser.title() or url
        if self.history and self.history[-1][1] == url:
            return
        self.history.append((title, url))
        if len(self.history) > 50:
            self.history = self.history[-50:]

    def show_history_menu(self, pos):
        if not self.history:
            return
        menu = QMenu(self)
        for title, url in reversed(self.history[-10:]):
            text = f"{title} - {url}"
            action = menu.addAction(text)
            action.triggered.connect(lambda checked=False, u=url: self.add_new_tab(u))
        menu.exec(self.back_button.mapToGlobal(pos))

    # --- Permission handling (incl. screen share) ---
    def on_feature_permission_requested(self, security_origin: QUrl, feature: QWebEnginePage.Feature):
        page = self.sender()
        if not isinstance(page, QWebEnginePage):
            return

        # Handle optional screen-share features safely
        FeatureEnum = QWebEnginePage.Feature
        desktop_video_feat = getattr(FeatureEnum, "DesktopVideoCapture", None)
        desktop_av_feat = getattr(FeatureEnum, "DesktopAudioVideoCapture", None)

        host = security_origin.host().lower()
        perms_default = self.settings.get("permissions_default")
        if not isinstance(perms_default, dict):
            perms_default = {"location": "block", "camera": "block", "microphone": "block", "screenshare": "block"}
        site_perms = self.settings.get("site_permissions")
        if not isinstance(site_perms, dict):
            site_perms = {}

        def get_site_perm(key: str):
            host_perms = site_perms.get(host, {})
            return host_perms.get(key)

        def set_site_perm(key: str, value: str):
            host_perms = site_perms.get(host, {})
            host_perms[key] = value
            site_perms[host] = host_perms

        key = None
        description = ""

        if feature == QWebEnginePage.Feature.Geolocation:
            key = "location"
            description = "your location"
        elif feature == QWebEnginePage.Feature.MediaAudioCapture:
            key = "microphone"
            description = "your microphone"
        elif feature == QWebEnginePage.Feature.MediaVideoCapture:
            key = "camera"
            description = "your camera"
        elif feature == QWebEnginePage.Feature.MediaAudioVideoCapture:
            key = "camera_microphone"
            description = "your camera and microphone"
        elif desktop_video_feat is not None and feature == desktop_video_feat:
            key = "screenshare"
            description = "your screen"
        elif desktop_av_feat is not None and feature == desktop_av_feat:
            key = "screenshare"
            description = "your screen and its audio"
        else:
            page.setFeaturePermission(
                security_origin,
                feature,
                QWebEnginePage.PermissionPolicy.PermissionDeniedByUser,
            )
            return

        decision = None

        if feature == QWebEnginePage.Feature.MediaAudioVideoCapture:
            cam = get_site_perm("camera")
            mic = get_site_perm("microphone")
            if cam == "allow" and mic == "allow":
                decision = "allow"
            elif cam == "block" or mic == "block":
                decision = "block"
        elif desktop_video_feat is not None and feature == desktop_video_feat:
            decision = get_site_perm("screenshare")
        elif desktop_av_feat is not None and feature == desktop_av_feat:
            decision = get_site_perm("screenshare")
        else:
            decision = get_site_perm(key)

        if decision is None:
            if feature == QWebEnginePage.Feature.Geolocation:
                default_for_feature = perms_default.get("location", "block")
            elif feature == QWebEnginePage.Feature.MediaAudioCapture:
                default_for_feature = perms_default.get("microphone", "block")
            elif feature == QWebEnginePage.Feature.MediaVideoCapture:
                default_for_feature = perms_default.get("camera", "block")
            elif feature == QWebEnginePage.Feature.MediaAudioVideoCapture:
                if (
                    perms_default.get("camera") == "allow"
                    and perms_default.get("microphone") == "allow"
                ):
                    default_for_feature = "allow"
                else:
                    default_for_feature = "block"
            elif (desktop_video_feat is not None and feature == desktop_video_feat) or (
                desktop_av_feat is not None and feature == desktop_av_feat
            ):
                default_for_feature = perms_default.get("screenshare", "block")
            else:
                default_for_feature = "block"

            msg = f"{host} wants to access {description}. Allow?"
            buttons = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            default_btn = (
                QMessageBox.StandardButton.Yes
                if default_for_feature == "allow"
                else QMessageBox.StandardButton.No
            )
            box = QMessageBox(self)
            box.setWindowTitle("Permission request")
            box.setText(msg)
            box.setStandardButtons(buttons)
            box.setDefaultButton(default_btn)
            result = box.exec()
            decision = "allow" if result == QMessageBox.StandardButton.Yes else "block"

            if feature == QWebEnginePage.Feature.Geolocation:
                set_site_perm("location", decision)
            elif feature == QWebEnginePage.Feature.MediaAudioCapture:
                set_site_perm("microphone", decision)
            elif feature == QWebEnginePage.Feature.MediaVideoCapture:
                set_site_perm("camera", decision)
            elif feature == QWebEnginePage.Feature.MediaAudioVideoCapture:
                set_site_perm("camera", decision)
                set_site_perm("microphone", decision)
            elif (desktop_video_feat is not None and feature == desktop_video_feat) or (
                desktop_av_feat is not None and feature == desktop_av_feat
            ):
                set_site_perm("screenshare", decision)

            self.settings["site_permissions"] = site_perms
            self.save_settings()

        if decision == "allow":
            policy = QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
        else:
            policy = QWebEnginePage.PermissionPolicy.PermissionDeniedByUser

        page.setFeaturePermission(security_origin, feature, policy)

    # --- Helpers ---
    def get_current_browser(self):
        cw = self.tabs.currentWidget()
        if not cw:
            return None
        if hasattr(cw, "_browser"):
            return cw._browser
        return cw.layout().itemAt(0).widget()

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
        if not isinstance(data.get("permissions_default"), dict):
            data["permissions_default"] = {
                "location": "block",
                "camera": "block",
                "microphone": "block",
                "screenshare": "block",
            }
        else:
            data["permissions_default"].setdefault("screenshare", "block")
        if not isinstance(data.get("site_permissions"), dict):
            data["site_permissions"] = {}
        return data

    def save_settings(self):
        try:
            with open(self.settings_file, "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass

    def load_bookmarks(self):
        if os.path.exists(self.bookmarks_file):
            try:
                with open(self.bookmarks_file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass
        b = self.settings.get("bookmarks")
        if isinstance(b, list):
            return b
        return []

    def save_bookmarks(self):
        try:
            with open(self.bookmarks_file, "w") as f:
                json.dump(self.bookmarks, f, indent=2)
        except Exception:
            pass

    def apply_gui_colors(self):
        bg = self.settings.get("bg_color", "#000000")
        self.setStyleSheet(f"QMainWindow {{ background-color: {bg}; }}")
        self.main_widget.setStyleSheet(f"background-color: {bg};")
        self.nav_bar.setStyleSheet(f"background-color: {bg};")
        if hasattr(self, "bookmarks_bar"):
            self.bookmarks_bar.setStyleSheet(f"background-color: {bg};")

    def update_url_bar(self, qurl):
        self.url_bar.setText(qurl.toString())
        self.update_bookmark_button_state()

    def update_title(self):
        current_widget = self.tabs.currentWidget()
        if current_widget:
            self.setWindowTitle(self.tabs.tabText(self.tabs.currentIndex()))
        else:
            self.setWindowTitle("PyBrowser")

    def update_tab_title(self, browser, title):
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            br = getattr(tab, "_browser", tab.layout().itemAt(0).widget())
            if br == browser:
                self.tabs.setTabText(i, title if title else "New Tab")
                if self.tabs.currentIndex() == i:
                    self.setWindowTitle(title if title else "New Tab")
                break

    def update_tab_icon(self, browser, icon: QIcon):
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            br = getattr(tab, "_browser", tab.layout().itemAt(0).widget())
            if br == browser:
                self.tabs.setTabIcon(i, icon)
                break

    def on_page_load_finished(self, browser: QWebEngineView, ok: bool):
        if not ok:
            return
        self.record_history_entry(browser)
        self.apply_custom_page_background(browser)
        self.apply_page_additions(browser)
        self.apply_view_style(browser)
        self.update_bookmark_button_state()

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

    def apply_view_style(self, browser: QWebEngineView | None = None):
        style = self.settings.get("view_style", "none")
        if browser is None:
            browser = self.get_current_browser()
        if not browser:
            return

        if style == "none":
            script = """
            (function(){
                try{
                    document.documentElement.style.filter = '';
                    if (document.body) document.body.style.filter = '';
                    var ov = document.getElementById('pybrowser-view-style-overlay');
                    if (ov) ov.remove();
                }catch(e){}
            })();
            """
        elif style == "bw":
            script = """
            (function(){
                try{
                    document.documentElement.style.filter = 'grayscale(1)';
                    if (document.body) document.body.style.filter = 'grayscale(1)';
                    var ov = document.getElementById('pybrowser-view-style-overlay');
                    if (ov) ov.remove();
                }catch(e){}
            })();
            """
        elif style == "invert":
            script = """
            (function(){
                try{
                    document.documentElement.style.filter = 'invert(1)';
                    if (document.body) document.body.style.filter = 'invert(1)';
                    var ov = document.getElementById('pybrowser-view-style-overlay');
                    if (ov) ov.remove();
                }catch(e){}
            })();
            """
        else:  # cracked
            script = """
            (function(){
                try{
                    document.documentElement.style.filter = '';
                    if (document.body) document.body.style.filter = '';
                    var ov = document.getElementById('pybrowser-view-style-overlay');
                    if (!ov){
                        ov = document.createElement('div');
                        ov.id = 'pybrowser-view-style-overlay';
                        ov.style.position = 'fixed';
                        ov.style.left = '0';
                        ov.style.top = '0';
                        ov.style.right = '0';
                        ov.style.bottom = '0';
                        ov.style.pointerEvents = 'none';
                        ov.style.zIndex = '999999';
                        ov.style.backgroundImage =
                            'repeating-linear-gradient(135deg, rgba(255,255,255,0.2) 0, rgba(255,255,255,0.2) 1px, transparent 1px, transparent 4px),' +
                            'repeating-linear-gradient(45deg, rgba(0,0,0,0.3) 0, rgba(0,0,0,0.3) 1px, transparent 1px, transparent 6px)';
                        ov.style.mixBlendMode = 'screen';
                    }
                    if (!ov.parentNode) document.body.appendChild(ov);
                }catch(e){}
            })();
            """
        browser.page().runJavaScript(script)

    def apply_page_additions(self, browser: QWebEngineView | None = None):
        if browser is None:
            browser = self.get_current_browser()
        if not browser:
            return

        url_obj = browser.url()
        host = url_obj.host().lower()

        if self.settings.get("kill_ai", False):
            ai_domains = [
                "voidai.app",
                "chatgpt.com",
                "openai.com",
                "chracter.ai",
                "spicychat.ai",
                "gemini.google.com",
                "perplexity.ai",
                "claude.ai",
                "deepai.org",
            ]
            for d in ai_domains:
                if host.endswith(d):
                    QMessageBox.warning(self, "Warning", "Get the hell off this AI site")
                    break

            script_ai = """
            (function(){
                try{
                    const matches = ['AI Overview','AI overview','AI Mode','AI mode'];
                    const all = document.querySelectorAll('span,div,button');
                    all.forEach(function(el){
                        const t = (el.innerText || '').trim();
                        for (let i=0; i<matches.length; i++){
                            const m = matches[i];
                            if (t === m || t.indexOf(m) !== -1){
                                const p = el.closest('div') || el;
                                p.style.display = 'none';
                                break;
                            }
                        }
                    });
                }catch(e){}
            })();
            """
            browser.page().runJavaScript(script_ai)

    # --- Bookmarks helpers ---
    def is_url_bookmarked(self, url: str) -> int:
        for idx, bm in enumerate(self.bookmarks):
            if bm.get("url") == url:
                return idx
        return -1

    def update_bookmark_button_state(self):
        b = self.get_current_browser()
        if not b:
            self.bookmark_button.setText("☆")
            return
        url = b.url().toString()
        if not url:
            self.bookmark_button.setText("☆")
            return
        idx = self.is_url_bookmarked(url)
        self.bookmark_button.setText("★" if idx >= 0 else "☆")

    def on_bookmark_button_clicked(self):
        b = self.get_current_browser()
        if not b:
            return
        url = b.url().toString()
        if not url:
            return
        title = b.title() or url

        existing_index = self.is_url_bookmarked(url)
        removing = existing_index >= 0

        dlg = QDialog(self)
        dlg.setWindowTitle("Remove Bookmark" if removing else "Add Bookmark")
        v = QVBoxLayout(dlg)

        v.addWidget(QLabel("Title:"))
        title_edit = QLineEdit(title, dlg)
        v.addWidget(title_edit)

        v.addWidget(QLabel("URL:"))
        url_edit = QLineEdit(url, dlg)
        v.addWidget(url_edit)

        buttons = QDialogButtonBox(dlg)
        btn_cancel = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        btn_action = buttons.addButton("Remove" if removing else "Add", QDialogButtonBox.ButtonRole.AcceptRole)
        v.addWidget(buttons)

        def on_accept():
            t = title_edit.text().strip()
            u = url_edit.text().strip()
            if not u:
                dlg.reject()
                return

            if removing:
                idx = self.is_url_bookmarked(u)
                if idx >= 0:
                    icon_path = self.bookmarks[idx].get("icon_path")
                    if icon_path and os.path.exists(icon_path):
                        try:
                            os.remove(icon_path)
                        except OSError:
                            pass
                    self.bookmarks.pop(idx)
            else:
                icon_path = None
                icon = b.icon()
                if icon and not icon.isNull():
                    pixmap = icon.pixmap(32, 32)
                    if not pixmap.isNull():
                        fav_dir = os.path.join(os.path.dirname(self.settings_file), "Favicons")
                        os.makedirs(fav_dir, exist_ok=True)
                        safe_name = str(abs(hash(u))) + ".png"
                        full_path = os.path.join(fav_dir, safe_name)
                        pixmap.save(full_path, "PNG")
                        icon_path = full_path

                idx = self.is_url_bookmarked(u)
                entry = {"title": t, "url": u}
                if icon_path:
                    entry["icon_path"] = icon_path

                if idx >= 0:
                    old = self.bookmarks[idx]
                    old.update(entry)
                    self.bookmarks[idx] = old
                else:
                    self.bookmarks.append(entry)

            self.save_bookmarks()
            self.refresh_bookmarks_bar()
            self.update_bookmark_button_state()
            dlg.accept()

        btn_action.clicked.connect(on_accept)
        btn_cancel.clicked.connect(dlg.reject)

        dlg.exec()

    # --- Settings / Modifications / Permissions ---
    def open_settings_dialog(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.get_values()
            self.settings.update(vals)
            self.save_settings()

            self.downloads_dir = self.settings.get("downloads_dir", r"C:\PyBrowser\Downloads")
            os.makedirs(self.downloads_dir, exist_ok=True)

            self.apply_gui_colors()
            self.apply_custom_page_background()
            self.apply_page_additions()
            self.apply_view_style()

    def open_modifications_dialog(self):
        dlg = ModificationsDialog(self.settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.get_values()
            self.settings["kill_ai"] = vals["kill_ai"]
            self.settings["view_style"] = vals["view_style"]
            self.save_settings()
            self.apply_page_additions()
            self.apply_view_style()

    def open_permissions_dialog(self):
        dlg = PermissionsDialog(self.settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.get_values()
            self.settings["permissions_default"] = vals["permissions_default"]
            self.settings["site_permissions"] = vals["site_permissions"]
            self.save_settings()

    def open_menu(self):
        menu = QMenu(self)
        downloads_action = menu.addAction("Downloads")
        settings_action = menu.addAction("Settings")
        modifications_action = menu.addAction("Modifications")
        permissions_action = menu.addAction("Permissions")

        downloads_action.triggered.connect(lambda: os.startfile(self.downloads_dir))
        settings_action.triggered.connect(self.open_settings_dialog)
        modifications_action.triggered.connect(self.open_modifications_dialog)
        permissions_action.triggered.connect(self.open_permissions_dialog)

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
