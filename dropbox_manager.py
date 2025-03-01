import dropbox
from dropbox.exceptions import AuthError
import os
from dotenv import load_dotenv
from dropbox import DropboxOAuth2FlowNoRedirect
import webbrowser
from PySide6.QtWidgets import QInputDialog, QMessageBox
from config_manager import ConfigManager

load_dotenv()


class DropboxManager:
    APP_KEY = os.getenv("DROPBOX_APP_KEY")
    APP_SECRET = os.getenv("DROPBOX_APP_SECRET")

    def __init__(self, config_manager: ConfigManager):
        self.dbx = None
        self.config_manager = config_manager

    def initialize_from_token(self, token=None):
        """
        Initializes the Dropbox client using an existing access token.

        Args:
            token (str, optional): The Dropbox access token. If None, it tries to load the token from the config.

        Returns:
            bool: True if the client was successfully initialized, False otherwise.
        """
        if not token and self.config_manager.config["dropbox_token"]:
            token = self.config_manager.config["dropbox_token"]


        if not token:
            return False

        try:
            self.dbx = dropbox.Dropbox(token)
            # Test if token is valid
            self.dbx.users_get_current_account()
            return True
        except AuthError:
            return False

    def start_auth_flow(self, parent_widget):
        """Start OAuth2 flow to get Dropbox authorization"""
        auth_flow = DropboxOAuth2FlowNoRedirect(
            self.APP_KEY,
            self.APP_SECRET,
            token_access_type="offline"
        )

        auth_url = auth_flow.start()
        # Open the URL in user's browser
        webbrowser.open(auth_url)

        # Get the authorization code from user
        auth_code, ok = QInputDialog.getText(
            parent_widget,
            "Dropbox Authorization",
            "Please authorize the app in your browser and enter the code here:"
        )

        if not ok or not auth_code:
            return False

        try:
            # Complete the authorization flow
            oauth_result = auth_flow.finish(auth_code)

            # Save the access token
            self.config_manager.set_config("dropbox_token", oauth_result.access_token)

            # Initialize Dropbox client with the token
            self.dbx = dropbox.Dropbox(oauth_result.access_token)
            return True
        except Exception as e:
            QMessageBox.warning(
                parent_widget,
                "Authorization Error",
                f"Failed to authorize with Dropbox: {str(e)}"
            )
            return False

    def list_folders(self, path=""):
        """List all contents in the specified folder."""
        try:
            # Use '' to refer to the root folder
            folder_path = "" if path == "" else path

            # List folder contents
            result = self.dbx.files_list_folder(folder_path, recursive=True)
            print(f"Recursive result entries count: {len(result.entries)}")

            # Extract folder names from the result
            folders = [entry.name for entry in result.entries if isinstance(
                entry, dropbox.files.FolderMetadata)]

            return folders
        except Exception as e:
            print(f"Error listing folder contents: {e}")
            return False

    def check_token_info(self):
        """Check information about the current token"""
        try:
            token_info = self.dbx.check_user(self.dbx._oauth2_access_token)
            print(f"Token info: {token_info}")
            return token_info
        except Exception as e:
            print(f"Error checking token: {e}")
            return None

    def get_delta_folder(self):
        """Attempt to automatically locate the Delta folder"""
        folders = self.list_folders("")

        # Check for common Delta folder names
        delta_folder_candidates = ["Delta", "Delta Emulator", "DeltaSync"]

        for candidate in delta_folder_candidates:
            if candidate in folders:
                return f"/{candidate}"

        return None

    def download_file(self, dropbox_path, local_path):
        """Download a file from Dropbox to local path"""
        if not self.dbx:
            return False

        try:
            self.dbx.files_download_to_file(local_path, dropbox_path)
            return True
        except Exception:
            return False

    def upload_file(self, local_path, dropbox_path):
        """Upload a file from local path to Dropbox"""
        print(local_path, dropbox_path)
        
        if not self.dbx:
            return False

        try:
            with open(local_path, 'rb') as f:
                self.dbx.files_upload(
                    f.read(),
                    dropbox_path,
                    mode=dropbox.files.WriteMode.overwrite
                )
            return True
        except Exception as e:
            print(f"Error uploading file: {e}")
            return False
            

    def get_file_metadata(self, path):
        """Get metadata for a file including last modified time"""
        if not self.dbx:
            return None

        try:
            metadata = self.dbx.files_get_metadata(path)
            return metadata
        except Exception:
            return None
