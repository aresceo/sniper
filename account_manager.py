"""
Account manager for handling multiple Telegram sessions
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from config import API_ID, API_HASH, SESSION_DIR
from database import DatabaseManager

logger = logging.getLogger(__name__)

class AccountManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.clients: Dict[str, TelegramClient] = {}
        self.pending_sessions: Dict[str, TelegramClient] = {}
    
    def get_session_path(self, phone_number: str) -> str:
        """Get the session file path for a phone number"""
        clean_phone = phone_number.replace('+', '').replace('-', '').replace(' ', '')
        return os.path.join(SESSION_DIR, f"session_{clean_phone}")
    
    async def add_new_account(self, phone_number: str) -> tuple[bool, str]:
        """Add a new account and send verification code"""
        try:
            session_name = self.get_session_path(phone_number)
            
            # Create new client
            client = TelegramClient(session_name, API_ID, API_HASH)
            await client.connect()
            
            # Send code request
            result = await client.send_code_request(phone_number)
            
            # Store pending session
            self.pending_sessions[phone_number] = client
            
            # Add to database
            self.db.add_account(phone_number, session_name)
            
            logger.info(f"Code sent to {phone_number}")
            return True, f"Codice inviato a {phone_number}. Usa il comando .code per verificare."
            
        except Exception as e:
            logger.error(f"Error adding account {phone_number}: {e}")
            return False, f"Error: {str(e)}"
    
    async def verify_code(self, phone_number: str, code: str) -> tuple[bool, str]:
        """Verify the code for a pending account"""
        if phone_number not in self.pending_sessions:
            return False, "Nessuna sessione in attesa per questo numero. Usa prima il comando .new"
        
        try:
            client = self.pending_sessions[phone_number]
            
            # Sign in with code
            await client.sign_in(phone_number, code)
            
            # Get user info
            me = await client.get_me()
            
            # Store active client
            self.clients[phone_number] = client
            
            # Remove from pending
            del self.pending_sessions[phone_number]
            
            # Activate in database
            self.db.activate_account(phone_number)
            
            logger.info(f"Account {phone_number} verified successfully")
            username = getattr(me, 'username', 'N/A')
            first_name = getattr(me, 'first_name', 'Sconosciuto')
            return True, f"Account verificato! Connesso come {first_name} (@{username})"
            
        except PhoneCodeInvalidError:
            return False, "Codice di verifica non valido. Riprova."
        except SessionPasswordNeededError:
            return False, "Questo account ha la 2FA attivata. Non ancora supportata."
        except Exception as e:
            logger.error(f"Error verifying code for {phone_number}: {e}")
            return False, f"Error: {str(e)}"
    
    async def load_existing_sessions(self):
        """Load all existing active sessions"""
        accounts = self.db.get_active_accounts()
        
        for account in accounts:
            try:
                client = TelegramClient(account['session'], API_ID, API_HASH)
                await client.connect()
                
                if await client.is_user_authorized():
                    self.clients[account['phone']] = client
                    logger.info(f"Loaded session for {account['phone']}")
                else:
                    logger.warning(f"Session for {account['phone']} is not authorized")
                    
            except Exception as e:
                logger.error(f"Error loading session for {account['phone']}: {e}")
    
    def get_active_clients(self) -> Dict[str, TelegramClient]:
        """Get all active clients"""
        return self.clients.copy()
    
    def get_client_list(self) -> List[str]:
        """Get list of active client phone numbers"""
        return list(self.clients.keys())
    
    async def disconnect_all(self):
        """Disconnect all clients"""
        for client in self.clients.values():
            try:
                if hasattr(client, 'disconnect'):
                    await client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting client: {e}")
        
        for client in self.pending_sessions.values():
            try:
                if hasattr(client, 'disconnect'):
                    await client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting pending client: {e}")
        
        self.clients.clear()
        self.pending_sessions.clear()
