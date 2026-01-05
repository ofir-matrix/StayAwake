import sys
import os
import logging
from datetime import datetime
from time import sleep
import winreg

import interface
from pyautogui import press
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QEvent, Qt, QThread
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QMenu, QSystemTrayIcon, qApp


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    
    return os.path.join(base_path, relative_path)


def get_log_file_path():
    """Get the path to the log file."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - log next to exe
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, 'StayAwake.log')
    else:
        # Running as script - log in script directory
        script_dir = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(script_dir, 'StayAwake.log')


def setup_logging():
    """Set up logging configuration."""
    log_file = get_log_file_path()
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info(f"StayAwake application started at {datetime.now()}")
    logger.info(f"Log file: {log_file}")
    return logger


def exception_handler(exc_type, exc_value, exc_traceback):
    """Handle unhandled exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger = logging.getLogger(__name__)
    logger.critical(
        "Unhandled exception occurred",
        exc_info=(exc_type, exc_value, exc_traceback)
    )
    logger.critical("=" * 80)
    
    # Also print to stderr if available
    try:
        print(f"CRITICAL ERROR: Check log file at {get_log_file_path()}", file=sys.stderr)
    except Exception:
        pass


class PreventSleep(QThread):
    def run(self):
        logger = logging.getLogger(__name__)
        logger.debug("PreventSleep thread started")
        try:
            while True:
                try:
                    press("f24")
                    sleep(60)
                except Exception as e:
                    logger.error(f"Error in PreventSleep loop: {e}", exc_info=True)
                    sleep(60)  # Continue after error
        except Exception as e:
            logger.critical(f"PreventSleep thread crashed: {e}", exc_info=True)


class StayAwakeApp(QtWidgets.QMainWindow):
    AUTOSTART_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    AUTOSTART_VALUE_NAME = "StayAwake"

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        try:
            super().__init__()
            self.ui = interface.Ui_MainWindow()
            self.ui.setupUi(self)
            icon_path = resource_path("icons/32x32.png")
            self.ui.label_2.setPixmap(QtGui.QPixmap(icon_path))

            self.running = False
            self.prevent_sleep = None
            self.tray_icon = None
            self.status = "off"

            self.setup_tray()
            self.setup_window()
            self.load_autostart_state()
            # Automatically start preventing sleep on launch
            self.start_prevent_sleep()
            self.logger.info("StayAwakeApp initialized successfully")
        except Exception as e:
            self.logger.critical(f"Error initializing StayAwakeApp: {e}", exc_info=True)
            raise

    def setup_tray(self):
        try:
            self.tray_icon = QSystemTrayIcon(self)
            icon_path = resource_path("icons/StayAwakeOpaque.ico")
            self.tray_icon.setIcon(QIcon(icon_path))
            self.tray_icon.setToolTip("Stay Awake")
            self.tray_icon.activated.connect(self.tray_icon_single_click)

            open_action = QAction("Open", self)
            quit_action = QAction("Quit", self)
            open_action.triggered.connect(self.showNormal)
            quit_action.triggered.connect(qApp.quit)
            tray_menu = QMenu()
            tray_menu.addAction(open_action)
            tray_menu.addAction(quit_action)
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.show()
            self.logger.debug("System tray icon setup completed")
        except Exception as e:
            self.logger.error(f"Error setting up tray icon: {e}", exc_info=True)
            raise

    def setup_window(self):
        try:
            self.ui.toggle.clicked.connect(self.toggle_pressed)
            self.ui.autostart_checkbox.stateChanged.connect(self.on_autostart_changed)
            icon_path = resource_path("icons/StayAwake.ico")
            self.setWindowIcon(QtGui.QIcon(icon_path))
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.setWindowTitle("Stay Awake")
            self.logger.debug("Window setup completed")
        except Exception as e:
            self.logger.error(f"Error setting up window: {e}", exc_info=True)
            raise

    def tray_icon_single_click(self, reason):
        if reason == self.tray_icon.Trigger:
            self.showNormal()
            self.activateWindow()

    def start_prevent_sleep(self):
        """Start preventing sleep."""
        try:
            if not self.running:
                self.ui.toggle.setText("Stop")
                self.status = "on"
                self.running = True
                self.prevent_sleep = PreventSleep()
                self.prevent_sleep.start()
                self.logger.info("Prevent sleep started")
        except Exception as e:
            self.logger.error(f"Error starting prevent sleep: {e}", exc_info=True)
            raise

    def stop_prevent_sleep(self):
        """Stop preventing sleep."""
        try:
            if self.running:
                self.ui.toggle.setText("Start")
                self.status = "off"
                self.running = False
                if self.prevent_sleep:
                    self.prevent_sleep.terminate()
                self.logger.info("Prevent sleep stopped")
        except Exception as e:
            self.logger.error(f"Error stopping prevent sleep: {e}", exc_info=True)
            raise

    def toggle_pressed(self):
        """Handle toggle button press."""
        if self.running:
            self.stop_prevent_sleep()
        else:
            self.start_prevent_sleep()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            if self.windowState() & Qt.WindowMinimized:
                event.ignore()
                self.hide()
                self.tray_icon.show()
                self.tray_icon.showMessage(
                    "Stay Awake is currently " + self.status + ".",
                    "Minimized to tray.",
                    QSystemTrayIcon.Information,
                )

    def get_exe_path(self):
        """Get the path to the executable or script."""
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            return sys.executable
        else:
            # Running as script
            return f'"{sys.executable}" "{os.path.abspath(__file__)}"'

    def is_autostart_enabled(self):
        """Check if autostart is enabled in Windows registry."""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.AUTOSTART_REG_KEY,
                0,
                winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, self.AUTOSTART_VALUE_NAME)
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception as e:
            self.logger.error(f"Error checking autostart: {e}", exc_info=True)
            return False

    def set_autostart(self, enabled):
        """Enable or disable autostart in Windows registry."""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.AUTOSTART_REG_KEY,
                0,
                winreg.KEY_WRITE
            )
            if enabled:
                exe_path = self.get_exe_path()
                winreg.SetValueEx(
                    key,
                    self.AUTOSTART_VALUE_NAME,
                    0,
                    winreg.REG_SZ,
                    exe_path
                )
            else:
                try:
                    winreg.DeleteValue(key, self.AUTOSTART_VALUE_NAME)
                except FileNotFoundError:
                    pass  # Already removed
            winreg.CloseKey(key)
            return True
        except Exception as e:
            self.logger.error(f"Error setting autostart: {e}", exc_info=True)
            return False

    def load_autostart_state(self):
        """Load autostart state from registry and update checkbox."""
        is_enabled = self.is_autostart_enabled()
        self.ui.autostart_checkbox.setChecked(is_enabled)

    def on_autostart_changed(self, state):
        """Handle autostart checkbox state change."""
        enabled = state == Qt.Checked
        success = self.set_autostart(enabled)
        if not success:
            # Revert checkbox if setting failed
            self.ui.autostart_checkbox.blockSignals(True)
            self.ui.autostart_checkbox.setChecked(not enabled)
            self.ui.autostart_checkbox.blockSignals(False)


