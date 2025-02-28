from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QListWidget
from PySide6.QtCore import Qt
from data import get_games
import sys
import logging

from PySide6.QtWidgets import QFileDialog, QMessageBox, QHBoxLayout

import os

from config_manager import ConfigManager
from dropbox_manager import DropboxManager


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GameSyncApp(QMainWindow):
    """
    Main application window for the Game Sync app.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Game Sync App")
        self.setGeometry(100, 100, 800, 600)

        self.config_manager = ConfigManager()
        self.dropbox_manager = DropboxManager(self.config_manager)
        
        self.dropbox_label = QLabel(
            "Dropbox not connected", alignment=Qt.AlignCenter)
        self.dropbox_button = QPushButton("Connect to Dropbox")
        self.dropbox_folder_button = QPushButton("Select Dropbox Folder")

        self.dropbox_folder_label = QLabel(
            "Dropbox folder not found", alignment=Qt.AlignCenter)
        if self.config_manager.config["dropbox_token"]:
            self.init_dropbox()

        # Initialize UI
        self.init_ui()
        self.update_sync_button()

    def init_ui(self):
        """
        Initialize the user interface.
        """
        # Create a central widget and main vertical layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()

        # Add a label
        self.label = QLabel(
            "Click the button to retrieve games from the database.", alignment=Qt.AlignCenter)
        main_layout.addWidget(self.label)

        # Add a button to retrieve database
        self.button = QPushButton("Retrieve Database")
        self.button.clicked.connect(self.retrieve_db_info)
        main_layout.addWidget(self.button)

        # Add a list widget to display games
        self.game_list = QListWidget()
        main_layout.addWidget(self.game_list)

        # Configuration section label
        self.config_label = QLabel("Configuration", alignment=Qt.AlignCenter)
        main_layout.addWidget(self.config_label)

        # Delta DB selection section
        delta_db_layout = QHBoxLayout()
        self.delta_db_button = QPushButton("Select Delta.sqlite")
        self.delta_db_button.clicked.connect(self.select_delta_db)
        delta_db_layout.addWidget(self.delta_db_button)

        self.db_label = QLabel("No DB found", alignment=Qt.AlignCenter)
        if self.config_manager.config["delta_db_path"]:
            self.db_label.setText(self.config_manager.config["delta_db_path"])
        delta_db_layout.addWidget(self.db_label)
        main_layout.addLayout(delta_db_layout)

        # Local saves folder selection section
        local_saves_layout = QHBoxLayout()
        self.local_saves_button = QPushButton("Select Local Saves Folder")
        self.local_saves_button.clicked.connect(self.select_local_saves)
        local_saves_layout.addWidget(self.local_saves_button)

        self.saves_label = QLabel(
            "No Saves Folder Set", alignment=Qt.AlignCenter)
        if self.config_manager.config["local_saves_path"]:
            self.saves_label.setText(
                self.config_manager.config["local_saves_path"])
        local_saves_layout.addWidget(self.saves_label)
        main_layout.addLayout(local_saves_layout)

        # Dropbox connection section
        dropbox_layout = QHBoxLayout()
        self.dropbox_button.clicked.connect(self.connect_to_dropbox)
        dropbox_layout.addWidget(self.dropbox_button)

        self.dropbox_label = QLabel(
            "Dropbox Status: Disconnected", alignment=Qt.AlignCenter)
        dropbox_layout.addWidget(self.dropbox_label)
        main_layout.addLayout(dropbox_layout)

        # Dropbox folder selection section
        dropbox_folder_layout = QHBoxLayout()
        self.dropbox_folder_button = QPushButton("Select Dropbox Folder")
        self.dropbox_folder_button.clicked.connect(self.select_dropbox_folder)
        dropbox_folder_layout.addWidget(self.dropbox_folder_button)

        self.dropbox_folder_label = QLabel(
            "No Dropbox Folder Selected", alignment=Qt.AlignCenter)
        dropbox_folder_layout.addWidget(self.dropbox_folder_label)
        main_layout.addLayout(dropbox_folder_layout)

        # Sync button
        self.sync_button = QPushButton("Sync Files")
        self.sync_button.clicked.connect(self.sync_files)
        # Disabled until configuration is complete
        self.sync_button.setEnabled(False)
        main_layout.addWidget(self.sync_button)

        # Set the main layout
        central_widget.setLayout(main_layout)

    def select_delta_db(self):
        """Let user select Delta.sqlite file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Delta.sqlite", "", "SQLite Files (*.sqlite);;All Files (*)"
        )

        if file_path:
            self.config_manager.set_config("delta_db_path", file_path)
            self.db_label.setText(self.config_manager.config["delta_db_path"])
            self.delta_db_button.setText(
                f"Delta DB: {os.path.basename(file_path)}")
            self.update_sync_button()

    def retrieve_db_info(self):
        """
        Handle button click event.
        """
        try:
            games = get_games(self.config_manager.config["delta_db_path"])
            if not games:
                self.label.setText("No games found in the database.")
                return
            for game in games:
                self.game_list.addItem(str(game))
                print(game)
            self.label.setText(
                f"Retrieved {len(games)} games from the database.")
            logger.info(f"Retrieved {len(games)} games.")

        except Exception as e:
            self.label.setText("An error occurred while retrieving games.")
            logger.error(f"Error retrieving games: {e}")

    def select_local_saves(self):
        """Let user select local saves folder"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Local Saves Folder"
        )

        if folder_path:
            self.config_manager.set_config("local_saves_path", folder_path)
            self.saves_label.setText(
                self.config_manager.config["local_saves_path"])
            self.local_saves_button.setText(
                f"Saves: {os.path.basename(folder_path)}")
            self.update_sync_button()

    def init_dropbox(self):
        """Initialize Dropbox connection from saved token"""
        if self.dropbox_manager.initialize_from_token():
            self.dropbox_label.setText("Connected")
            self.dropbox_button.setText("Reconnect to Dropbox")
            self.dropbox_folder_button.setEnabled(True)

            # If we have a saved folder path, display it
            if self.config_manager.config["dropbox_folder_path"]:
                self.dropbox_folder_label.setText(
                    self.config_manager.config["dropbox_folder_path"])

    def connect_to_dropbox(self):
        """Connect to Dropbox using OAuth flow"""
        if self.dropbox_manager.initialize_from_token():
            self.dropbox_label.setText("Connected")
            self.dropbox_button.setText("Reconnect to Dropbox")
            self.dropbox_folder_button.setEnabled(True)
            self.log_message("Connected to Dropbox using saved token")
            # self.auto_detect_delta_folder()
        else:
            # Start the authorization flow
            if self.dropbox_manager.start_auth_flow(self):
                self.dropbox_label.setText("Connected")
                self.dropbox_button.setText("Reconnect to Dropbox")
                self.dropbox_folder_button.setEnabled(True)
                self.log_message("Successfully connected to Dropbox")
                # self.auto_detect_delta_folder()
            else:
                self.log_message("Failed to connect to Dropbox", is_error=True)
        self.update_sync_button()

    def select_dropbox_folder(self):
        """Let user select the Delta folder in Dropbox"""
        if not self.dropbox_manager.dbx:
            QMessageBox.warning(self, "Not Connected",
                                "Please connect to Dropbox first")
            return
        folders = self.dropbox_manager.list_folders("")
        print(f"Folders in root: {folders}")
        if not folders:
            QMessageBox.warning(
                self, "Error", "Failed to list Dropbox folders")
            return

        from PySide6.QtWidgets import QInputDialog
        folder, ok = QInputDialog.getItem(
            self, "Select Delta Folder", "Choose a folder:", folders, 0, False
        )

        if ok and folder:
            folder_path = f"/{folder}"
            self.config_manager.set_config("dropbox_folder_path", folder_path)
            self.dropbox_folder_label.setText(folder_path)
            self.log_message(f"Selected Dropbox folder: {folder_path}")
            self.update_sync_button()

    def update_sync_button(self):
        """Update sync button state based on configuration"""
        config = self.config_manager.config
        if config["delta_db_path"] and config["local_saves_path"] and config["dropbox_token"]:
            self.sync_button.setEnabled(True)
        else:
            self.sync_button.setEnabled(False)

    def sync_files(self):
        """_summary_
        """
        pass

    def log_message(self, message, is_error=False):
        """Add a message to the sync log"""
        pass
        # timestamp = time.strftime("%H:%M:%S")
        # prefix = "ERROR: " if is_error else ""
        # log_entry = f"[{timestamp}] {prefix}{message}"

        # item = QListWidgetItem(log_entry)
        # if is_error:
        #     item.setForeground(Qt.red)

        # self.sync_log.addItem(item)
        # self.sync_log.scrollToBottom()
        # logger.info(message) if not is_error else logger.error(message)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = GameSyncApp()
    window.show()

    sys.exit(app.exec())
