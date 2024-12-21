import sys
import os
import sqlite3
from datetime import datetime
from PyQt5.QtCore import QUrl, Qt, QSize, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QLineEdit, 
                           QVBoxLayout, QWidget, QPushButton, QHBoxLayout,
                           QMenuBar, QMenu, QAction, QDialog, QTableWidget,
                           QTableWidgetItem, QProgressBar, QLabel, QFileDialog,
                           QMessageBox)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEngineSettings
from PyQt5.QtGui import QIcon

class DownloadManager(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Manager")
        self.resize(600, 400)
        self.download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        self.downloads = []

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Download Directory Selection
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel(f"Download Directory: {self.download_dir}")
        dir_button = QPushButton("Change Directory")
        dir_button.clicked.connect(self.change_directory)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(dir_button)
        layout.addLayout(dir_layout)

        # Downloads Table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["File Name", "Progress", "Status"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_all)
        btn_layout.addWidget(clear_btn)
        layout.addLayout(btn_layout)

    def change_directory(self):
        new_dir = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.download_dir)
        if new_dir:
            self.download_dir = new_dir
            self.dir_label.setText(f"Download Directory: {self.download_dir}")

    def add_download(self, download_item):
        file_name = download_item.downloadFileName()
        for download in self.downloads:
            if download["download_item"].downloadFileName() == file_name:
                return
        row = self.table.rowCount()
        self.table.insertRow(row)

        name_item = QTableWidgetItem(file_name)
        progress_bar = QProgressBar()
        status_item = QTableWidgetItem("Downloading")

        self.table.setItem(row, 0, name_item)
        self.table.setCellWidget(row, 1, progress_bar)
        self.table.setItem(row, 2, status_item)

        download_info = {
            "download_item": download_item,
            "progress_bar": progress_bar,
            "status_item": status_item
        }
        self.downloads.append(download_info)

        # Set download path
        download_item.setDownloadDirectory(self.download_dir)
        
        # Connect signals
        download_item.downloadProgress.connect(
            lambda received, total, info=download_info: self.update_progress(received, total, info)
        )
        download_item.finished.connect(
            lambda info=download_info: self.download_finished(info)
        )
        
        # Accept the download
        download_item.accept()

    def update_progress(self, received, total, download_info):
        if total > 0:
            progress = (received * 100) / total
            download_info["progress_bar"].setValue(int(progress))

    def download_finished(self, download_info):
        download_info["progress_bar"].setValue(100)
        download_info["status_item"].setText("Completed")

    def clear_all(self):
        self.table.setRowCount(0)
        self.downloads = []


class HistoryDialog(QDialog):
    url_selected = pyqtSignal(str)
    
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Browser History")
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["URL", "Visit Time"])
        self.table.setColumnWidth(0, 400)
        self.table.setColumnWidth(1, 150)
        
        layout.addWidget(self.table)
        
        cursor = conn.cursor()
        cursor.execute('SELECT url, visit_time FROM history ORDER BY visit_time DESC')
        history = cursor.fetchall()
        
        self.table.setRowCount(len(history))
        for i, (url, time) in enumerate(history):
            self.table.setItem(i, 0, QTableWidgetItem(url))
            self.table.setItem(i, 1, QTableWidgetItem(time))
            
        self.table.doubleClicked.connect(self.on_url_selected)
        
    def on_url_selected(self, index):
        url = self.table.item(index.row(), 0).text()
        self.url_selected.emit(url)
        self.accept()