def set_app_icon():
    try:
        app_icon = QtGui.QIcon()
        app_icon.addFile(resource_path("icons/16x16.png"), QtCore.QSize(16, 16))
        app_icon.addFile(resource_path("icons/32x32.png"), QtCore.QSize(32, 32))
        app_icon.addFile(resource_path("icons/48x48.png"), QtCore.QSize(48, 48))
        app_icon.addFile(resource_path("icons/192x192.png"), QtCore.QSize(192, 192))
        app_icon.addFile(resource_path("icons/512x512.png"), QtCore.QSize(512, 512))
        app.setWindowIcon(app_icon)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error setting app icon: {e}", exc_info=True)


if __name__ == "__main__":
    # Set up logging first
    logger = setup_logging()
    
    # Set up global exception handler
    sys.excepthook = exception_handler
    
    try:
        app = QtWidgets.QApplication([])
        
        # Set up Qt message handler
        def qt_message_handler(msg_type, context, message):
            """Handle Qt messages and log them."""
            if msg_type == QtCore.QtDebugMsg:
                logger.debug(f"Qt: {message}")
            elif msg_type == QtCore.QtWarningMsg:
                logger.warning(f"Qt: {message}")
            elif msg_type == QtCore.QtCriticalMsg:
                logger.error(f"Qt: {message}")
            elif msg_type == QtCore.QtFatalMsg:
                logger.critical(f"Qt FATAL: {message}")
        
        QtCore.qInstallMessageHandler(qt_message_handler)
        
        set_app_icon()
        application = StayAwakeApp()
        application.hide()  # Start minimized to tray
        logger.info("Application started successfully, entering event loop")
        sys.exit(app.exec_())
    except Exception as e:
        logger.critical(f"Fatal error during application startup: {e}", exc_info=True)
        logger.critical("=" * 80)
        sys.exit(1)
