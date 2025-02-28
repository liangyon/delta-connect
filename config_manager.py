import json
import os
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config = {
            "delta_db_path": "",
            "dropbox_token": "",
            "dropbox_folder_path": "",
            "local_saves_path": ""
        }
        self.load_config()
        
    def set_config(self, config, value):
        """Setter for configs
        """
        self.config[config] = value
        self.save_config()
    
    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
                return True
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        return False
    
    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False