class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Enhanced Browser v2.0")
        self.resize(1200, 800)
        
        # Initialize download manager
        self.download_manager = DownloadManager(self)
        
        # Create main layout and central widget
        central_widget = QWidget()
        self.main_layout = QVBoxLayout()
        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Address bar and navigation buttons layout
        nav_layout = QHBoxLayout()
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate)
        
        back_btn = QPushButton("←")
        forward_btn = QPushButton("→")
        refresh_btn = QPushButton("🔄")
        home_btn = QPushButton("🏠")
        
        back_btn.clicked.connect(self.go_back)
        forward_btn.clicked.connect(self.go_forward)
        refresh_btn.clicked.connect(self.refresh)
        home_btn.clicked.connect(self.go_home)
        
        nav_layout.addWidget(back_btn)
        nav_layout.addWidget(forward_btn)
        nav_layout.addWidget(refresh_btn)
        nav_layout.addWidget(home_btn)
        nav_layout.addWidget(self.url_bar)
        
        self.main_layout.addLayout(nav_layout)
        
        # Tab management
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.main_layout.addWidget(self.tabs)
        
        # New tab button
        self.tabs.setCornerWidget(self.create_new_tab_button())
        
        # History database
        self.init_history_database()
        
        # Initialize homepage
        self.add_new_tab(QUrl("https://www.google.com"))

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        new_tab_action = QAction('New Tab', self)
        new_tab_action.setShortcut('Ctrl+T')
        new_tab_action.triggered.connect(lambda: self.add_new_tab(QUrl("https://www.google.com")))
        
        new_window_action = QAction('New Window', self)
        new_window_action.setShortcut('Ctrl+N')
        new_window_action.triggered.connect(self.new_window)
        
        new_incognito_action = QAction('New Incognito Window', self)
        new_incognito_action.setShortcut('Ctrl+Shift+N')
        new_incognito_action.triggered.connect(self.new_incognito_window)
        
        print_action = QAction('Print...', self)
        print_action.setShortcut('Ctrl+P')
        print_action.triggered.connect(self.print_page)
        
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        
        file_menu.addAction(new_tab_action)
        file_menu.addAction(new_window_action)
        file_menu.addAction(new_incognito_action)
        file_menu.addSeparator()
        file_menu.addAction(print_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
        
        # History menu
        history_menu = menubar.addMenu('History')
        show_history_action = QAction('Show History', self)
        show_history_action.triggered.connect(self.show_history)
        history_menu.addAction(show_history_action)
        
        # Downloads menu
        downloads_menu = menubar.addMenu("Downloads")
        show_downloads_action = QAction("Show Downloads (Ctrl+J)", self)
        show_downloads_action.setShortcut("Ctrl+J")
        show_downloads_action.triggered.connect(self.show_download_manager)
        downloads_menu.addAction(show_downloads_action)
        
        # View menu
        view_menu = menubar.addMenu('View')
        zoom_in_action = QAction('Zoom In', self)
        zoom_out_action = QAction('Zoom Out', self)
        zoom_in_action.setShortcut('Ctrl++')
        zoom_out_action.setShortcut('Ctrl+-')
        zoom_in_action.triggered.connect(self.zoom_in)
        zoom_out_action.triggered.connect(self.zoom_out)
        view_menu.addAction(zoom_in_action)
        view_menu.addAction(zoom_out_action)

    def create_new_tab_button(self):
        btn = QPushButton("+")
        btn.clicked.connect(lambda: self.add_new_tab(QUrl("https://www.google.com")))
        return btn

    def add_new_tab(self, url=None):
        web_view = QWebEngineView()
        web_view.urlChanged.connect(self.update_url)
        
        # Set up download handling
        web_view.page().profile().downloadRequested.connect(self.handle_download)
        
        # Advanced settings for modern web support
        profile = web_view.page().profile()
        
        settings = web_view.page().settings()
        settings.setAttribute(QWebEngineSettings.AutoLoadImages, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebRTCPublicInterfacesOnly, False)
        settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
        settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, False)
        settings.setAttribute(QWebEngineSettings.HyperlinkAuditingEnabled, True)
        
        if url is None or not isinstance(url, QUrl):
            url = QUrl("https://www.google.com")
        elif isinstance(url, str):
            url = QUrl.fromUserInput(url)
            
        web_view.load(url)
        index = self.tabs.addTab(web_view, "New Tab")
        self.tabs.setCurrentIndex(index)
        self.update_url(url)
        
        if url.toString() != "":
            self.save_history(url.toString())

    def handle_download(self, download_item):
        self.download_manager.add_download(download_item)
        self.show_download_manager()

    def show_history(self):
        dialog = HistoryDialog(self.conn, self)
        dialog.url_selected.connect(lambda url: self.add_new_tab(QUrl(url)))
        dialog.exec_()

    def show_download_manager(self):
        self.download_manager.show()

    def new_window(self):
        new_browser = Browser()
        new_browser.show()

    def new_incognito_window(self):
        # In a real implementation, this would create a private browsing window
        QMessageBox.information(self, "Incognito Mode", "Incognito mode would launch here")

    def print_page(self):
        if self.tabs.currentWidget():
            self.tabs.currentWidget().page().printToPdf("webpage.pdf")
            QMessageBox.information(self, "Print", "Page has been saved as PDF")

    def zoom_in(self):
        if self.tabs.currentWidget():
            self.tabs.currentWidget().setZoomFactor(
                self.tabs.currentWidget().zoomFactor() + 0.1
            )

    def zoom_out(self):
        if self.tabs.currentWidget():
            self.tabs.currentWidget().setZoomFactor(
                self.tabs.currentWidget().zoomFactor() - 0.1
            )

    def navigate(self):
        url = QUrl.fromUserInput(self.url_bar.text())
        current_web_view = self.tabs.currentWidget()
        if current_web_view:
            current_web_view.load(url)

    def update_url(self, url):
        self.url_bar.setText(url.toString())
        self.tabs.setTabText(self.tabs.currentIndex(), url.host() or "New Tab")

    def close_tab(self, index):
        if self.tabs.count() > 1:
            widget = self.tabs.widget(index)
            widget.deleteLater()
            self.tabs.removeTab(index)

    def go_back(self):
        if self.tabs.currentWidget():
            self.tabs.currentWidget().back()

    def go_forward(self):
        if self.tabs.currentWidget():
            self.tabs.currentWidget().forward()

    def refresh(self):
        if self.tabs.currentWidget():
            self.tabs.currentWidget().reload()

    def go_home(self):
        self.add_new_tab(QUrl("https://www.google.com"))

    def init_history_database(self):
        self.conn = sqlite3.connect('browser_history.db')
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                visit_time DATETIME
            )
        ''')
        self.conn.commit()

    def save_history(self, url):
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO history (url, visit_time) VALUES (?, ?)',
                      (url, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        self.conn.commit()

# Entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)
    browser = Browser()
    browser.show()
    sys.exit(app.exec_())
