"""
JSON-based data manager for storing accounts, usernames, and configuration
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional
from config import SESSION_DIR

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.data_dir = "data"
        self.accounts_file = os.path.join(self.data_dir, "accounts.json")
        self.usernames_file = os.path.join(self.data_dir, "usernames.json")
        self.config_file = os.path.join(self.data_dir, "config.json")
        self.sniped_file = os.path.join(self.data_dir, "sniped_history.json")
        self.init_json_files()

    def init_json_files(self):
        """Initialize JSON files with required structure"""
        try:
            # Create data directory if it doesn't exist
            os.makedirs(self.data_dir, exist_ok=True)

            # Initialize accounts.json
            if not os.path.exists(self.accounts_file):
                self._save_json(self.accounts_file, [])

            # Initialize usernames.json
            if not os.path.exists(self.usernames_file):
                self._save_json(self.usernames_file, [])

            # Initialize config.json with defaults
            if not os.path.exists(self.config_file):
                default_config = {
                    "check_interval": "30",
                    "pair_delay": "60"
                }
                self._save_json(self.config_file, default_config)

            # Initialize sniped_history.json
            if not os.path.exists(self.sniped_file):
                self._save_json(self.sniped_file, [])

            logger.info("JSON data files initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing JSON files: {e}")
            raise

    def _load_json(self, file_path: str, default=None):
        """Load data from JSON file"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return default if default is not None else []
        except Exception as e:
            logger.error(f"Error loading JSON from {file_path}: {e}")
            return default if default is not None else []

    def _save_json(self, file_path: str, data):
        """Save data to JSON file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving JSON to {file_path}: {e}")
            raise

    def add_account(self, phone_number: str, session_name: str) -> bool:
        """Add a new account to the JSON file"""
        try:
            accounts = self._load_json(self.accounts_file, [])

            # Check if account already exists
            for account in accounts:
                if account.get('phone_number') == phone_number:
                    logger.warning(f"Account {phone_number} already exists")
                    return False

            # Add new account
            new_account = {
                "phone_number": phone_number,
                "session_name": session_name,
                "is_active": False,
                "added_timestamp": datetime.now().isoformat()
            }
            accounts.append(new_account)
            self._save_json(self.accounts_file, accounts)

            logger.info(f"Added account: {phone_number}")
            return True

        except Exception as e:
            logger.error(f"Error adding account: {e}")
            return False

    def activate_account(self, phone_number: str) -> bool:
        """Activate an account"""
        try:
            accounts = self._load_json(self.accounts_file, [])

            for account in accounts:
                if account["phone_number"] == phone_number:
                    account["is_active"] = True
                    break

            self._save_json(self.accounts_file, accounts)
            logger.info(f"Activated account: {phone_number}")
            return True

        except Exception as e:
            logger.error(f"Error activating account: {e}")
            return False

    def deactivate_account(self, phone_number: str) -> bool:
        """Deactivate an account"""
        try:
            accounts = self._load_json(self.accounts_file, [])

            for account in accounts:
                if account["phone_number"] == phone_number:
                    account["is_active"] = False
                    break

            self._save_json(self.accounts_file, accounts)
            logger.info(f"Deactivated account: {phone_number}")
            return True

        except Exception as e:
            logger.error(f"Error deactivating account: {e}")
            return False

    def get_active_accounts(self) -> List[Dict]:
        """Get all active accounts"""
        try:
            accounts = self._load_json(self.accounts_file, [])
            return [{"phone": acc["phone_number"], "session": acc["session_name"]} 
                   for acc in accounts if acc.get("is_active", False)]
        except Exception as e:
            logger.error(f"Error getting active accounts: {e}")
            return []

    def get_all_accounts(self) -> List[Dict]:
        """Get all accounts"""
        try:
            accounts = self._load_json(self.accounts_file, [])
            return [{"phone": acc["phone_number"], "session": acc["session_name"], "active": acc.get("is_active", False)} 
                   for acc in accounts]
        except Exception as e:
            logger.error(f"Error getting all accounts: {e}")
            return []

    def add_username(self, username: str) -> bool:
        """Add a username to monitor"""
        try:
            usernames = self._load_json(self.usernames_file, [])
            clean_username = username.lstrip('@')

            # Check if username already exists
            for user in usernames:
                if user.get('username') == clean_username:
                    logger.warning(f"Username {username} already exists")
                    return False

            # Add new username
            new_username = {
                "username": clean_username,
                "is_active": True,
                "added_timestamp": datetime.now().isoformat(),
                "last_checked": None
            }
            usernames.append(new_username)
            self._save_json(self.usernames_file, usernames)

            logger.info(f"Added username: @{clean_username}")
            return True

        except Exception as e:
            logger.error(f"Error adding username: {e}")
            return False

    def remove_username(self, username: str) -> bool:
        """Remove a username from monitoring"""
        try:
            usernames = self._load_json(self.usernames_file, [])
            clean_username = username.lstrip('@')

            original_length = len(usernames)
            usernames = [u for u in usernames if u.get('username') != clean_username]

            if len(usernames) < original_length:
                self._save_json(self.usernames_file, usernames)
                logger.info(f"Removed username: @{clean_username}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error removing username: {e}")
            return False

    def get_active_usernames(self) -> List[str]:
        """Get all active usernames to monitor"""
        try:
            usernames = self._load_json(self.usernames_file, [])
            return [u["username"] for u in usernames if u.get("is_active", True)]
        except Exception as e:
            logger.error(f"Error getting usernames: {e}")
            return []

    def update_username_check(self, username: str):
        """Update last checked timestamp for a username"""
        try:
            usernames = self._load_json(self.usernames_file, [])

            for user in usernames:
                if user.get('username') == username:
                    user['last_checked'] = datetime.now().isoformat()
                    break

            self._save_json(self.usernames_file, usernames)

        except Exception as e:
            logger.error(f"Error updating username check: {e}")

    def set_config(self, key: str, value: str):
        """Set a configuration value"""
        try:
            config = self._load_json(self.config_file, {})
            config[key] = value
            self._save_json(self.config_file, config)
        except Exception as e:
            logger.error(f"Error setting config: {e}")

    def get_config(self, key: str, default: str = None) -> Optional[str]:
        """Get a configuration value"""
        try:
            config = self._load_json(self.config_file, {})
            return config.get(key, default)
        except Exception as e:
            logger.error(f"Error getting config: {e}")
            return default

    def add_sniped_username(self, username: str, channel_link: str = None, account_used: str = None):
        """Add a sniped username to history"""
        try:
            sniped_history = self._load_json(self.sniped_file, [])

            new_snipe = {
                "username": username,
                "channel_link": channel_link,
                "sniped_timestamp": datetime.now().isoformat(),
                "account_used": account_used
            }

            sniped_history.append(new_snipe)
            self._save_json(self.sniped_file, sniped_history)

            logger.info(f"Added sniped username to history: @{username}")

        except Exception as e:
            logger.error(f"Error adding sniped username: {e}")

    def get_sniped_usernames(self, limit: int = 50) -> List[Dict]:
        """Get history of sniped usernames"""
        try:
            sniped_history = self._load_json(self.sniped_file, [])

            # Sort by timestamp in descending order
            sniped_history.sort(key=lambda x: x.get("sniped_timestamp", ""), reverse=True)

            # Apply limit
            limited_history = sniped_history[:limit]

            return [{"username": entry["username"], 
                    "channel_link": entry.get("channel_link"), 
                    "timestamp": entry.get("sniped_timestamp"), 
                    "account": entry.get("account_used")} 
                   for entry in limited_history]

        except Exception as e:
            logger.error(f"Error getting sniped usernames: {e}")
            return []