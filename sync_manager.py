from config_manager import ConfigManager
from dropbox_manager import DropboxManager
import sqlite3
import datetime
import os
import hashlib
import json
from tzlocal import get_localzone
import pytz

import string

import random


class SyncManager():

    def __init__(self, config_manager: ConfigManager, dropbox_manager: DropboxManager):
        self.config_manager = config_manager
        self.dropbox_manager = dropbox_manager
        self.local_path = self.config_manager.config["local_saves_path"]
        self.dropbox_path = self.config_manager.config["dropbox_folder_path"]
        self.delta_db_path = self.config_manager.config["delta_db_path"]

        # USE A HASHMAP game/id map
        self.game_map = {}

        # game saves
        self.sav_map = {}

        # sync queues
        self.upload_queue = []
        self.download_queue = []

    def load_game_data(self):
        """Load from Delta's SQL Database
        """
        try:
            conn = sqlite3.connect(self.delta_db_path)
            cursor = conn.cursor()

            # lets make the dict bi-directional
            cursor.execute("SELECT ZNAME, ZIdentifier FROM zgame")
            for name, identifier in cursor.fetchall():
                self.game_map[name] = identifier
                self.game_map[identifier] = name

            # then get save information
            cursor.execute("""
                           SELECT gs.ZIDENTIFIER, ZMODIFIEDDATE, g.ZNAME
                           FROM zgamesave gs
                           JOIN zgame g ON gs.ZGAME = g.Z_PK
                           """)

            for identifier, modified_date, name in cursor.fetchall():
                if identifier and modified_date and name:
                    cocoa_epoch = datetime.datetime(2001, 1, 1)
                    timestamp = cocoa_epoch + \
                        datetime.timedelta(seconds=modified_date)

                    self.sav_map[identifier] = {
                        'name': name,
                        'timestamp': timestamp,
                        'local_modified': None,
                        'local_path': None,
                        'local_header_path': None,
                        'dropbox_path': None,
                        'dropbox_filename': None,
                        'dropbox_modified': None,
                        'dropbox_header_path': None,
                        'dropbox_header_filename': None,
                        'dropbox_header_modified': None
                    }

            conn.close()
            return True
        except Exception as e:
            print(e)
            return False

    def scan_local_saves(self):
        """scans local save folder to find existing saves
        """
        try:
            local_files = os.listdir(self.local_path)
            for file in local_files:
                parts = file.split(".")
                if parts[0] in self.game_map:
                    full_path = os.path.join(self.local_path, file)
                    modified_time = datetime.datetime.fromtimestamp(
                        os.path.getmtime(full_path))

                    self.sav_map[self.game_map[parts[0]]
                                 ]['local_path'] = full_path
                    self.sav_map[self.game_map[parts[0]]
                                 ]['local_modified'] = modified_time
            return True

        except Exception as e:
            print(e)
            return False

    def scan_dropbox_saves(self):
        """Scan Dropbox folder to find existing save files"""
        try:
            # Get list of files in the Dropbox Delta folder
            result = self.dropbox_manager.dbx.files_list_folder(
                self.dropbox_path)

            for entry in result.entries:
                if hasattr(entry, 'name') and not hasattr(entry, 'folder'):  # It's a file
                    filename = entry.name
                    identifier = None
                    file_type = None

                    # Handle different file naming patterns
                    if filename.startswith("gamesave-"):
                        # Format: gamesave-IDENTIFIER
                        print("this is a game header " + filename)
                        identifier = filename.replace("gamesave-", "", 1)
                        file_type = "header"
                    elif filename.startswith("GameSave-") and filename.endswith("-gameSave"):
                        # Format: GameSave-IDENTIFIER-gameSave
                        print("this is a game save " + filename)
                        middle_part = filename.replace(
                            "GameSave-", "", 1).replace("-gameSave", "", 1)
                        identifier = middle_part
                        file_type = "save"

                    if identifier and identifier in self.sav_map and file_type == "save":
                        dropbox_path = f"{self.dropbox_path}/{filename}"

                        # Get metadata for modified time
                        metadata = self.dropbox_manager.get_file_metadata(
                            dropbox_path)
                        if metadata and hasattr(metadata, 'server_modified'):
                            self.sav_map[identifier]['dropbox_path'] = dropbox_path
                            self.sav_map[identifier]['dropbox_modified'] = metadata.server_modified
                            self.sav_map[identifier]['dropbox_filename'] = filename
                    elif identifier and identifier in self.sav_map and file_type == "header":
                        dropbox_path = f"{self.dropbox_path}/{filename}"

                        # Get metadata for modified time
                        metadata = self.dropbox_manager.get_file_metadata(
                            dropbox_path)
                        if metadata and hasattr(metadata, 'server_modified'):
                            self.sav_map[identifier]['dropbox_header_path'] = dropbox_path
                            self.sav_map[identifier]['dropbox_header_modified'] = metadata.server_modified
                            self.sav_map[identifier]['dropbox_header_filename'] = filename
                        # we also need to generate the actual header file 


            return True
        except Exception as e:
            print(f"Error scanning Dropbox saves: {e}")
            return False

    def compare_and_queue(self):
        """Compare timestamps and queue files for sync"""
        for identifier, info in self.sav_map.items():
            # Skip if the game doesn't exist in both places
            if not info.get('local_path') or not info.get('dropbox_path'):
                continue

            local_time = info.get('local_modified')
            dropbox_time = info.get('dropbox_modified')
            
            if dropbox_time.tzinfo is None:
                dropbox_time = dropbox_time.replace(tzinfo=pytz.UTC)
            else:
                # If it already has a timezone, ensure it's UTC
                dropbox_time = dropbox_time.astimezone(pytz.UTC)
            
            # Get the local timezone of the device
            local_timezone = get_localzone()
            if local_time.tzinfo is None:
                local_time = local_time.replace(tzinfo=local_timezone)
            else:
                # If it already has a timezone, convert it to the local timezone
                local_time = local_time.astimezone(local_timezone)
            
            if local_time and dropbox_time:
                # Add a small buffer (e.g., 1 minute) to avoid syncing identical files
                time_diff = abs((local_time - dropbox_time).total_seconds())
                if time_diff < 30:  # Less than a minute difference
                    continue

                if local_time > dropbox_time:
                    print("upload queue appended")
                    # Local is newer, upload to Dropbox
                    self.create_metadata_file(self.sav_map[identifier]['local_path'], info['dropbox_header_path'], identifier)
                    revised_metadata_path = info['dropbox_header_path'].split("/")[2] 
                    self.upload_queue.append({
                        'identifier': identifier,
                        'name': info['name'],
                        'local_path': info['local_path'],
                        'dropbox_path': info['dropbox_path'],
                        'local_header_path': info['local_header_path'],
                        'dropbox_header_path': revised_metadata_path
                    })
                else:
                    # Dropbox is newer, download to local

                    print("download queue appended")
                    self.download_queue.append({
                        'identifier': identifier,
                        'name': info['name'],
                        'local_path': info['local_path'],
                        'dropbox_path': info['dropbox_path']
                    })

    def execute_sync(self, callback=None):
        """Execute the sync operations: Items in upload should not also be in download!! (there could be a condition)"""

        total_operations = len(self.upload_queue) + len(self.download_queue)
        completed = 0

        # Process uploads
        for item in self.upload_queue:
            try:
                success = self.dropbox_manager.upload_file(
                    item['local_path'],
                    item['dropbox_path']
                )
                completed += 1
                
                success = self.dropbox_manager.upload_file(
                    item['local_header_path'],
                    item['dropbox_header_path']
                )
                completed += 1
                if callback:
                    callback(completed, total_operations,
                             f"Uploaded {item['name']}", success)
                
            except Exception as e:
                if callback:
                    callback(completed, total_operations,
                             f"Error uploading {item['name']}: {e}", False)

        # Process downloads
        for item in self.download_queue:
            try:
                # Create a temporary file path to avoid overwriting the original
                temp_path = item['local_path'] + '.tmp'

                success = self.dropbox_manager.download_file(
                    item['dropbox_path'],
                    temp_path
                )

                if success:
                    # If download was successful, replace the original file
                    os.replace(temp_path, item['local_path'])

                completed += 1
                if callback:
                    callback(completed, total_operations,
                             f"Downloaded {item['name']}", success)
            except Exception as e:
                if callback:
                    callback(completed, total_operations,
                             f"Error downloading {item['name']}: {e}", False)

                # Clean up temp file if it exists
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        return completed

    def run_sync(self, progress_callback=None):
        """Run the complete sync process"""
        # Load data from database
        if not self.load_game_data():
            return False, "Failed to load game data from database"

        # Scan local saves
        if not self.scan_local_saves():
            return False, "Failed to scan local saves"

        # Scan Dropbox saves
        if not self.scan_dropbox_saves():
            return False, "Failed to scan Dropbox saves"

        # Compare and queue files
        self.compare_and_queue()

        # If nothing to sync, we're done
        if not self.upload_queue and not self.download_queue:
            return True, "No files needed syncing"

        # Execute sync operations
        completed = self.execute_sync(progress_callback)

        return True, f"Completed {completed} sync operations"
    
    
    

    def create_metadata_file(self, save_path, metadata_path, game_id):
        """Creates a metadata file for a game save"""
        # Calculate SHA1 hash of the save file
        try:
            sha1_hash = self.calculate_sha1(save_path)
            

            # Build metadata structure
            metadata = {
                "files": [{
                    "remoteIdentifier": f"/delta emulator/gamesave-{game_id}-gameSave",
                    "identifier": "gameSave",
                    "sha1Hash": sha1_hash,
                    "size": os.path.getsize(save_path),
                    # You'd need a strategy for version identifiers
                    "versionIdentifier": self.generate_version_id()
                }],
                "relationships": {
                    "game": {
                        "type": "Game",
                        "identifier": game_id
                    }
                },
                "sha1Hash": sha1_hash,  # This might be different from the file hash
                "identifier": game_id,
                "record": {
                    "modifiedDate": self.sav_map[game_id]['local_modified'].isoformat(),
                    "sha1": sha1_hash
                },
                "type": "GameSave"
            }

            revised_metadata_path = metadata_path.split("/")[2] 
            print(revised_metadata_path)
            # Write metadata to file
            with open(self.local_path +  "/" + revised_metadata_path, 'w') as f:
                json.dump(metadata, f)
        except Exception as e:
            print(f"Error creating metadata file: {e}")

                
    def generate_version_id(self):
        # Generate a random 32-character hexadecimal string
        hex_chars = string.hexdigits.lower()  # Use lowercase hexadecimal characters
        version_identifier = ''.join(random.choice(hex_chars) for _ in range(32))
        return version_identifier


    def calculate_sha1(self, file_path):
        """Calculate SHA1 hash of a file"""
        hasher = hashlib.sha1()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
